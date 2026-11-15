# 016 重复导入拦截、节点记录与历史跳转

日期：2026-11-13

## 修正内容

### 重复导入

- 入队前同时检查 `research_import_jobs` 和已经存在的 `public_researches`。
- 已完成导入：返回 HTTP 409，提示“该研究已经导入到我的研究图谱，无需重复导入”。
- 正在处理或等待：返回 HTTP 409，提示“该研究正在后台导入，请勿重复操作”。
- 旧版本中导入、尚未创建队列任务的研究也能被识别，不会重新调用 DeepSeek。

### 节点相关记录

- 用户图谱节点详情继续通过 `research_topics` 精确查询关联的导入记录。
- 节点详情返回 `source_run_id`、题目、完整研究输入、来源类型和导入时间。
- 空状态文案改为“没有关联的导入记录”。
- 实际数据库验证：当前显示的 40 个用户图谱节点均能返回至少一条关联记录。

### 跳转研究历史

- “我的导入记录”中的真实研究题目可以点击。
- 节点详情中的真实研究题目也可以点击。
- 点击后使用已有 `#research/{source_run_id}` 路由打开对应历史记录。
- 没有修改研究运行、新研究创建或历史记录读取流程。
- 样例数据没有真实 `research-runs` 记录，因此保持普通文本，不提供错误跳转。

## 修改文件

- `backend/src/research_square/store.py`
- `backend/src/research_square/router.py`
- `frontend/src/features/research-square/ResearchSquarePage.vue`
- `frontend/src/features/research-square/CommunityTopicDetailPage.vue`
- `backend/tests/test_research_square.py`

## 验证

- 后端专项测试：19 项通过；
- 前端 TypeScript 检查与 Vite 生产构建通过；
- 当前 3 条真实导入记录均带有效 `source_run_id`；
- 当前用户图谱 40/40 个展示节点均能查询到关联导入记录。

## 2026-11-13 点击事件补充修复

图谱初次挂载时数据尚未返回，旧实现只在 `onMounted` 阶段绑定一次 ECharts
点击监听；此时图表实例不存在，因此后续虽然能绘图和显示悬停提示，却没有点击事件。
现改为在 `render()` 真正创建图表实例时绑定一次监听，并在销毁时重置绑定状态。

已在 Edge 中实际验证：

1. 点击“多模态”节点进入详情页；
2. 详情显示 4 条关联记录；
3. 点击其中真实研究，成功打开对应 `#research/{source_run_id}` 历史报告。
