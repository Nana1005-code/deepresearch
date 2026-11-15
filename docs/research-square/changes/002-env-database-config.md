# 修改点 002：研究广场数据库配置

- 修改文件：`backend/.env.example`
- 新增配置：`RESEARCH_SQUARE_DB_URL=sqlite:///./data/research_square.sqlite3`
- 原因：允许本地 SQLite 和未来 MySQL 使用相同配置入口。
- 对现有功能影响：没有。现有 `RESEARCH_DB_PATH` 和研究历史数据库保持不变。
- 安全：这里只提交示例地址，不提交数据库文件、密码或真实 `.env`。
