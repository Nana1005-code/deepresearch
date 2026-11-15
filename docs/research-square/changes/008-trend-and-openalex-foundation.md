# 修改点 008：分段趋势与 OpenAlex 真实数据基础

涉及文件：

- `backend/src/research_square/store.py`：趋势分桶和环比；新增六张独立 `openalex_*` 数据表及索引。
- `backend/src/research_square/router.py`：趋势回答必须逐段列出热度、新增研究数和环比。
- `scripts/research_square/import_openalex.py`：带游标、重试、upsert、批次状态和成本记录的元数据导入器。
- `backend/.env.example`：增加可选 `OPENALEX_API_KEY`。
- `backend/tests/test_research_square.py`：验证 90 天三段趋势和真实表隔离。
- `scripts/research_square/audit.py`：显示 OpenAlex 作品、主题和映射数量。

隔离说明：OpenAlex 导入器不会写入 `public_researches`、模拟 `topics` 或原项目历史库。未来中文别名和跨领域补充分开保存来源、置信度和审核状态，不会覆盖 OpenAlex 原始分类。
