# 修改点 013：清除模拟研究数据

## 执行结果

- 删除 `source_run_id=seed-*` 或标题以 `[模拟]` 开头的模拟公开研究30,000条。
- 通过外键级联删除对应主题关系、事件、点赞和收藏；模拟事件共300,057条。
- 删除无引用的 `sim-user-*` 与 `load-user-*` 用户2,050个。
- 删除 `source=seed` 的别名和领域关系，并删除没有任何真实研究引用的社区主题。
- 保留真正用户公开的“多模态”研究1条及其主题。
- 保留全部30,000条OpenAlex真实论文及全部 `openalex_*` 数据。

## 恢复与重复执行

清理前备份：`backend/data/backups/research_square-before-clear-synthetic-20261112-161216.sqlite3`。

清理脚本为 `scripts/research_square/clear_synthetic.py`，按显式生成器标记定位数据，必须传入 `--yes` 才执行。脚本可重复运行；不存在模拟数据时不会影响用户公开研究或OpenAlex数据。

```powershell
.\backend\.venv\Scripts\python.exe scripts\research_square\clear_synthetic.py --yes
```
