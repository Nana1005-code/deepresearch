# 修改点 009：OpenAlex AI 增强与真实数据页面

涉及文件：

- `backend/src/research_square/store.py`：新增 AI 增强、低置信度复核、批次记录表；增加真实数据概览、论文列表和分类进度查询。
- `backend/src/research_square/router.py`：新增 `/openalex/overview`、`/openalex/works`、`/openalex/enrichment-status`。
- `scripts/research_square/enrich_openalex_ai.py`：可恢复的主题批量翻译、多领域增强和低置信度论文复核。
- `frontend/src/features/research-square/ResearchSquarePage.vue`：增加本地/OpenAlex 数据源切换、真实论文列表和 AI 分类进度。
- `backend/tests/test_research_square.py`：验证真实表与模拟表隔离，以及多主题映射不会重复计算论文数。

安全边界：模型看不到数据库连接；论文只能从 OpenAlex 自己的前三个候选主题中复核；AI 结果不会覆盖 OpenAlex 原始分类。真实图谱本次不生成。
