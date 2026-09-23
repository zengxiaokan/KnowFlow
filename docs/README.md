# KnowFlow 学习导航

这套文档是一份能照着操作的实验手册。建议严格按编号阅读；完成一篇，就勾选该篇的验收清单。遇到错误时先看“常见错误”，不要一上来就删除容器或数据库。

## 你最终会做出什么

KnowFlow 是企业知识库与线性智能工作流平台：用户创建组织和知识库，上传 PDF/DOCX/Markdown；后台完成解析、切片、向量化和入库；然后只在当前知识库内进行带引用的流式问答。系统还保存会话记忆、模型 Token 用量、任务进度、审计记录和工作流运行记录。

```text
浏览器（Django 模板 + JavaScript）
             │ HTTP / WebSocket
             ▼
Django + DRF + Channels ───── PostgreSQL + pgvector
             │                       │
             ├──── Redis ────────────┤
             ▼                       ▼
  Celery Worker：解析 / 向量化 / 问答 / 工作流
             │
     DeepSeek（生成）+ SiliconFlow BGE-M3（向量）
```

## 先选择运行方式

| 方式 | 适合场景 | 数据库与异步任务 | 模型 |
| --- | --- | --- | --- |
| Docker Compose（推荐） | 演示、真实 RAG、最终作业 | PostgreSQL、Redis、Celery 都真实运行 | 填 Key 后调用真实供应商 |
| 本机演示模式 | 没有 Docker、阅读页面和单元逻辑 | SQLite、内存 Channel、Celery 同步 | 确定性的演示 Provider |

期末展示请用 Docker Compose。`KNOWFLOW_LOCAL_DEMO=true` 只是临时学习或排错模式，不能替代真实 pgvector 检索。

## 推荐学习顺序

| 阶段 | 文档 | 完成后应能做到 |
| --- | --- | --- |
| M0 | [00 环境准备](00-环境准备.md) → [01 Docker 与 Django](01-Docker与Django原理.md) | 启动四服务，知道请求流向 |
| M1 | [02 数据模型](02-数据模型与迁移.md) → [03 Celery](03-Celery异步任务.md) → [04 RAG](04-文档解析与RAG.md) → [05 WebSocket](05-WebSocket进度推送.md) | 上传资料并观察进度、失败重试 |
| M1 | [06 检索与提示词](06-检索与提示词设计.md) → [07 聊天与 Token](07-聊天与Token用量.md) | 获得带来源的流式回答 |
| M2 | [08 工作流](08-工作流领域模型.md) → [09 幂等性](09-任务编排与幂等性.md) | 创建线性工作流，理解安全重试 |
| M3 | [10 权限](10-权限与数据隔离.md) → [11 运维](11-部署与运维.md) | 管理角色、备份恢复、准备上线 |

## 每次都会用到的命令

在项目根目录 `D:\python\KnowFlow` 的 PowerShell 执行：

```powershell
docker compose up --build
docker compose ps
docker compose logs -f web
docker compose logs -f worker
docker compose exec web python manage.py check
docker compose exec web pytest -q
docker compose down
```

> 警告：`docker compose down -v` 会删除数据库、Redis 和上传文件的命名卷。没有验证备份前不要执行。

## 代码地图

| 位置 | 负责内容 |
| --- | --- |
| `config/` | Settings、ASGI、Celery 和总路由 |
| `apps/identity/` | 组织、成员、邀请、审计日志 |
| `apps/knowledge/` | 知识库、文档、解析、切片、向量、任务、权限 |
| `apps/chat/` | 会话、消息、检索问答、流式输出、用量 |
| `apps/workflows/` | 流程定义、运行记录、节点执行 |
| `templates/` / `static/` | 页面和浏览器交互 |
| `scripts/backup.ps1` | PostgreSQL 和媒体文件备份 |

## 改完代码后的固定自检

1. 执行 `docker compose exec web python manage.py check`。
2. 改模型时执行 `makemigrations`、`migrate`，检查新迁移文件。
3. 改异步逻辑时同时看 Worker 日志和页面任务状态。
4. 改权限时至少用两个账号验证允许和拒绝两种情况。
5. 执行 `docker compose exec web pytest -q`，通过后再提交或截图。

## 术语速查

- **组织**：多租户边界；一个用户可属于多个组织。
- **知识库**：资料集合，也是问答检索范围。
- **文档版本**：同一资料的一次上传结果；只有当前成功版本参与检索。
- **切片**：适合向量检索的小段文本，带标题、序号与向量。
- **IngestionTask**：用户可见的解析进度、错误和重试记录。
- **流式输出**：模型生成一小段，浏览器立刻收到一小段。

从 [00-环境准备](00-环境准备.md) 开始。
