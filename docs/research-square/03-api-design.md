# API 设计

所有新接口使用 `/research-square` 前缀，不占用原项目路径。

- `GET /domains`：领域列表。
- `GET /overview`：统计卡片与主题热榜，支持时间和领域筛选。
- `GET /researches`：公开研究搜索、排序和分页。
- `GET /researches/{id}`：公开研究详情。
- `POST /publish`：从已完成的本地研究创建或更新公开快照。
- `DELETE /researches/{id}/publication`：取消公开，不删除本地研究。
- `POST /researches/{id}/like|favorite|view|share`：幂等互动事件。
- `GET /graph`：全局或领域主题图谱。
- `POST /chat`：受控热点问答。
- `GET /openalex/graph`：OpenAlex 真实主题共现图，响应格式与模拟图谱一致。
- `GET /openalex/topics/{public_id}`：规范主题详情及本地已导入论文中引用量最高的前100篇。
- `POST /chat` 的 `data_source` 可取 `local` 或 `openalex`，两类数据严格分表查询。
- `POST /admin/rebuild`：本地开发时重建统计与图谱。

公开接口只访问独立研究广场数据库；`publish` 是唯一读取现有研究数据库的入口，并且只读取用户指定的已完成任务和最终报告。
