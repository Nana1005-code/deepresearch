# DeepResearch 深度研究助手整合版

这是一个在 Windows 本地运行的深度研究项目，整合了研究规划、联网检索、报告生成、对话助手、本地文献、Word 导出、报告质检、个人研究图谱和 OpenAlex 真实学术图谱等功能。

项目采用 Vue 前端、FastAPI 后端和 SQLite 本地数据库。每位同学下载后使用自己的模型与搜索 API Key，研究历史和图谱数据默认只保存在自己的电脑上。

## 主要功能

- 新研究：自动拆分研究任务、检索资料、生成笔记和最终报告。
- 对话助手：基于已有研究记录继续提问。
- 本地文献：导入 PDF、Word、TXT 和 Markdown 文件辅助研究。
- 报告导出：将最终报告下载为 Word 文档。
- 报告质检：检查引用、来源、报告结构和缺少依据的章节。
- 我的研究图谱：把自己的研究记录导入本地图谱，查看关键词及其关联。
- 真实学术图谱：基于本机导入的 OpenAlex 论文和标准主题展示学术关系。
- 研究助手：查询真实学术热点，或对照个人历史寻找可能遗漏的研究方向。

## 运行环境

建议使用以下版本：

- Windows 10 或 Windows 11
- Python 3.11 64 位
- Node.js 22 LTS（需要同时安装 npm）
- Git for Windows
- Windows PowerShell 5.1 或 PowerShell 7

安装完成后重新打开 PowerShell，执行下面的命令检查环境：

```powershell
python --version
node --version
npm.cmd --version
git --version
```

Python 应显示 3.11.x，Node.js 建议显示 22.x。项目不要求手动修改系统 Path；如果上述命令无法识别，请重新运行对应安装程序并勾选“添加到 Path”，然后重新打开 PowerShell。

## 首次安装

### 1 下载代码

使用 Git 克隆仓库：

```powershell
Set-Location -LiteralPath "D:\学期项目"
git clone https://github.com/你的账号/你的仓库名.git Deepresearch-integrated
Set-Location -LiteralPath "D:\学期项目\Deepresearch-integrated"
```

也可以从 GitHub 下载 ZIP，解压后在 PowerShell 中进入项目根目录。后面的所有命令都应在包含 `start-local.cmd` 的目录中运行。

### 2 创建 Python 虚拟环境

```powershell
python -m venv backend\.venv
.\backend\.venv\Scripts\python.exe -m pip install --upgrade pip
.\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.local.txt
```

如果 `python` 不是 Python 3.11，可以把第一条命令中的 `python` 换成 Python 3.11 的完整路径，例如：

```powershell
& "C:\Users\你的用户名\AppData\Local\Programs\Python\Python311\python.exe" -m venv backend\.venv
```

不要复制其他电脑的 `.venv`，不同电脑应分别创建虚拟环境。

### 3 安装前端依赖

```powershell
npm.cmd --prefix frontend ci
```

应使用 `npm ci` 按 `package-lock.json` 安装确定版本。安装提示存在依赖漏洞不会阻止本地启动，不要在不了解影响时直接运行 `npm audit fix --force`。

### 4 创建本地配置

以下命令只在配置文件不存在时复制模板，不会覆盖已有配置：

```powershell
if (!(Test-Path backend\.env)) {
    Copy-Item backend\.env.example backend\.env
}
if (!(Test-Path frontend\.env.local)) {
    Copy-Item frontend\.env.example frontend\.env.local
}
```

打开 `backend\.env`，按需要填写：

```dotenv
LLM_BASE_URL=https://你的模型服务地址/v1
LLM_MODEL_ID=你的模型ID
LLM_API_KEY=你的模型APIKey

SEARCH_API=tavily
TAVILY_API_KEY=你的TavilyKey
```

注意：

- `TAVILY_API_KEY` 只能填写原始 Key，不要填写带 Key 的 MCP URL。
- 没有 Tavily Key 时，对话和本地文献仍可使用，但联网研究可能回退到 DuckDuckGo，稳定性较低。
- 也可以启动后在首页“模型配置”中新增或修改模型。导入的历史模型配置不包含 API Key，需要每位使用者自行填写。
- `.env` 含有密钥，已被 Git 忽略，不要截图、提交或发送给其他人。

### 5 可选导入共享历史

想查看仓库附带的脱敏研究样例时执行：

```powershell
.\backend\.venv\Scripts\python.exe scripts\import-history.py
```

这一步不是启动项目的必要条件。重复执行会跳过已经存在的同 ID 数据，不会覆盖本机后来产生的研究。

## 启动和停止

使用默认端口启动：

```powershell
.\start-local.cmd
```

启动成功后访问：

- 前端：http://127.0.0.1:5174/
- 后端健康检查：http://127.0.0.1:8000/healthz

如果默认端口已被占用，可以改用其他端口：

```powershell
.\start-local.ps1 -BackendPort 8011 -FrontendPort 5175
```

此时打开 http://127.0.0.1:5175/ 。启动脚本会自动把前端连接到本次选择的后端端口。

停止服务：

```powershell
.\stop-local.cmd
```

启动日志保存在 `.runtime\backend.err.log` 和 `.runtime\frontend.err.log`。如果启动失败，先查看这两个文件，不要反复启动多个副本。

## 第一次运行时的手动检查

建议按下面顺序验证：

1. 打开后端健康检查地址，确认返回 `{"status":"ok"}`。
2. 在首页模型配置中填写自己的 API Key，点击“测试连接”。
3. 新建一个简短研究，确认任务能完成并显示最终报告。
4. 测试对话助手、本地文献、Word 下载和报告质检。
5. 在已完成研究中点击“导入到我的研究图谱”，确认后台处理完成后出现节点。
6. 如果已经导入 OpenAlex 数据，再测试真实学术图谱和真实学术问答助手。

项目以实际页面手动测试为主要验收方式。自动测试用于辅助检查依赖和基础代码，不代替完整的人工功能验证。

## 本地数据说明

运行后会在本机生成以下主要数据：

- `backend\data\research.sqlite3`：研究历史、对话和模型配置。
- `backend\data\research_square.sqlite3`：个人研究图谱和 OpenAlex 真实学术数据。
- `backend\notes\`：研究笔记。
- `.runtime\`：启动状态和日志。

这些目录已被 Git 忽略。其他同学克隆仓库后得到的是代码和配置模板，不会自动获得你的 API Key、个人研究历史或本机 OpenAlex 数据。

## 导入 OpenAlex 真实学术数据

真实学术图谱初始为空时，需要每位使用者在本机单独导入。导入超过 100 条需要免费的 OpenAlex API Key，把它写入 `backend\.env`：

```dotenv
OPENALEX_API_KEY=你的OpenAlexKey
```

下面示例按明确日期导入 5,000 条论文元数据：

```powershell
.\backend\.venv\Scripts\python.exe `
  scripts\research_square\import_openalex.py `
  --limit 5000 `
  --filter "from_publication_date:2025-01-01,to_publication_date:2025-12-31,has_abstract:true,type:article|review|preprint"
```

导入完成后，先启动项目并取得模型配置 ID：

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/model-profiles" |
  Select-Object id,name,model_id
```

然后执行主题中文化、别名生成和领域归属：

```powershell
.\backend\.venv\Scripts\python.exe `
  scripts\research_square\enrich_openalex_ai.py `
  --model-profile-id 你的模型配置ID `
  --topic-batch 20 `
  --review-batch 10
```

需要继续合并语义等价主题时，先预览候选：

```powershell
.\backend\.venv\Scripts\python.exe `
  scripts\research_square\merge_openalex_aliases_ai.py `
  --model-profile-id 你的模型配置ID `
  --minimum-name-similarity .75 `
  --auto-merge-confidence .95 `
  --batch 6 `
  --dry-run
```

确认候选合理后，去掉最后的 `--dry-run` 再运行一次。脚本会跳过已经完成的主题，可以分批执行和中断续跑。

## 常见问题

### PowerShell 找不到 py 或 python

可以直接使用 Python 3.11 的完整路径创建虚拟环境。只要 `backend\.venv` 创建成功，后续都使用项目虚拟环境中的 `python.exe`。

### npm 命令不存在或 npm 安装损坏

重新运行 Node.js 22 安装程序，确保 npm 功能已安装，然后关闭并重新打开 PowerShell。`node --version` 和 `npm.cmd --version` 都应正常输出。

### 启动提示端口被占用

先运行 `stop-local.cmd`。如果另一个项目正在使用默认端口，可以使用 `-BackendPort` 和 `-FrontendPort` 选择其他端口。

### 页面显示 Failed to fetch

通常表示前端无法连接后端。确认健康检查地址可访问，并确保前后端来自同一次 `start-local.ps1` 启动。修改端口后应打开启动脚本输出的新前端地址。

### 研究返回 401

模型 API Key 无效、过期或与所选模型配置不匹配。进入首页模型配置重新填写并测试连接。Tavily Key 不能解决模型 401。

### 联网检索回退到 DuckDuckGo

确认 `backend\.env` 中存在 `SEARCH_API=tavily` 和有效的原始 `TAVILY_API_KEY`，然后重启项目。

### 测试出现 GBK 无法输出警告符号

测试前设置 UTF-8：

```powershell
$env:PYTHONUTF8 = "1"
```

启动脚本已经自动设置该变量，正常启动和手动使用通常不会受影响。

## 开发检查

手动功能测试完成后，可执行以下基础检查：

```powershell
.\backend\.venv\Scripts\python.exe -m pip check

$env:PYTHONUTF8 = "1"
$env:PYTHONPATH = (Resolve-Path backend\src).Path
.\backend\.venv\Scripts\python.exe -m unittest discover -s backend\tests

npm.cmd --prefix frontend run build
```

完整测试可能耗时较长，最终仍应按照“第一次运行时的手动检查”逐项验收页面功能。

## 上传到自己的 GitHub

本目录已经是 Git 仓库，不要再次执行 `git init`。先在 GitHub 新建一个空仓库，不要勾选自动创建 README、License 或 `.gitignore`。

在项目根目录确认当前分支和远程地址：

```powershell
git branch --show-current
git remote -v
```

提交本次说明文件时不要使用 `git add .`，避免把本机临时文件一起加入。建议明确指定文件：

```powershell
git add README.md RUNNING.txt backend/README.md README-quality-gate.md
git status --short
git commit -m "docs: add setup and local run guide"
```

如果还没有 `origin`：

```powershell
git remote add origin https://github.com/你的账号/你的仓库名.git
git push -u origin HEAD:main
```

如果已经存在 `origin`，但需要改成自己的仓库：

```powershell
git remote set-url origin https://github.com/你的账号/你的仓库名.git
git push -u origin HEAD:main
```

`HEAD:main` 会把当前整合分支上传为远程仓库的 `main` 分支，同时保留本地提交历史。

## 其他说明

- 报告质检的详细说明见 [README-quality-gate.md](README-quality-gate.md)。
- 后端入口说明见 [backend/README.md](backend/README.md)。
- OpenAlex 数据、个人研究历史和 API Key 不应提交到 GitHub。
- 上游项目来源为 [Datawhale Hello Agents](https://github.com/datawhalechina/hello-agents)，仓库保留 `UPSTREAM_LICENSE.txt`。
