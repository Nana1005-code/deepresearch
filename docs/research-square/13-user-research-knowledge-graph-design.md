# 用户复杂研究问题知识图谱设计

## 核心原则

不能把整句长问题直接当成一个不可拆分的主题。采用“双层图”：

1. **研究节点**：用户公开的一次研究问题或研究成果，保留原文、摘要、作者、状态和证据。
2. **概念节点**：可复用的原子概念，包括领域、任务、方法、模态、数据、对象、指标、约束和场景。

界面可显示完整双层图，也可隐藏研究节点，把经同一研究连接的概念投影成概念关系图。

## 概念类型

| 类型 | 示例 |
|---|---|
| domain | 多模态学习、精神医学 |
| task | 多视图表示学习、抑郁症检测 |
| method | 因果不变学习、图神经网络 |
| modality | 语音、文本、图像、脑电 |
| object | 被试、患者、社交交互 |
| dataset | DAIC-WOZ、公开语音语料 |
| metric | F1、AUC、跨域泛化误差 |
| constraint | 小样本、跨中心、隐私、缺失模态 |
| population | 青少年、老年人、特定语言人群 |
| application | 临床筛查、辅助诊断 |

## 关系类型

- `HAS_TASK`：研究要解决的任务。
- `USES_METHOD`：采用或计划采用的方法。
- `USES_MODALITY`：使用的数据模态。
- `APPLIES_TO`：方法应用于任务或对象。
- `COMBINES_WITH`：方法组合。
- `EVALUATED_ON`：使用的数据集或场景。
- `EVALUATED_BY`：评价指标。
- `HAS_CONSTRAINT`：研究约束。
- `BELONGS_TO`：概念所属规范领域。
- `EQUIVALENT_TO`、`BROADER_THAN`、`NARROWER_THAN`、`RELATED_TO`：规范化关系。
- `SUPPORTED_BY`：用户研究与OpenAlex论文之间的证据关系。

每条关系必须保存 `stance`：`question`、`proposal`、`hypothesis`、`finding`。例如“因果不变是否可以配合图神经网络”只能保存为待验证的 `proposal`，不能当作已有研究结论。

## 抽取流程

1. 保存用户问题原文，不做覆盖。
2. DeepSeek按JSON Schema抽取概念、类型、关系、语气和原文证据片段。
3. 先在规范概念名、别名和OpenAlex规范主题中检索候选。
4. DeepSeek只能选择复用候选或提出新概念；后端验证ID、类型和置信度。
5. 高置信度等价概念复用节点；低置信度进入审核，不直接合并。
6. 写入研究节点、概念节点、研究—概念边及概念—概念边。
7. 查询OpenAlex主题及论文，为研究节点增加真实论文证据。
8. 聚合公开研究后生成社区概念图、研究图和学术—社区对照图。

## 示例一：多视图学习在多模态领域的应用

仅从这句话可确定：`多视图学习(method)`、`多模态学习(domain)`。`跨模态表示`、`特征融合`或`缺失模态`只有在摘要或报告明确提到时才能增加，不能由模型自行补全。

关系：

- 研究 `USES_METHOD` 多视图学习。
- 多视图学习 `APPLIES_TO` 多模态学习，`stance=question/proposal`。

## 示例二：抑郁症语音检测里因果不变是否可以配合图神经网络

概念：`抑郁症检测(task)`、`语音(modality)`、`因果不变学习(method)`、`图神经网络(method)`。`跨域泛化`和`说话人关系`只有在用户摘要或报告出现时再抽取。

关系：

- 研究 `HAS_TASK` 抑郁症检测。
- 研究 `USES_MODALITY` 语音。
- 因果不变学习 `COMBINES_WITH` 图神经网络，`stance=proposal`。
- 组合方法 `APPLIES_TO` 抑郁症检测，`stance=hypothesis`。

## 边权计算

概念投影图中，不应只按共同出现次数连边。建议：

```text
community_weight =
  0.40 × 加权共同研究数
  + 0.20 × 独立研究者数
  + 0.15 × 最近90天增长
  + 0.15 × 用户互动热度
  + 0.10 × AI抽取平均置信度
```

OpenAlex学术边继续使用论文共现Jaccard：

```text
academic_relation = 共同论文数 / (主题A论文数 + 主题B论文数 - 共同论文数)
```

融合视图可同时显示两类边，或计算：

```text
combined_weight = 0.6 × academic_relation + 0.4 × normalized_community_weight
```

边的悬浮详情必须展示共同论文、共同用户研究、独立研究者、关系语气和代表性证据，不能只显示一个难以解释的分数。

## 推荐数据表

- `research_concepts`：规范原子概念。
- `research_concept_aliases`：概念别名。
- `public_research_concepts`：公开研究与概念的关系、权重、证据和置信度。
- `research_concept_relations`：概念关系、语气、方向、证据和审核状态。
- `research_openalex_evidence`：用户研究与真实论文的匹配及理由。
- `concept_resolution_decisions`：复用、新建、合并和人工审核记录。

这套表应与现有 `openalex_canonical_topics` 映射，而不是复制或破坏OpenAlex原始主题。
