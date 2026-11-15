# 修改点 007：受控热点问答与示例问题

涉及文件：

- `backend/src/research_square/store.py`：增加规范主题/别名的自由文本匹配；主题类查询缺少实体时返回明确错误。
- `backend/src/research_square/router.py`：增加六类 few-shot 示例、确定性计划修复和匹配主题审计字段。
- `frontend/src/features/research-square/ResearchSquarePage.vue`：显示六类示例问题，点击后填入输入框。
- `backend/tests/test_research_square.py`：覆盖无引号主题识别、模型漏参修复和禁止错误热榜降级。

模型仍使用主界面当前选中的模型配置，但只负责生成 JSON 查询计划和根据统计结果组织语言。模型不接触数据库连接，也不能直接生成或执行任意 SQL。
