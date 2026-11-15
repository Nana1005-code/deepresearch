# 020 同学项目安全整合

## 安全基线

- 同学原目录 `D:\学期项目\Deepresearch-main` 未修改。
- 我方原目录 `D:\学期项目\deepresearch` 未修改。
- 新建独立目录 `D:\学期项目\Deepresearch-integrated`。
- 整合前已建立 Git 基线提交 `41a777f`，可逐文件审查和回退。

## 手工合并点

1. `backend/src/main.py`
   - 保留同学的本地资料库、Word 导出和报告质检 Router。
   - 新增独立的研究图谱 Store、Router 和后台导入队列。
   - 研究图谱继续使用独立 SQLite，不改写原研究历史数据库。
   - 增加 5175 作为第二个本地开发端口，便于并行测试另一份 checkout。
2. `frontend/src/App.vue`
   - 保留 `LocalDocumentPicker` 和研究请求中的 `document_ids`。
   - 新增“我的研究图谱”入口、研究完成后的导入按钮和导入状态。
   - 图谱页面采用异步加载，不增加主研究页面的首屏负担。
3. `frontend/package.json` 与 `frontend/package-lock.json`
   - 仅新增 ECharts 6 及其锁定依赖。
4. `backend/.env.example`
   - 保留同学项目的 `LLM_TEMPERATURE`。
   - 新增 `RESEARCH_SQUARE_DB_URL` 与可选 `OPENALEX_API_KEY`。
5. 新增目录
   - `backend/src/research_square/`
   - `frontend/src/features/research-square/`
   - `scripts/research_square/`
   - `backend/tests/test_research_square.py`

## 本地数据

原研究图谱数据库已复制到整合目录的 `backend/data/research_square.sqlite3`，用于本机验收；该目录受 `.gitignore` 保护，不会被提交到 GitHub。原始数据库未移动、未修改。

## 启动脚本修复

同学压缩包中的 `start-local.cmd` 引用了缺失的 `start-local.ps1`。整合目录补回该脚本，使用隐藏的本地子进程启动前后端，并与现有 `stop-local.ps1` 的运行状态文件格式保持一致。

## 测试口径

- 自动化测试验证模块级和 API 级行为。
- 真实模型、Tavily/OpenAlex 联网调用需要有效密钥与网络额度，不能用本地 mock 结果冒充线上验证。
- 浏览器视觉点击需在用户本机完成；当前 Codex 会话不允许浏览器访问 localhost。
