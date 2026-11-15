# 修改点 012：大尺寸图谱与主题高引论文详情页

## 修改范围

- `frontend/src/features/research-square/TopicGraph.vue`：桌面端图谱高度由430px提升到680px，节点点击事件返回完整节点对象。
- `frontend/src/features/research-square/ResearchSquarePage.vue`：图谱改为独占整行宽度；真实图谱节点进入独立详情视图，模拟图谱仍带入热点问答。
- `frontend/src/features/research-square/TopicDetailPage.vue`：新增规范主题详情、领域、别名、聚合统计及引用量前100论文列表。
- `backend/src/research_square/store.py`：新增规范主题详情查询，按映射聚合等价OpenAlex主题、去重论文并按引用量降序。
- `backend/src/research_square/router.py`：新增 `GET /research-square/openalex/topics/{public_id}?limit=100`。
- `backend/tests/test_research_square.py`：验证最多100篇、引用量降序和论文去重。

## 数据口径

详情页只显示当前本地已导入的OpenAlex论文。引用量取 `openalex_works.cited_by_count`；同一论文即使命中多个已归并OpenAlex主题也只显示一次。页面不会下载或保存论文全文。
