# 01：Docker 与 Django 原理

## 概念

网页请求适合做很短的事情：检查权限、保存表单、返回页面。解析 100 页 PDF、调用 Embedding 或等待大模型生成可能花几秒到几分钟；若把它们放在同一个请求里，浏览器容易超时，Web 进程也会被占满。

KnowFlow 因此拆分职责：Django 创建业务记录；Celery Worker 做耗时计算；Redis 在两者之间传递任务与实时事件；PostgreSQL 保存最终事实；Channels/Daphne 将进度和回答文本通过 WebSocket 推给浏览器。

```text
浏览器上传 → Django 创建 Document / Version / IngestionTask
                              │ 事务提交后
                              ▼
                       Celery .delay() → Redis → Worker
                                                     │
浏览器进度 ← WebSocket ← Channels/Redis ← 更新任务、生成文本 ┘
```

## 本阶段目标

理解项目的启动方式、ASGI 与 WSGI 的差别、Redis 的角色，并能用日志判断每一个环节是否正常。

## 关键文件

| 文件 | 作用 | 初学者观察点 |
| --- | --- | --- |
| `compose.yaml` | 四个容器、端口、健康检查、数据卷 | Web 与 Worker 共用镜像，命令不同 |
| `Dockerfile` | Python 基础环境和依赖 | 所有服务为何能使用同一份代码 |
| `config/settings.py` | 数据库、Redis、Provider 配置 | 环境变量、Channel layers、Celery 参数 |
| `config/asgi.py` | HTTP 与 WebSocket 的统一入口 | `ProtocolTypeRouter` |
| `config/celery.py` | Celery 应用初始化 | Worker 如何加载 Django settings |
| `config/urls.py` | 页面/API 入口 | 各 app URL 如何汇总 |

## 操作步骤

### 1. 理解容器内部地址

Docker 为项目创建内部网络。`web` 和 `worker` 通过主机名 `db` 访问 PostgreSQL、通过 `redis` 访问 Redis；这个主机名只在 Docker 内部有效。Windows 浏览器访问的始终是 `localhost:8000`。

项目有三个命名卷：`postgres_data` 保存表和向量，`redis_data` 保存 Redis AOF，`media_data` 保存上传文件。Web 与 Worker 都挂载 `media_data:/app/media`，否则 Worker 找不到刚上传的原文件。

```powershell
docker volume ls
```

### 2. 为什么使用 ASGI

传统 WSGI 只能处理 HTTP；ASGI 同时支持 HTTP 与 WebSocket。Web 容器用 Daphne 启动：

```text
daphne -b 0.0.0.0 -p 8000 config.asgi:application
```

普通页面、表单和 REST API 仍由 Django HTTP 路由处理；`/ws/tasks/<uuid>/` 与 `/ws/conversations/<uuid>/` 由 Channels Consumer 处理。WebSocket 路由应写在 app 的 `routing.py`，而不是普通 `urls.py`。

### 3. Redis 为什么有两个编号

默认配置为：

```dotenv
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1
```

`0` 和 `1` 是同一 Redis 服务的逻辑库。0 用于 Channels 和任务 Broker，1 用于 Celery Result Backend。文档的业务状态不能只放在 Celery Backend；它还必须写入 PostgreSQL 的 `IngestionTask`，这样用户刷新页面后仍能看到进度和错误。

### 4. 看一次真实链路

1. 一个窗口运行 `docker compose logs -f web`。
2. 另一个窗口运行 `docker compose logs -f worker`。
3. 在浏览器上传一个 Markdown 文件。
4. Web 日志会出现请求；Worker 日志会出现 Celery 任务；页面会显示处理阶段。

如果页面显示“处理中”却没有 Worker 日志，任务没有被消费；如果 Worker 报供应商错误，优先检查 `.env` 和网络，而不是重启数据库。

## 编码任务

为 `CHAT_HISTORY_MESSAGE_LIMIT` 做完整配置接线：在 `.env.example` 说明默认值，在 `settings.py` 转成整数，在聊天任务中读取它，并写测试证明最多只带入这个数量的历史消息。修改环境变量后重启 Web 和 Worker：

```powershell
docker compose up -d --build web worker
```

## 验收清单

- [ ] 能解释四个容器的职责。
- [ ] 能解释 Web 与 Worker 为什么要共享媒体卷。
- [ ] 能说出 ASGI 相比 WSGI 多支持了什么。
- [ ] 能在 Worker 日志中找到一次文档任务。
- [ ] 知道业务任务状态保存在 PostgreSQL，不只看 Celery。

## 常见错误

| 错误做法 | 后果 | 正确方式 |
| --- | --- | --- |
| 在 View 中直接解析 PDF/调用模型 | 请求阻塞且容易超时 | 创建任务，事务提交后投递 Celery |
| 只给 Web 挂媒体卷 | Worker 无法读取上传文件 | Web、Worker 同时挂载 `media_data` |
| 把 Key 写入前端 | 所有用户可见 | 只写入 `.env`，后端 Provider 调用 |
| WebSocket 不通就重启所有容器 | 掩盖登录 Cookie、路由或权限问题 | 先看浏览器网络面板和 Consumer 日志 |

## 延伸阅读

继续阅读 [02-数据模型与迁移](02-数据模型与迁移.md)。
