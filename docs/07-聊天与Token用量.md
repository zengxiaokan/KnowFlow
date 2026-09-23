# 07：聊天与 Token 用量

## 概念

聊天不是把一段文本临时显示在页面上。为了支持刷新恢复、会话切换、重新生成、引用追溯和成本统计，KnowFlow 将会话和每一条消息都持久化。用户提问后先保存 User Message；再立刻创建状态为 `generating` 的 Assistant Message；后台任务开始时浏览器收到 `answer.started`，每个文本片段收到 `answer.delta`，最终保存完整回答、来源和用量。

Token 是模型处理文本的计量单位，不等于汉字数量。供应商若返回 usage，系统使用真实输入/输出 Token；流式接口未提供时，项目按字符数除以 4 做估算，并在 `is_estimated=True` 明确标记，不能把估算值当作账单精确数据。

## 本阶段目标

理解会话记忆、流式事件、失败状态、重新生成和用量记录；能从页面和数据库验证“问答没有因刷新丢失”。

## 数据如何保存

| 模型 | 保存内容 | 为什么需要 |
| --- | --- | --- |
| `Conversation` | 组织、知识库、创建人、标题、更新时间 | 切换历史会话、保证用户隔离 |
| `Message` | 角色、文本、状态、来源、对应问题 | 还原消息顺序、生成状态、重新生成 |
| `ModelUsageRecord` | Provider、模型、类型、输入/输出 Token、耗时、成功与否 | 查看成本和定位供应商问题 |

`Message.in_reply_to` 把生成的助手消息关联到它回答的用户消息。点击“重新生成”时，系统不覆盖旧回答，而是为同一个问题创建新的 `generating` Assistant Message；这样历史答案可保留并可追溯。

## 操作步骤

### 1. 验证会话记忆

1. 在已就绪知识库中问一个有资料支持的问题。
2. 等待流式回答完成并确认来源。
3. 再问“把它用三条总结一下”。
4. 刷新页面，打开同一会话，再发一个相关问题。

当前实现最多取最近 `CHAT_HISTORY_MESSAGE_LIMIT=6` 条已完成用户/助手消息；每条最多截取 `CHAT_HISTORY_MESSAGE_CHARS=1200` 字符。历史只用于理解指代，知识事实仍必须由本轮检索资料支持。

### 2. 验证生成期间的界面

发送问题后，浏览器立即显示用户气泡和 Assistant 占位；按钮应禁用，防止连续点击造成多份同问题任务。生成完成或失败后按钮恢复。网络中途刷新时，聊天 Consumer 连接后会查询最新助手消息，恢复 completed 或 failed 状态。

### 3. 查看用量

仪表盘展示组织范围 Token 汇总与趋势；后台 `ModelUsageRecord` 同时记录：

- Provider 与模型名；
- 调用种类：embedding、chat、workflow；
- 输入/输出 Token；
- 是否估算；
- 延迟毫秒数与成功状态。

嵌入阶段目前按文本长度估算输入 Token；工作流 LLM 也会记录估算用量。不要因为模型 API 没返回 usage 就把数字写成 0，这会让用量面板失真。

### 4. 用 Django shell 检查最近记录

```powershell
docker compose exec web python manage.py shell
```

```python
from apps.chat.models import Conversation, ModelUsageRecord
print(Conversation.objects.count())
for record in ModelUsageRecord.objects.all()[:5]:
    print(record.kind, record.model, record.input_tokens, record.output_tokens, record.is_estimated)
```

只读查看后输入 `exit()`。

## 编码任务

为“无 usage 的流式响应”写测试：使用 fake Provider 返回若干文本 delta、但不返回 usage；执行生成任务；断言 Assistant Message 是 `complete`，记录的 `is_estimated` 为真，输入/输出 Token 均不为负。再加一个 Provider 抛错测试，断言消息变为 `failed`，前端收到失败事件。

## 验收清单

- [ ] 刷新页面后历史会话与消息仍存在。
- [ ] 后续问题能理解上一轮的指代，但回答仍有本轮资料来源。
- [ ] 生成中按钮不可重复点击，终态会恢复。
- [ ] 无资料时显示明确兜底，而不是卡在生成中。
- [ ] 每次聊天/向量化/工作流模型调用有用量记录；估算值有标记。

## 常见错误

| 错误 | 后果 | 修正 |
| --- | --- | --- |
| 只在前端保存聊天 | 刷新、换设备后全部丢失 | 每条消息先入库再启动任务 |
| 把正在生成的消息当完成历史 | 下轮上下文可能包含半截内容 | 只取 `COMPLETE` 消息 |
| 流式失败不更新状态 | 按钮永远禁用、页面像卡死 | 统一处理 `answer.failed` |
| 日志记录 Key/鉴权头/隐含推理 | 泄露敏感信息 | 只存业务必须的模型名、用量、错误摘要 |

## 延伸阅读

定价统计还需要价格版本、币种和账单周期；不要在代码里硬编码临时单价。下一篇：[08-工作流领域模型](08-工作流领域模型.md)。
