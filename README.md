# KnowFlow

基于 Django 的企业 AI 知识库与智能工作流平台。它将 PDF、DOCX、Markdown 异步解析为向量块，通过 DeepSeek 生成带来源引用的答案，并记录任务状态、重试、会话和 Token 用量。

## 一分钟启动

1. 安装 Docker Desktop，并启用 WSL2 后端。
2. 将 .env.example 复制为 .env，至少填写 DEEPSEEK_API_KEY 与 SILICONFLOW_API_KEY。
3. 运行 docker compose up --build。
4. 打开 http://localhost:8000/accounts/signup/ 注册首个账号。

服务包括 Django/Channels、Celery Worker、PostgreSQL + pgvector 和 Redis。首次启动会自动执行迁移与静态文件收集。

## 没有 Docker：本地演示模式

本地演示模式用于学习界面和完整业务流程，不需要 Docker、PostgreSQL、Redis 或模型 API Key。它使用 SQLite、同步任务、内存 WebSocket 通道、离线向量及模拟回答；因此不应用于生产，也不能衡量真实 RAG 质量。

在 PowerShell 中运行：

    .\run_local.ps1

首次启动会创建 `local-demo.sqlite3`。看到 `Starting development server` 后，打开 http://127.0.0.1:8000/accounts/signup/ 注册账号。要清空演示数据，停止服务后删除 `local-demo.sqlite3` 和 `media` 目录。

## 首版能力

- 个人组织空间与知识库访问范围
- PDF、DOCX、Markdown 上传；扫描件 PDF 显示可操作的失败原因
- Celery 异步解析、切片、批量 Embedding、HNSW 向量索引、自动重试
- WebSocket 任务进度与流式回答
- 带资料引用的 RAG 问答、聊天记录、模型 Token 用量
- 线性工作流：输入、检索、提示词、LLM 节点
- Django Admin、REST API 与 OpenAPI：/api/docs/

## 重要环境变量

| 变量 | 用途 |
| --- | --- |
| DEEPSEEK_API_KEY | 回答和工作流 LLM |
| SILICONFLOW_API_KEY | BAAI/bge-m3 向量化 |
| SECRET_KEY | Django 会话与 CSRF 安全密钥 |
| MAX_UPLOAD_BYTES | 默认 20 MB 的单文件上限 |

密钥只放在本地 .env；该文件已被 Git 忽略。

## 测试与质量检查

容器启动后可运行：

    docker compose exec web pytest
    docker compose exec web ruff check .

完整的开发与学习路径见 docs/README.md。界面设计基准见 docs/assets/knowflow-dashboard-concept.png。
