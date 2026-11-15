# 修改点 006：ECharts 图谱与模拟主题模型

涉及文件：

- `frontend/package.json`、`frontend/package-lock.json`：增加 ECharts。
- `frontend/src/features/research-square/TopicGraph.vue`：新增独立交互图谱组件。
- `frontend/src/features/research-square/ResearchSquarePage.vue`：用新组件替换静态 SVG。
- `frontend/src/App.vue`：动态加载研究广场，隔离 ECharts 对原首页包体的影响。
- `backend/src/research_square/store.py`、`router.py`：增加趋势指标、领域列表与每节点边数限制。
- `scripts/research_square/seed.py`：全局主题、多领域、别名、生命周期和可读标题。
- `scripts/research_square/audit.py`：增加主题重复、主领域、别名和跨领域审计。
- `backend/tests/test_research_square.py`：增加别名归一、跨领域与稀疏图测试。

隔离说明：未修改原研究执行、报告生成、搜索、笔记或历史数据库。新增字段只存在于独立的研究广场 SQLite 数据库中。
