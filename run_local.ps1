$ErrorActionPreference = "Stop"
$env:KNOWFLOW_LOCAL_DEMO = "true"
$env:DEBUG = "true"

Write-Host "启动 KnowFlow 本地演示模式（SQLite + 离线模型，无需 Docker 或 API Key）..."
& .\.venv\Scripts\python.exe manage.py migrate --noinput
& .\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
