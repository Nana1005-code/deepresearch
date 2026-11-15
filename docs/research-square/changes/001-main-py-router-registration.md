# 修改点 001：后端路由注册

- 修改文件：`backend/src/main.py`
- 修改内容：创建独立 `ResearchSquareStore`，并注册 `/research-square` 路由。
- 原因：FastAPI 不会自动发现新模块，必须在应用入口显式启用。
- 对现有功能影响：不修改原 `Store`、`ResearchJobs` 或已有路由；新模块使用另一数据库文件。
- 撤销方式：删除新增的两个 import、`app.state.research_square` 和 `include_router` 两行。
- 验证：完整运行原有后端测试和新增研究广场测试。
