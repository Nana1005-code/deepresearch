# 024 直接跟踪 Vite Node 进程

## 问题

通过 `Start-Process npm.cmd` 启动前端时，状态文件记录的是临时 `cmd.exe`。该父进程退出后，真实 Node/Vite 进程可能继续监听端口，导致 `stop-local.cmd` 显示已停止但 5174/5175 仍被占用。

## 修复

- 直接使用 `node.exe node_modules/vite/bin/vite.js` 启动前端。
- `frontend.json` 保存真实 Node 进程 PID，停止脚本可以可靠释放端口。
- 启动失败时立即调用 `stop-local.ps1`，清理另一项已经成功启动的服务及状态文件。
- 启动前检查 `node.exe` 和本地 Vite 入口是否存在，并给出明确安装提示。

## 一次性处理

修复前已经遗留的旧 Vite 进程不在新状态文件中，需要关闭其原 PowerShell 窗口，或确认命令行属于本项目后手动停止一次。后续由新脚本启动的 Vite 可正常通过 `stop-local.cmd` 停止。

## 验证

在 Windows PowerShell 5.1 中连续两次使用同一组测试端口完成“启动 → 前端 HTTP 200 → 后端 healthz=ok → 停止”，第二次仍可绑定相同端口，证明新脚本能够释放真实 Vite 监听进程。
