# DeepResearch 后端

后端使用 Python 3.11、FastAPI 和 SQLite。完整安装、模型与搜索 API 配置、启动方法和 OpenAlex 导入步骤见项目根目录 [README.md](../README.md)。

建议始终从项目根目录使用 `start-local.cmd` 启动，它会自动加载 `backend/.env`、设置 UTF-8 并连接正确的前端端口。需要单独启动后端时执行：

```powershell
.\backend\.venv\Scripts\python.exe -m uvicorn main:app `
  --app-dir .\backend\src `
  --env-file .\backend\.env `
  --host 127.0.0.1 `
  --port 8000
```

健康检查地址为 http://127.0.0.1:8000/healthz 。本地数据库、笔记、虚拟环境和 `.env` 均不应提交到 GitHub。
