# 01：Docker 与 Django 原理

## 概念

Django 负责 HTTP、会话、模板、管理后台和 ORM；ASGI/Channels 增加 WebSocket；Celery 使用独立进程处理耗时工作。

## 本阶段目标

理解一次上传请求不会直接解析文件：请求只创建任务，Worker 才执行提取、切片和向量化。

## 操作步骤

阅读 Dockerfile、config/settings.py、config/asgi.py 和 config/celery.py，画出浏览器到 Redis、Worker、PostgreSQL 的数据流。

## 编码任务

为一个新的环境变量增加 .env.example、settings.py 读取逻辑和文档说明。

## 验收清单

- 能说明 ASGI 与 WSGI 的差异
- 能解释 Redis 同时承担 broker 和 Channels layer 的原因

## 常见错误

不要把 API Key 写进模板、JavaScript 或镜像；只能通过 .env 注入后端进程。

## 延伸阅读

阅读 Django settings 和 Celery with Django 文档。

