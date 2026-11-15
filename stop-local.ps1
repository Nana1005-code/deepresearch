$ErrorActionPreference = 'Stop'
$runtimeDir = Join-Path $PSScriptRoot '.runtime'
foreach ($serviceName in @('frontend','backend')) {
    $statePath = Join-Path $runtimeDir "$serviceName.json"
    if (!(Test-Path -LiteralPath $statePath)) { continue }
    $saved = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
    $service = Get-Process -Id $saved.id -ErrorAction SilentlyContinue
    if ($service -and [string]$service.StartTime.ToUniversalTime().Ticks -eq [string]$saved.startedTicks -and $service.Path -eq $saved.executable) {
        $treeStopped = $false
        try {
            $children = Get-CimInstance Win32_Process -Filter "ParentProcessId=$($service.Id)" -ErrorAction Stop
            foreach ($child in $children) {
                if ($child.CommandLine -and $child.CommandLine.Contains($PSScriptRoot)) {
                    Stop-Process -Id $child.ProcessId -ErrorAction SilentlyContinue
                }
            }
        } catch {
            # Some managed terminals deny CIM. The recorded PID has already been
            # validated by start time and executable, so stopping its process tree is safe.
            $taskkill = Join-Path $env:SystemRoot 'System32\taskkill.exe'
            if (Test-Path -LiteralPath $taskkill) {
                try {
                    & $taskkill /PID $service.Id /T /F 2>$null | Out-Null
                    $treeStopped = ($LASTEXITCODE -eq 0)
                } catch {
                    $treeStopped = $false
                }
            }
        }
        if (!$treeStopped) {
            Stop-Process -Id $service.Id -ErrorAction SilentlyContinue
        }
        Write-Host "Stopped $serviceName."
    }
    Remove-Item -LiteralPath $statePath
}
