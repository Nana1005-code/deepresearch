# 修改点 005：模拟数据、一致性审计和并发测试工具

- 新增 `scripts/research_square/seed.py`：生成可复现的 small、medium、large 模拟数据，所有标题带 `[模拟]`。
- 新增 `scripts/research_square/audit.py`：检查外键、互动缓存、图谱边和核心表数量。
- 新增 `scripts/research_square/load_test.py`：以线程池并发执行热榜、图谱、分页、详情和浏览写入，报告吞吐量与 P50/P95/P99。
- 工具只操作独立的 `research_square.sqlite3`，不会清理或修改原有 `research.sqlite3`。
- `seed.py --reset` 是显式操作，只重建研究广场模拟数据。
