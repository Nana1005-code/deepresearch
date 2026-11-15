# 023 启动时加载 backend/.env

## 问题

README 要求把 Tavily 等配置写入 `backend/.env`，但原启动命令没有调用 `load_dotenv()`，也没有向 Uvicorn 传入 `--env-file`。因此配置文件存在时，后端仍可能回退到 `duckduckgo` 和默认 Ollama。

## 修复

- `start-local.ps1` 检测 `backend/.env` 是否存在。
- 存在时向 Uvicorn 追加 `--env-file <absolute path>`。
- 系统环境变量仍拥有更高优先级；没有 `.env` 时保持原有默认行为。

## Tavily 值格式

本项目的 `TAVILY_API_KEY` 必须是原始 `tvly-...` Key，不能填写 `https://mcp.tavily.com/mcp/?tavilyApiKey=...` 形式的 MCP URL。
