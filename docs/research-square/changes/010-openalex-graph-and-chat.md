# 修改点 010：OpenAlex 真实图谱与问答入口

## 修改范围

- `backend/src/research_square/store.py`：增加真实主题识别、真实主题力导向图数据和受控问答查询。节点来自 `openalex_topics`，不会使用论文标题；边表示同一篇论文中两个主题的共现。
- `backend/src/research_square/router.py`：增加 `GET /research-square/openalex/graph`，并让 `/chat` 按 `data_source` 选择模拟表或 OpenAlex 表。
- `backend/src/research_square/schemas.py`：问答请求增加 `data_source=local|openalex`。
- `frontend/src/features/research-square/ResearchSquarePage.vue`：OpenAlex 模式展示与模拟模式同格式的 ECharts 图谱和独立问答入口。
- `frontend/src/features/research-square/TopicGraph.vue`：复用同一组件，并按数据源显示“热度/论文数”和“公开研究/真实论文”的正确含义。
- `backend/tests/test_research_square.py`：验证真实图谱节点不是论文标题、边来自主题共现、问答只查 OpenAlex 数据。

## 指标定义

- 节点：OpenAlex 标准主题；优先显示 AI 生成的中文规范名，同时保留英文原名。
- 节点大小：所选周期内映射到该主题的真实论文数。
- 节点颜色：相对前一个等长周期的论文数量增长率分位数。
- 边：同一篇真实论文的 OpenAlex 前三主题共同出现。
- 边粗细：Jaccard 关联度，即共同论文数除以两个主题论文集合的并集数量。
- 稀疏化：默认每个节点最多保留三条最强边，避免图谱退化为完全图。

## 隔离保证

本次查询只读取既有 `openalex_*` 独立表，不覆盖模拟数据表，不修改 OpenAlex 原始主题分类，也不影响原有深度研究流程。
