# 本地使用方法

## 启动

修改完成后需要重启后端和前端，使新路由与新页面生效。项目当前可继续使用原有手动启动方式：

```powershell
Set-Location -LiteralPath "D:\学期项目\deepresearch"
.\backend\.venv\Scripts\python.exe -m uvicorn main:app --app-dir ".\backend\src" --env-file ".\backend\.env" --host 127.0.0.1 --port 8000
```

另开 PowerShell：

```powershell
Set-Location -LiteralPath "D:\学期项目\deepresearch"
npm.cmd --prefix frontend run dev -- --host 127.0.0.1 --port 5174 --strictPort
```

首页左侧会出现“研究广场”。已经结束且有最终报告的研究，会显示“公开到研究广场”。

## 模拟数据

当前本地已生成 medium 数据集。`--reset` 只替换 `seed-*` 模拟研究，会保留用户自己公开的研究，也不会触碰原研究历史：

```powershell
.\backend\.venv\Scripts\python.exe scripts\research_square\seed.py --preset medium --reset
```

## 审计和并发测试

```powershell
.\backend\.venv\Scripts\python.exe scripts\research_square\audit.py
.\backend\.venv\Scripts\python.exe scripts\research_square\load_test.py --reads 500 --writes 100 --workers 32
```

本地生成的 SQLite 数据库受 `.gitignore` 保护，不会被提交到 GitHub。提交代码时应提交生成器和迁移逻辑，而不是 117 MiB 的模拟数据库文件。

## OpenAlex 真实元数据

少量匿名验证不需要 API Key；导入超过 100 条需要免费的 OpenAlex API Key，用于游标翻页，不需要充值。不要把 Key 发到聊天或提交到 GitHub，在 `backend/.env` 中增加：

```dotenv
OPENALEX_API_KEY=你的免费Key
```

导入 5,000 条：

```powershell
.\backend\.venv\Scripts\python.exe scripts\research_square\import_openalex.py --limit 5000
```

导入 10,000 条时把参数改为 `--limit 10000`。默认只导入 2024 年以来、不晚于今天、有摘要的 article、review 和 preprint；导入过程只写入 `openalex_*` 独立表。

## 批量 AI 增强

先在主界面模型配置中准备一个带 API Key 的模型，然后执行：

```powershell
.\backend\.venv\Scripts\python.exe scripts\research_square\enrich_openalex_ai.py `
  --model-profile-id 你的模型配置ID `
  --topic-batch 20 `
  --review-batch 10
```

脚本会跳过已经完成的记录，可以安全续跑。若只处理主题，增加 `--skip-reviews`；若只复核低置信度论文，增加 `--skip-topics`。

增强脚本会先检索现有规范主题和别名，命中等价候选时复用；没有合适候选才建立新规范主题。批量导入和增强完成后，可以运行存量语义归并：

```powershell
.\backend\.venv\Scripts\python.exe scripts\research_square\merge_openalex_aliases_ai.py `
  --model-profile-id 你的模型配置ID `
  --minimum-name-similarity .75 `
  --auto-merge-confidence .95 `
  --batch 6
```

脚本可安全重复运行，只处理 `pending` 规范主题。先增加 `--dry-run` 可以查看候选数量而不调用模型、不执行AI归并。
