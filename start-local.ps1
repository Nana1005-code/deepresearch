param(
    [ValidateRange(1, 65535)] [int] $BackendPort = 8000,
    [ValidateRange(1, 65535)] [int] $FrontendPort = 5174
)

$ErrorActionPreference = 'Stop'

$projectRoot = $PSScriptRoot
$backendDir = Join-Path $projectRoot 'backend'
$frontendDir = Join-Path $projectRoot 'frontend'
$pythonExe = Join-Path $backendDir '.venv\Scripts\python.exe'
$nodeExe = (Get-Command node.exe -ErrorAction SilentlyContinue).Source
$viteEntry = Join-Path $frontendDir 'node_modules\vite\bin\vite.js'
$runtimeDir = Join-Path $projectRoot '.runtime'

if (!(Test-Path -LiteralPath $pythonExe)) {
    throw "Backend virtual environment not found: $pythonExe. Follow README.md to install dependencies first."
}
if (!$nodeExe) {
    throw 'node.exe was not found. Install Node.js and reopen PowerShell.'
}
if (!(Test-Path -LiteralPath $viteEntry)) {
    throw "Vite was not found: $viteEntry. Run npm.cmd --prefix frontend ci first."
}

& $pythonExe (Join-Path $projectRoot 'scripts\prepare-data.py')
if ($LASTEXITCODE -ne 0) { throw 'Bundled data preparation failed.' }

New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null

function Save-ServiceState {
    param(
        [Parameter(Mandatory = $true)] [string] $Name,
        [Parameter(Mandatory = $true)] [System.Diagnostics.Process] $Process
    )

    $Process.Refresh()
    @{
        id = $Process.Id
        startedTicks = [string] $Process.StartTime.ToUniversalTime().Ticks
        executable = $Process.Path
    } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $runtimeDir "$Name.json") -Encoding utf8
}

function Wait-HttpReady {
    param(
        [Parameter(Mandatory = $true)] [string] $Uri,
        [Parameter(Mandatory = $true)] [System.Diagnostics.Process] $Process,
        [int] $TimeoutSeconds = 20
    )

    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        $Process.Refresh()
        if ($Process.HasExited) { return $false }
        try {
            $response = Invoke-WebRequest -Uri $Uri -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                return $true
            }
        } catch {
            Start-Sleep -Milliseconds 400
        }
    }
    return $false
}

foreach ($serviceName in @('backend', 'frontend')) {
    $statePath = Join-Path $runtimeDir "$serviceName.json"
    if (!(Test-Path -LiteralPath $statePath)) { continue }
    $saved = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
    $existing = Get-Process -Id $saved.id -ErrorAction SilentlyContinue
    if ($existing) {
        throw "$serviceName is already running (PID $($saved.id)). Run .\stop-local.cmd first."
    }
}

foreach ($selectedPort in @($BackendPort, $FrontendPort)) {
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $selectedPort)
    try { $listener.Start() } catch { throw "Port $selectedPort is occupied. Choose unused -BackendPort and -FrontendPort values." } finally { $listener.Stop() }
}
if ($BackendPort -eq $FrontendPort) { throw 'Backend and frontend must use different ports.' }

$backendOut = Join-Path $runtimeDir 'backend.out.log'
$backendErr = Join-Path $runtimeDir 'backend.err.log'
$frontendOut = Join-Path $runtimeDir 'frontend.out.log'
$frontendErr = Join-Path $runtimeDir 'frontend.err.log'
$backendEnvFile = Join-Path $backendDir '.env'

$previousPythonUtf8 = $env:PYTHONUTF8
$env:PYTHONUTF8 = '1'
$backendArguments = @(
    '-m', 'uvicorn', 'main:app',
    '--app-dir', (Join-Path $backendDir 'src'),
    '--host', '127.0.0.1',
    '--port', $BackendPort
)
if (Test-Path -LiteralPath $backendEnvFile) {
    $backendArguments += @('--env-file', $backendEnvFile)
}
$backend = Start-Process -FilePath $pythonExe `
    -ArgumentList @($backendArguments | ForEach-Object { '"' + [string]$_ + '"' }) `
    -WorkingDirectory $backendDir -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput $backendOut -RedirectStandardError $backendErr
if ($null -eq $previousPythonUtf8) { Remove-Item Env:PYTHONUTF8 } else { $env:PYTHONUTF8 = $previousPythonUtf8 }
Save-ServiceState -Name 'backend' -Process $backend

$previousApiBase = $env:VITE_API_BASE_URL
$env:VITE_API_BASE_URL = "http://127.0.0.1:$BackendPort"
$frontend = Start-Process -FilePath $nodeExe `
    -ArgumentList @(@($viteEntry, '--host', '127.0.0.1', '--port', $FrontendPort, '--strictPort') | ForEach-Object { '"' + [string]$_ + '"' }) `
    -WorkingDirectory $frontendDir -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput $frontendOut -RedirectStandardError $frontendErr
if ($null -eq $previousApiBase) { Remove-Item Env:VITE_API_BASE_URL } else { $env:VITE_API_BASE_URL = $previousApiBase }
Save-ServiceState -Name 'frontend' -Process $frontend

$backendReady = Wait-HttpReady -Uri "http://127.0.0.1:$BackendPort/healthz" -Process $backend
$frontendReady = Wait-HttpReady -Uri "http://127.0.0.1:$FrontendPort/" -Process $frontend
if (!$backendReady -or !$frontendReady) {
    Write-Host 'Startup failed. Check these logs:' -ForegroundColor Red
    Write-Host "  $backendErr"
    Write-Host "  $frontendErr"
    & (Join-Path $projectRoot 'stop-local.ps1')
    throw 'A local service exited early. The selected port may already be in use.'
}

Write-Host 'Local services started:' -ForegroundColor Green
Write-Host "  Frontend: http://127.0.0.1:$FrontendPort/"
Write-Host "  Backend:  http://127.0.0.1:$BackendPort/healthz"
Write-Host 'Stop services with: .\stop-local.cmd'
