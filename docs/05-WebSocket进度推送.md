# 05：WebSocket 进度推送

## 概念

浏览器通过 /ws/tasks/uuid/ 订阅任务组；Worker 更新任务后，经 Redis Channels layer 广播状态。

## 本阶段目标

让用户看见阶段和百分比，而不是盲目等待上传页面。

## 操作步骤

阅读 events.py、consumers.py 和 static/js/app.js。Consumer 在连接前验证当前用户能否查看该任务。

## 编码任务

增加一个测试事件，确认未登录用户的 WebSocket 连接被拒绝。

## 验收清单

- 文档表格状态会在不刷新页面的情况下变化
- 完成后页面自动刷新并显示已就绪
- 非当前组织成员不能订阅任务

## 常见错误

不能把数据库对象直接发送到 WebSocket；事件载荷应是稳定、可序列化的字典。

## 延伸阅读

对比 WebSocket 与 SSE 的重连、双向通信和代理配置差异。

