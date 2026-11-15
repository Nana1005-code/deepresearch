# 修改点 004：独立研究广场前端

- 新增文件：`frontend/src/features/research-square/ResearchSquarePage.vue`
- 不修改现有组件内部行为。
- 页面包含统计卡片、热度柱形图、ECharts 力导向主题图、公开研究列表和热点问答。
- 新增 `frontend/src/features/research-square/TopicGraph.vue`，并增加 `echarts` 依赖。
- 研究广场页面在 `App.vue` 中改为动态导入；未进入研究广场时不会加载 ECharts 代码。
- 图谱支持拖动节点、缩放、平移、邻接高亮和重置视图。
- 图谱点击节点会生成相关主题问题；AI 查询计划在页面中可展开审计。
