# 018 按研究发起时间计算图谱近期活跃度

## 修改范围

- `backend/src/research_square/store.py`
- `backend/src/research_square/import_queue.py`
- `backend/tests/test_research_square.py`
- `frontend/src/features/research-square/TopicGraph.vue`
- `frontend/src/features/research-square/ResearchSquarePage.vue`
- `scripts/research_square/import_user_research_samples.py`
- `scripts/research_square/backfill_research_started_at.py`

## 时间字段

`public_researches` 新增 `research_started_at`：

- 真实导入记录取原始研究历史 `runs.data.created_at`。
- 模拟记录由样例脚本在最近 330 天内确定性错开。
- `published_at` 仍表示导入到“我的研究图谱”的时间，两者不混用。

数据库初始化会自动增加该字段和索引。已有数据可运行：

```powershell
.\backend\.venv\Scripts\python.exe scripts\research_square\backfill_research_started_at.py
```

## 近期活跃度

图谱统计窗口当前为 365 天。对每个节点：

```text
时间新鲜度 = 1 - 平均发起距今天数 / 364
近期活跃度 = 关联研究次数 × (0.25 + 0.75 × 时间新鲜度)
```

时间新鲜度限制在 0～1。该公式满足：

- 关联研究次数越多，活跃度越高；
- 关联研究的平均发起时间越晚，活跃度越高；
- 颜色只在当前显示的节点内归一化，最低值为灰色，最高值为红色。
- 节点大小仍只表示关联研究/论文数量，避免把时间新鲜度重复编码到大小中。

OpenAlex 图谱使用相同公式，但时间字段对应论文发表日期。

## 界面调整

节点悬浮框移除“较前一周期”和“领域”，只显示：

- 近期活跃度；
- 关联研究数或真实论文数；
- 平均发起/发表时间；
- 最近发起/发表时间。

## 本机数据回填结果

- 真实用户研究：3 条使用原始研究发起时间。
- 模拟研究：36 条错开到最近 330 天。
- 当前前 40 个节点活跃度范围：0.957～2.310。
- 当前节点平均发起时间范围：2026-04-22～2026-11-13。

## 验证

- 后端研究广场测试：21 项通过。
- 新增回归测试证明颜色指标使用研究发起时间，而不是导入时间。
- 前端 TypeScript 检查和 Vite 生产构建通过。
