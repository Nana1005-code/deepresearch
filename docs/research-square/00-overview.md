# 研究广场总体设计

研究广场是独立于现有研究执行流程的可选模块。它只读取已经结束的本地研究，在用户主动确认后保存一份公开快照。

## 隔离边界

- 原有数据库：`backend/data/research.sqlite3`，不改变表结构和读写逻辑。
- 新数据库：`backend/data/research_square.sqlite3`，保存公开研究、主题、互动、统计和图谱关系。
- 默认私有。只有调用“公开”接口后才会复制经过选择的数据。
- 模型密钥、本地路径、私人对话、运行事件和错误日志不会进入研究广场。

## 模块位置

- 后端：`backend/src/research_square/`
- 前端：`frontend/src/features/research-square/`
- 模拟数据：`scripts/research_square/`
- 测试：`backend/tests/test_research_square.py`
- 修改说明：`docs/research-square/changes/`
