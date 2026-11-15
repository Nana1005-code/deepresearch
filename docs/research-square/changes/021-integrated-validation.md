# 021 整合版验证记录

验证日期：2026-11-13

## 自动化测试

- `scripts/test_import_history.py`：3 项通过。
- 后端全量 `unittest`：189 项通过。
- 研究图谱定向回归：22 项通过。
- 前端 `npm run build`：Vue TypeScript 检查通过，Vite 生产构建通过，680 个模块完成转换。
- `git diff --check`：没有空白错误。

## 真实服务冒烟测试

使用整合目录的 `start-local.ps1`，以测试端口 8011/5175 完成启动、访问和停止闭环：

- 前端首页返回 HTTP 200，包含 Vue 挂载节点。
- `/healthz` 返回 `ok`。
- 本地资料 TXT 上传返回 201，可列表查询、下载，并成功删除测试记录。
- Word 导出返回 200、正确 DOCX MIME 类型，文件头为 ZIP/DOCX 签名 `50-4B-03-04`。
- 研究图谱概览、个人图谱、OpenAlex 概览与图谱接口均返回 200。
- CORS 对第二本地开发端口 5175 返回正确允许源。
- `stop-local.ps1` 能停止前后端；CIM 不可用时使用已校验 PID 的进程树回退方案。

## 本地数据验收

- OpenAlex 论文：20,000 条。
- OpenAlex 规范主题：4,071 个。
- 本地导入研究：38 条。
- 个人图谱默认返回 35 个节点。
- OpenAlex 图谱默认返回 40 个节点。

数据库文件位于 `backend/data/`，受 `.gitignore` 保护，不进入版本控制。

## 未宣称通过的范围

- 当前 Codex 浏览器不允许访问 localhost，因此没有完成视觉点击截图验收。
- 真实 DeepSeek/Tavily 研究流程依赖用户的有效 API Key、额度和外部网络，本次没有用 mock 结果冒充真实调用成功。
- `npm ci` 报告 14 个依赖漏洞（2 moderate、12 high）；未自动执行可能引入破坏性升级的 `npm audit fix`。
