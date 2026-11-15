# 014 用户研究关键词图谱与匿名公开简化

日期：2026-11-12

## 本次目标

- 图谱入口只保留“真实学术图谱”和“用户研究图谱”，不提供融合图谱。
- 用户只公开最初输入的完整研究题目，始终匿名；不再填写标签、领域、报告公开范围。
- DeepSeek 从完整输入提取 3～8 个规范关键词；同一输入中的关键词形成共现边。
- 点击用户图谱节点进入详情页，查看与该关键词相关的最新完整匿名研究输入。
- 导入可识别、可单独清理的本地样例库，不伪装成真实用户。

## 数据存储

样例和真实公开都存于 `backend/data/research_square.sqlite3`，但使用
`public_researches.data_origin` 区分：

- `user`：真实用户点击公开的输入；
- `sample`：本地功能验证样例。

新增/扩展字段：

- `public_researches.research_input`：完整原始输入；
- `data_origin`：真实公开或样例；
- `extraction_status/extraction_error`：AI 提取状态；
- `topics.concept_type`：领域、任务、方法、模态、对象、模型等；
- `research_topics.confidence/evidence_text`：归属置信度和原句证据；
- `topic_openalex_mappings`：用户关键词复用 OpenAlex 规范主题时的可追踪映射。

原有研究运行库、OpenAlex 论文表、报告和搜索流程没有被覆盖。

## 数据流

1. 用户点击“匿名公开研究题目”。
2. 后端只保存 `run.topic` 原始完整输入，不公开报告。
3. 从用户关键词库与 OpenAlex 规范主题/别名库检索最多 30 个候选。
4. DeepSeek 在候选中判断复用，或创建新关键词，最多返回 8 个概念。
5. 后端校验模型结果并写入 `topics`、`topic_aliases`、`research_topics`。
6. `rebuild_analytics()` 对同一研究输入的所有关键词两两计数，计算 Jaccard 关联强度并更新图谱。
7. 页面刷新后立即显示新节点/边；点击节点调用 `/research-square/community/topics/{public_id}` 读取完整输入。

## 样例库

已导入 36 条复杂样例输入，全部匿名且带“样例数据”标识。重新导入：

```powershell
Set-Location -LiteralPath "D:\学期项目\deepresearch"
$env:PYTHONIOENCODING='utf-8'
.\backend\.venv\Scripts\python.exe -u scripts\research_square\import_user_research_samples.py `
  --model-profile-id da5b90c911874a0eac425e8759632354 --reset
```

`--reset` 只删除 `data_origin='sample'`，不会删除真实用户公开记录或 OpenAlex 数据。

## 修改文件

- `backend/src/research_square/community_extractor.py`
- `backend/src/research_square/router.py`
- `backend/src/research_square/schemas.py`
- `backend/src/research_square/store.py`
- `frontend/src/App.vue`
- `frontend/src/features/research-square/ResearchSquarePage.vue`
- `frontend/src/features/research-square/CommunityTopicDetailPage.vue`
- `scripts/research_square/import_user_research_samples.py`
- `backend/tests/test_research_square.py`

## 验证结果

- 样例导入：36/36 成功，0 失败；
- 当前公开记录：真实用户 1，样例 36；
- 用户关键词节点：204；共现边：617；
- 数据一致性审计：`ok=True`，0 个问题；
- 后端专项测试：15 项通过；
- 前端 `vue-tsc` 与 Vite 生产构建通过。
