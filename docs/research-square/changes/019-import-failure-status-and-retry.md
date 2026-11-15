# 019 导入失败状态与重试

## 问题

研究记录在调用模型提取关键词前就会写入 `public_researches`。旧逻辑只要看到这条记录存在，就返回“已经导入”，即使 `extraction_status='failed'` 且没有任何 `research_topics`。结果是页面显示成功，但知识图谱没有节点，并且再次导入被拒绝。

## 修正

- 只有 `extraction_status='completed'` 且至少存在一个关键词关系时，才认定为“已导入”。
- 失败记录可以复用原导入任务重新排队，不新建重复研究记录。
- 新增 `GET /research-square/import-status/{source_run_id}`，返回 `not_imported`、`queued`、`processing`、`completed` 或 `failed`。
- 研究结果页按钮根据真实状态显示：
  - 导入到我的研究图谱；
  - 等待提取关键词；
  - 正在提取关键词；
  - 已导入；
  - 导入失败，请重试。
- “我的导入记录”对失败卡片显示红色提示，并提供“重新提取关键词”按钮。

## 验证

- 后端研究广场测试：22 项通过。
- 新增失败状态和重新排队回归测试。
- 前端 TypeScript 检查与 Vite 生产构建通过。

## 与团队项目集成原则

当前目录没有 `.git` 历史，不能安全地直接执行 `git pull`。后续应把团队仓库克隆到新目录，以团队仓库为主线建立功能分支，再迁移以下低耦合目录：

- `backend/src/research_square/`
- `frontend/src/features/research-square/`
- `scripts/research_square/`
- `docs/research-square/`
- `backend/tests/test_research_square.py`

只手工合并少量接入点：`backend/src/main.py`、`frontend/src/App.vue`、依赖清单和环境变量示例。不得直接用当前文件覆盖团队版本。
