# 022 Windows PowerShell 5.1 编码兼容修复

## 问题

`start-local.ps1` 最初保存为 UTF-8 无 BOM，并包含中文提示字符串。Windows PowerShell 5.1 会按系统 ANSI/GBK 代码页读取无 BOM 脚本，导致中文字节被错误解码，继而出现 `UnexpectedToken`、字符串缺少终止符等解析错误。

## 修复

- 将启动脚本中的运行时提示改为纯 ASCII 英文。
- 脚本逻辑、端口参数、路径处理和服务状态格式不变。
- `stop-local.ps1` 已带 UTF-8 BOM，无需改动编码。
- 停止脚本在受限终端无法使用 CIM 或 `taskkill` 时，会回退到停止已校验的服务 PID，并继续清理状态文件。
- 启动完成判定由固定等待 2 秒改为轮询前端首页和后端 `/healthz`，只有两个地址都可访问才报告成功。

## 验证

使用系统自带的 `C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe` 进行解析和启动验证，避免仅在 PowerShell 7 下通过而遗漏兼容问题。
