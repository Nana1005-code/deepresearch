# 修改点 011：OpenAlex规范主题检索优先与DeepSeek别名归并

## 目标

解决“多个OpenAlex主题具有不同名称或别名，但实际表达同一研究主题”的重复节点问题，同时保留全部OpenAlex原始数据和可撤销审计记录。

## 数据结构

- `openalex_canonical_topics`：项目内部规范主题；原始OpenAlex主题不会写回或删除。
- `openalex_canonical_aliases`：规范主题别名；允许同一歧义别名对应不同规范主题。
- `openalex_topic_canonical_mappings`：OpenAlex主题到规范主题的多对一映射。
- `openalex_canonical_decisions`：每次保留、建议审核或自动归并的模型理由和置信度。
- `openalex_canonical_runs`：批处理进度、模型和token用量。

## 新数据流程

`enrich_openalex_ai.py` 在生成中文主题时会先检索现有规范主题与别名，并把候选交给DeepSeek。模型只能选择复用候选或新建；后端验证候选ID和置信度。中文名称或别名精确命中时直接复用，其余才创建新的规范主题。

## 存量归并

`merge_openalex_aliases_ai.py` 使用字符二元组筛选相近候选，再让DeepSeek判断 `merge`、`keep` 或 `review`。只有置信度不低于0.95的等价关系自动归并；相关、上下位和简称匹配均不归并。归并只移动本地映射并复制别名，不修改论文、OpenAlex主题或原始分类。

本次存量运行结果：4,244个OpenAlex主题形成4,219个初始规范主题；DeepSeek处理517个有效候选，自动归并46组，57组标记人工审核。最终活动规范主题4,173个，全部4,244个OpenAlex主题均保留映射。

## 页面查询

真实热门榜、论文主题标签、知识图谱和真实热点问答均改为读取规范主题。论文数量和主题共现会聚合所有等价OpenAlex主题，避免同义节点重复展示。
