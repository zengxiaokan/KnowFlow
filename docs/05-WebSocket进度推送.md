# 05：WebSocket 进度推送

## 概念

HTTP 是“浏览器请求一次，服务器回答一次”；WebSocket 是浏览器与服务器保持长连接，服务器有新事件时可主动推送。KnowFlow 用它解决两种等待体验：文档处理进度与模型流式回答。用户不需要不断刷新页面，也不会在模型生成时误以为“消息没发出去”。

当前端连接地址形如 `/ws/tasks/<task_id>/` 或 `/ws/conversations/<conversation_id>/` 时，Consumer 会先检查登录和数据权限，再把连接加入相应频道组。Worker 更新状态后，将普通 JSON 字典发到 Redis Channel Layer；对应浏览器立即收到。

## 本阶段目标

理解任务和聊天的事件格式；知道 WebSocket 不是权限绕过通道；能用浏览器和日志排查连接失败。

## 两类连接与事件

| 场景 | 地址 | 典型事件 | 权限检查 |
| --- | --- | --- | --- |
| 文档任务 | `/ws/tasks/<uuid>/` | `status`、`stage`、`progress`、`error_message` | 当前用户必须能看见该任务所属知识库 |
| 聊天会话 | `/ws/conversations/<uuid>/` | `answer.started`、`answer.delta`、`answer.completed`、`answer.failed` | 当前用户必须是该会话创建者且属于组织 |

任务事件来自 `apps/knowledge/events.py` 的 `publish_task()`；任务 Consumer 在 `apps/knowledge/consumers.py`。聊天事件来自 `publish_conversation()`，聊天 Consumer 在 `apps/chat/consumers.py`。

## 操作步骤

### 1. 验证文档进度

1. 登录并打开某知识库。
2. 上传一个稍大的文本型 PDF 或 DOCX。
3. 不刷新页面，观察状态、阶段和进度变化。
4. 完成后页面应显示已就绪，或清晰错误信息。

浏览器按 F12 打开开发者工具，在 Network 中过滤 `WS` 可以看到 WebSocket 是否已连接。状态码 101 表示协议升级成功；4403 通常表示未登录或没有权限。

### 2. 验证聊天流式回答

1. 选择包含已就绪文档的知识库。
2. 输入问题并发送。
3. 发送按钮在生成期间应不可点，避免重复创建消息。
4. 回答内容应逐段出现，结束后显示来源与用量。
5. 刷新页面后重连 Consumer 会读取最近 Assistant 消息的状态，恢复 completed 或 failed 事件，避免页面卡在“思考中”。

### 3. 新增事件的步骤

假设新增 `task.warning`：

1. 定义稳定的 JSON 结构，例如 `{"code": "low_text", "message": "..."}`。
2. 在 Worker 或服务层调用发布函数；不要把 Django Model 实例直接序列化发送。
3. 在 Consumer 中把 Channels 的事件转为浏览器 JSON。
4. 在前端只按字段更新界面，不把错误文案当作逻辑条件。
5. 写未登录、无权限和正常连接三类测试。

## 编码任务

在开发环境中为任务页增加“连接状态”提示：连接成功显示“实时更新已连接”，关闭后显示“连接断开，将在页面刷新后获取最新状态”。不要在前端伪造成功状态；断开时仍应能刷新并从数据库读取真实任务记录。

## 验收清单

- [ ] 上传期间页面不刷新也能看到阶段、百分比变化。
- [ ] 生成回答时内容逐段出现，发送按钮被禁用。
- [ ] 回答完成后显示来源，失败后显示失败而不是空白成功消息。
- [ ] 未登录或无权用户连接 WebSocket 会被拒绝。
- [ ] 刷新会话页不会永远停在“生成中”。

## 常见错误

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| 连接立即关闭 | 没有登录 Cookie、权限不足或 URL 错 | 检查 4403、Consumer 的权限函数和路由 |
| Worker 更新了数据库但页面不变 | 未发布事件或 Redis Channel Layer 不通 | 看 Worker 日志和 Redis 配置 |
| 前端重复添加回答 | 重连与 delta 事件没有按 message ID 去重 | 以 Assistant message ID 为唯一标识更新 DOM |
| 发送按钮一直不可点 | 未处理 completed/failed/close | 所有终态都恢复可发送状态 |

## 延伸阅读

SSE 也可做单向流式输出；WebSocket 更适合本项目同时承载任务与聊天事件。继续阅读 [06-检索与提示词设计](06-检索与提示词设计.md)。
