# DeepResearch 深度研究助手 — 完整数据交付版

本目录包含当前项目代码、研究历史、报告、笔记、对话、上传的原始文献和完整知识图谱数据库。模型与搜索 API 密钥已清空，接收者填写自己的密钥即可继续使用。数据库已直接放在程序默认位置，**不要再导入示例数据、重新初始化数据库或运行清空图谱的脚本**。

## 1. 交付内容

| 内容 | 位置 | 本次快照 |
| --- | --- | --- |
| 研究记录、任务事件、模型配置、文献索引、笔记、对话和阅读标记 | `backend/data/research.sqlite3` | 6 条研究记录，345 条任务事件，4 个模型配置（密钥为空），2 份上传文献，18 条阅读/笔记/对话对象 |
| 研究图谱、OpenAlex 数据及两个图谱助手的历史 | `backend/data/research_square.sqlite3` | 44 条研究图谱记录，31,141 篇 OpenAlex 论文，4,244 个原始学术主题，4,219 个规范化主题，49 个补充学术概念 |
| 上传的原始文件 | `backend/data/library_files/` | 与文献索引配套，保留原文件字节 |
| 研究过程产生的 Markdown 笔记 | `backend/notes/` | 原目录完整保留 |
| 早期共享历史与笔记 | `shared-data/` | 完整保留，无需重复导入 |
| 早期数据库备份 | `backend/data/backups/` | 保留并清理密钥 |
| 运行记录、截图、验收资料、旧数据库快照 | `archive/runtime/` | 原 `.runtime` 内容归档，避免旧进程编号影响新电脑启动 |
| 原项目文档及变更记录 | `docs/`、各模块 README、`archive/README-original.md` | 保留供查阅；**安装启动以本 README 为准** |
| 数据数量与打包记录 | `PACKAGING_REPORT.json` | 每个数据库的表记录数与脱敏统计 |

模型密钥不仅从 `.env` 清空，也从数据库内的模型配置和旧快照中清除。数据库已执行清理与重建，避免已删除密钥残留在空闲页中。模型名称、接口地址、模型 ID、研究内容和历史关系保持保留。

不附带 `.git`、Python 虚拟环境、`node_modules` 和缓存目录：这些不是业务数据，且不能可靠地在另一台电脑复用。依赖通过下面的安装步骤恢复。浏览器本地的面板宽度、当前选中会话等显示偏好不属于项目数据库；新电脑使用默认显示设置，历史会话本身保存在数据库中。

## 2. 运行环境

本交付包提供 Windows 10/11 的启动与安装脚本，使用 Vue + Vite 前端、FastAPI 后端和 SQLite 数据库，无需安装 MySQL、PostgreSQL 或 Neo4j。

- Python **3.11（64 位）**，安装时选择加入 PATH。
- Node.js **22 或更新的兼容版本**，需包含 npm。
- Windows 自带 Windows PowerShell 5.1，或 PowerShell 7。
- 首次安装需要联网下载依赖；联网研究和模型回答也需要网络及相应 API 服务。
- 直接接收本文件夹即可，**不要求安装 Git，也无需重新克隆仓库**。

安装后重新打开 PowerShell，检查：

```powershell
python --version
node --version
npm.cmd --version
```

## 3. 放置完整文件夹

将整个 `final_upload` 放在可读写的本地目录，例如 `D:\Projects\final_upload`。如果收到 ZIP，先完整解压，不要从压缩包内直接运行。

在包含 `start-local.cmd`、`backend` 和 `frontend` 的目录打开 PowerShell。以下示例路径需换成你的实际路径：

```powershell
Set-Location -LiteralPath 'D:\Projects\final_upload'
```

不要只复制源码目录：两个数据库、`library_files` 和 `notes` 都需要随项目一起保留。启动脚本会根据当前目录修复导入文献与研究笔记的路径，因此换盘或换电脑后仍可访问原文件。

## 4. 首次安装依赖

### 推荐：使用安装脚本

```powershell
.\setup-local.cmd
```

脚本会创建本机的 `backend/.venv`，按 `backend/requirements.local.txt` 安装 Python 依赖，按前端锁文件运行 `npm ci`，检查已有文献路径。它不会清空或重新导入历史数据。

如果电脑上有多个 Python，明确指定 Python 3.11：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\setup-local.ps1 -PythonExe 'C:\你的Python安装目录\python.exe'
```

### 手动安装（与脚本二选一）

```powershell
python -m venv backend\.venv
.\backend\.venv\Scripts\python.exe -m pip install --upgrade pip
.\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.local.txt
.\backend\.venv\Scripts\python.exe -m pip check
npm.cmd --prefix frontend ci
.\backend\.venv\Scripts\python.exe scripts\prepare-data.py
```

始终在本机创建虚拟环境，不要复制原作者电脑的 `.venv`。运行程序不需要激活虚拟环境，启动脚本会直接使用其中的 Python。

## 5. 填写自己的 API

### 5.1 模型 API：启动后在页面修改

本次保留了原来的模型配置，但所有密钥均为空。先按下一节启动程序，再在首页右侧“模型配置”中操作：

1. 选择要使用的配置，点击“修改”，或点击“新增”创建自己的配置。
2. 填写供应商提供的 **API 地址、模型 ID、API Key**。地址和密钥必须属于同一个服务商；模型 ID 必须是该服务实际支持的名称。
3. 点击“保存配置”，再点击“测试连接”。
4. 在新研究和问答助手中选择这个已通过测试的配置。

保留的旧服务地址和模型名称只是原配置，不保证你的账号可以访问。历史中的“功能测试”等配置不必使用，也不必为了查看历史而删除。

**注意：已有模型配置存放在数据库中，仅修改 `backend/.env` 的 `LLM_API_KEY` 不会覆盖这些配置。对于本交付包，优先通过页面保存自己的模型配置。**

### 5.2 联网搜索：填写 Tavily Key

打开 `backend/.env`，将下面的空值替换为自己的 Tavily API Key：

```dotenv
SEARCH_API=tavily
TAVILY_API_KEY=填写自己的Tavily_API_Key
```

这里需要 Tavily 原始 Key，不是 MCP 链接，也不是模型平台的 Key。当前配置不自动切换搜索引擎；缺少 Tavily Key 时，联网研究无法完成，但仍可浏览已有数据，或配置模型后使用不依赖联网搜索的功能。

修改 `.env` 后需停止并重新启动后端才能生效。

### 5.3 OpenAlex Key：仅新增数据时需要考虑

本包已包含 OpenAlex 数据，因此浏览现有论文和图谱不需要重新导入。若要继续从 OpenAlex 拉取数据，可在 `backend/.env` 配置自己的：

```dotenv
OPENALEX_API_KEY=填写自己的OpenAlex_API_Key
```

OpenAlex 数据导入规则与配额以自己的服务账户为准。执行额外导入前先备份 `backend/data`，相关脚本位于 `scripts/research_square/`。

### 5.4 配置文件说明

`backend/.env` 和 `frontend/.env.local` 已附带可运行的本地配置，密钥留空。若文件被误删，可从各自的 `.env.example` 复制回来。`LLM_BASE_URL`、`LLM_MODEL_ID`、`LLM_API_KEY` 用于后端默认配置，不能代替对已有数据库模型配置的修改。

## 6. 启动与停止

在项目根目录运行，或双击 `start-local.cmd`：

```powershell
.\start-local.cmd
```

看到 `Local services started` 后访问：

- 页面：<http://127.0.0.1:5174/>
- 后端健康检查：<http://127.0.0.1:8000/healthz>，正常返回 `{"status":"ok"}`。
- 后端接口文档：<http://127.0.0.1:8000/docs>。

如果本机已经运行另一个副本，使用不同端口，不要覆盖原项目：

```powershell
.\start-local.cmd -BackendPort 8011 -FrontendPort 5175
```

此时访问 <http://127.0.0.1:5175/>，健康检查地址为 <http://127.0.0.1:8011/healthz>。脚本会设置前端对应的 API 地址，不需要手动修改源码。

停止当前文件夹启动的服务：

```powershell
.\stop-local.cmd
```

不要通过关闭浏览器判断服务已经停止。运行期间日志写入 `.runtime/backend.err.log`、`.runtime/frontend.err.log` 等文件。原项目旧日志位于 `archive/runtime/`，不会参与本次启动。

## 7. 手动分开启动（排查问题时使用）

下面是对自动脚本的替代方案，不要与自动启动同时运行。先在根目录执行一次路径准备：

```powershell
.\backend\.venv\Scripts\python.exe scripts\prepare-data.py
```

终端一启动后端：

```powershell
Set-Location backend
$env:PYTHONUTF8='1'
.\.venv\Scripts\python.exe -m uvicorn main:app --app-dir src --host 127.0.0.1 --port 8000 --env-file .env
```

终端二从项目根目录启动前端：

```powershell
$env:VITE_API_BASE_URL='http://127.0.0.1:8000'
npm.cmd --prefix frontend run dev -- --host 127.0.0.1 --port 5174 --strictPort
```

分别在两个终端按 `Ctrl+C` 停止。手动进程不受 `stop-local.cmd` 管理。

## 8. 首次启动验收

1. 首页历史列表能看到已有研究，打开记录后能看到最终报告和子任务。
2. 笔记列表和对话历史可以打开；图谱助手初次进入显示新对话，旧会话在各自历史栏中。
3. 本地文献列表可打开原始 PDF/TXT；Word 文件由浏览器下载后使用本机软件打开。
4. 进入“研究图谱”，确认已有导入记录和真实学术图谱数据，搜索“大语言模型”或“多模态”。
5. 模型配置“测试连接”通过后，尝试一次简短问答。
6. 填写 Tavily Key 并重启后，运行一个小型联网研究，检查报告、来源和质检面板。

前四项可以用于确认数据迁移是否完整；后两项依赖接收者自己的有效密钥、余额、网络和模型权限。

## 9. 常见问题

**启动成功，但模型报 401/403**：在页面修改对应模型配置，检查 Key、地址、模型 ID 是否匹配。不要只改 `.env`，也不要把 Tavily Key 填到模型 API Key 中。

**搜索提示未配置 Tavily**：确认修改的是当前文件夹的 `backend/.env`，填写原始 Key 后执行停止和重新启动。

**端口占用**：使用本文件夹的停止脚本，或按第 6 节换端口。不要启动多个使用同一数据库的副本。

**`Failed to fetch`**：先检查后端健康地址，再查看 `.runtime` 日志。使用脚本打印出的前端地址，确认没有打开另一个项目的旧页面。

**看不到原来的历史或图谱**：检查两个 SQLite 文件是否完整，确认访问的是这个目录启动的服务。不要运行 `seed.py`、`clear_synthetic.py` 或导入旧共享历史来“恢复”，这些会改变现有数据。

**原文件打不开**：运行 `scripts/prepare-data.py` 并重启，确认 `backend/data/library_files` 未遗漏。路径脚本只修复本包中文件的引用，不重新提取或改写原始文献。

**PowerShell 阻止 `.ps1`**：优先运行 `.cmd` 包装脚本；它只对本次进程使用 `ExecutionPolicy Bypass`，无需更改全局执行策略。

**依赖安装失败**：检查网络与本机配置的 pip/npm 镜像。根据错误信息修复后重跑安装脚本，不要删除数据库。不要直接用 `npm audit fix --force` 改动锁定依赖。

**迁移或备份**：先停止程序，再复制整个目录。若只备份业务数据，至少保留完整 `backend/data/`、`backend/notes/` 与配置文件。重新发送给他人前须再次清理新录入的 API 密钥。

## 10. 可选检查命令

```powershell
.\backend\.venv\Scripts\python.exe -m pip check
npm.cmd --prefix frontend run build
.\backend\.venv\Scripts\python.exe -m unittest discover -s backend\tests
```

前端构建用于验证代码；日常使用仍可通过 `start-local.cmd` 启动。自动测试不能替代使用接收者自身 API 的真实连接验证。

本交付保留原项目许可文件 `UPSTREAM_LICENSE.txt`。当前目录是可直接转交的文件包；如使用 Git 上传，注意原有忽略规则可能排除数据库，推荐直接传递完整目录或 ZIP。
