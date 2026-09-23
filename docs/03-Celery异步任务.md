# 03：Celery 异步任务

## 概念

Celery 是后台任务系统。Django Web 负责快速返回页面，Celery Worker 从 Redis 取出任务后慢慢完成文档解析、调用 Embedding、模型问答和工作流。重要的是：Celery 的“成功/失败”不是用户唯一能看到的状态；项目另有 `IngestionTask` 表保存阶段、百分比、错误码、开始结束时间和尝试次数，刷新浏览器后仍然可见。

任务系统通常只能承诺 **at-least-once（至少执行一次）**：网络断开、Worker 重启、确认消息丢失时，同一任务可能又被投递。因此业务代码不能假设“绝不重复执行”。

## 本阶段目标

沿着一次上传读懂“创建任务 → 提交事务 → 投递 → Worker 更新状态 → WebSocket 推送”的路径；知道如何观察日志、手动重试，并在新增阶段时同步修改所有层。

## 真实处理流程

上传服务 `create_uploaded_document()` 的简化步骤：

1. 表单检查后缀、大小、批量限制。
2. 在一个数据库事务中创建 `Document`、`DocumentVersion`、`IngestionTask` 和审计日志。
3. 使用 `transaction.on_commit()`；事务真正提交后才调用 `enqueue_ingestion()`。
4. `enqueue_ingestion()` 重置任务状态，调用 `process_document.delay()`，把 Celery 任务 ID 记录回数据库。
5. Worker 执行 `process_document()`，依次完成提取、切片、向量化、索引。

```text
pending / queued (0%)
  → processing / extracting (5%)
  → processing / chunking (30%)
  → processing / embedding (45%~85%)
  → processing / indexing (90%)
  → succeeded / complete (100%)
                     └→ failed（保存错误码和错误原因）
```

任务的状态枚举与阶段枚举在 `apps/knowledge/models.py`；真正更新与广播在 `apps/knowledge/tasks.py` 的 `_set_task()`。

## 操作步骤

### 1. 观察一次任务

```powershell
docker compose logs -f worker
```

浏览器上传一个小 Markdown 文档，观察任务状态逐步变化。若想看数据库迁移、Web 页面请求和 Worker 是否都正常，另开窗口：

```powershell
docker compose logs -f web
docker compose exec web python manage.py shell
```

在 Django shell 内可以安全查看最近任务（不修改数据）：

```python
from apps.knowledge.models import IngestionTask
for task in IngestionTask.objects.all()[:5]:
    print(task.id, task.status, task.stage, task.progress, task.error_code)
```

输入 `exit()` 退出 shell。

### 2. 理解重试

`process_document` 使用 `max_retries=3`。当 Provider 发生可重试错误时，首次失败后等待 10 秒，之后 20 秒、40 秒，最多进行 3 次重试（初始执行加重试最多会有 4 次尝试）。每次都会更新 `attempt_count` 与页面可见的错误提示。

不可重试的解析错误，例如扫描 PDF、空 Word、页数超限、格式不支持，不应浪费时间反复请求；它们直接标记为 `failed`。用户在页面点击“重试”后，复用原有 `IngestionTask`，清除旧错误并再次投递。

### 3. 为什么要 `transaction.on_commit()`

下面是危险写法：

```python
with transaction.atomic():
    task = IngestionTask.objects.create(...)
    process_document.delay(str(task.id))  # 不要这样做
```

Worker 速度足够快时，可能在外层事务尚未提交时查询任务，读不到它或读到不完整数据。正确方式是：

```python
with transaction.atomic():
    task = IngestionTask.objects.create(...)
    transaction.on_commit(lambda: enqueue_ingestion(task))
```

## 编码任务

假设需要新增“内容清洗”阶段：

1. 在 `IngestionTask.Stage` 增加 `CLEANING`。
2. 在 `process_document()` 的文本提取后调用清洗逻辑，并用 `_set_task()` 更新阶段与合理百分比。
3. 检查页面状态文案和浏览器 JavaScript 是否能显示该阶段。
4. 增加测试，验证每次成功任务都会经过该阶段。
5. 人工上传一份文档，确认 WebSocket 页面实时显示新阶段。

不能只改 Worker：否则数据库、页面和测试的“状态语言”会不一致。

## 验收清单

- [ ] Worker 日志中能看到上传后产生的 Celery 任务。
- [ ] 页面显示排队、解析、切片、向量化、完成或失败中的正确阶段。
- [ ] 暂时性 Provider 故障会退避重试，最终失败能看到错误信息。
- [ ] 点击重试后旧错误清除，任务再次从 `queued` 开始。
- [ ] 成功索引后只有一组当前版本 Chunk，不出现重复块。

## 常见错误

| 现象 | 原因 | 排查/修复 |
| --- | --- | --- |
| 一直 pending | Worker 未启动或 Redis 不通 | 看 `docker compose ps` 和 Worker 日志 |
| Worker 报找不到文件 | Web/Worker 没共享媒体卷 | 检查 `compose.yaml` 的 `media_data` |
| 重试后 Chunk 成倍增加 | 未在事务内清理旧 Chunk | 对同一 version 先删除再 `bulk_create` |
| `DoesNotExist` 偶发出现 | 提交事务前就 `.delay()` | 使用 `transaction.on_commit()` |
| 把所有错误都自动重试 | 扫描件、格式错误永远不会成功 | 只对 `RetryableProviderError` 退避 |

## 延伸阅读

- [04-文档解析与 RAG](04-文档解析与RAG.md)
- 关键词：任务幂等、ack late、Worker prefetch、Outbox pattern。
