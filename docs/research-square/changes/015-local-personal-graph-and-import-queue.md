# 015 本机个人研究图谱与后台导入队列

日期：2026-11-12

## 产品定位调整

- “研究广场”改为“我的研究图谱”。
- 不再提供多人公开、点赞、浏览量、收藏等社交界面。
- 用户研究图谱只展示本机用户主动导入的研究和明确标记的本地样例。
- 不需要租用服务器；SQLite、OpenAlex 元数据和个人研究记录均保存在本机。
- “公开”改为“导入到我的研究图谱”。

## 后台导入队列

新增 SQLite 表 `research_import_jobs`，状态包括：

- `queued`：等待处理；
- `processing`：DeepSeek 正在提取并归一关键词；
- `completed`：已写入个人图谱；
- `failed`：处理失败，可从原研究记录重新导入；
- `cancelled`：用户已经取消导入。

导入接口现在立即返回 HTTP 202，不再等待模型处理。后台只启动一个工作线程，
按创建时间逐条处理，最多允许 10 条等待任务。程序退出时仍在处理的任务会在
下次启动时自动恢复为 `queued`，避免永久卡死。

## 本机列表

- 每页 10 条，提供上一页、页码、下一页；
- 排序固定为“置顶优先，其次按导入时间倒序”；
- 新增置顶/取消置顶；
- 真实记录和样例记录都可以取消导入；
- 取消导入只从个人图谱移除，不删除原始研究历史；
- 移除热度角标、点赞、浏览量和收藏显示；
- 移除统计周期、研究领域和排序筛选框。

## 研究遗漏助手

个人图谱下的问答只保留一个用途：查找用户可能遗漏的相关研究主题。

1. 从问题中识别 OpenAlex 规范主题；短名称会扩展到相近的完整规范主题。
2. 根据同一真实论文中的主题共现计算学术关联。
3. 统计本机 `data_origin='user'` 研究对候选主题的覆盖次数；样例不计入个人覆盖。
4. 按“学术关联较强、个人覆盖较低”排序。
5. DeepSeek 只解释后端已经查出的结果；调用失败时返回确定性统计答案。

## 数据库变化

- `public_researches.is_pinned`
- `public_researches.pinned_at`
- `research_import_jobs`

迁移为增量迁移，不覆盖原研究数据库、OpenAlex 表或已经导入的记录。

## 主要修改文件

- `backend/src/main.py`
- `backend/src/research_square/import_queue.py`
- `backend/src/research_square/router.py`
- `backend/src/research_square/schemas.py`
- `backend/src/research_square/store.py`
- `frontend/src/App.vue`
- `frontend/src/features/research-square/ResearchSquarePage.vue`
- `frontend/src/features/research-square/CommunityTopicDetailPage.vue`
- `backend/tests/test_research_square.py`

## 验证

- 后端专项测试：17 项通过；
- 前端 TypeScript 检查与 Vite 生产构建通过；
- SQLite 一致性审计通过；
- 已验证“多模态”短主题可映射到 OpenAlex 规范主题“多模态机器学习应用”，并返回个人未覆盖的相关主题。
