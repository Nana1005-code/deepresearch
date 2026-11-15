# 数据库设计摘要

研究广场使用独立 SQLite 数据库，并开启 WAL、外键和 busy timeout。实体使用整数内部主键提高关联效率，同时使用唯一 `public_id` 作为前端公开标识。

主要表：

- `users`：本地模拟用户和将来的真实用户映射。
- `domains`：研究领域树。
- `public_researches`：用户主动公开的研究快照。
- `topics`、`topic_aliases`：规范主题和别名。
- `topic_domains`：主题与领域的多对多关系。
- `research_topics`：公开研究与主题的多对多关系。
- `research_events`：幂等的浏览、点赞、收藏和分享事件。
- `research_likes`、`research_favorites`：以复合主键防止重复操作。
- `topic_daily_stats`：图表和热榜使用的每日汇总。
- `topic_edges`：由主题共现计算的知识图谱边。
- `hotspot_chat_*`：热点问答会话扩展预留。
- `openalex_works`：真实学术作品元数据，与用户公开研究、模拟研究完全分离。
- `openalex_topics`、`openalex_work_topics`：OpenAlex 主题体系及作品的前三个主题概率。
- `openalex_topic_aliases`、`openalex_topic_domains`：未来 AI 生成的中文别名、跨领域补充、置信度和审核状态。
- `openalex_import_runs`：批量导入进度、游标、状态和 OpenAlex 返回的成本记录。
- `openalex_topic_enrichments`：主题中文规范名、说明、模型、提示词版本和审核状态。
- `openalex_work_topic_reviews`：低置信度论文的 AI 候选复核建议；不修改 OpenAlex 原始主主题。
- `openalex_ai_runs`：批量任务进度、模型、token 用量和错误记录。
- `openalex_canonical_topics`、`openalex_canonical_aliases`：不改动OpenAlex原始数据的项目规范主题与可歧义别名。
- `openalex_topic_canonical_mappings`：多个OpenAlex主题映射到一个规范主题。
- `openalex_canonical_decisions`、`openalex_canonical_runs`：DeepSeek归并决策、理由、置信度、进度和token审计。

知识图谱边统一要求 `source_topic_id < target_topic_id`，避免同一无向关系存两次。关系强度使用 Jaccard：共同研究数除以两主题研究集合的并集数量，降低泛化大主题对图谱的垄断。

主题名称在 `topics` 中全局唯一。`topic_aliases` 和 `topic_domains` 都保存 `source`、`confidence` 与 `review_status`，用于区分用户输入、模拟规则和未来 AI 分类结果。发布研究时若输入命中已有别名，会复用规范主题，不会建立第二个节点。

模拟器先创建全局主题目录，再建立带权重的多领域关系。当前中型数据包含明确的跨领域主题、中文/英文/缩写别名，以及上升、稳定、降温三类生命周期；研究标题和主题名称不再追加展示用数字。

真实 OpenAlex 表不会写入或覆盖 `public_researches`、`topics` 和模拟数据。等真实数据页面完成后，通过数据源筛选分别展示用户公开、OpenAlex 与模拟数据。
