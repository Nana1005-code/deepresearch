param([string] $PythonExe = '')
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$backend = Join-Path $root 'backend'
$venv = Join-Path $backend '.venv\Scripts\python.exe'
if (!(Get-Command node.exe -ErrorAction SilentlyContinue) -or !(Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
    throw 'Install Node.js (including npm), reopen PowerShell, and retry.'
}
if (!(Test-Path -LiteralPath $venv)) {
    if ($PythonExe) {
        & $PythonExe -m venv (Join-Path $backend '.venv')
    } elseif (Get-Command py.exe -ErrorAction SilentlyContinue) {
        & py.exe -3.11 -m venv (Join-Path $backend '.venv')
    } else {
        & python.exe -m venv (Join-Path $backend '.venv')
    }
    if ($LASTEXITCODE -ne 0) { throw 'Could not create Python environment. Install Python 3.11 or pass -PythonExe with its full path.' }
}
& $venv -c 'import sys; assert sys.version_info >= (3,11), "Python 3.11 or newer is required"'
if ($LASTEXITCODE -ne 0) { throw 'Python version check failed.' }
& $venv -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'pip upgrade failed. Check network/proxy settings.' }
& $venv -m pip install -r (Join-Path $backend 'requirements.local.txt')
if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
& $venv -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Python dependency verification failed.' }
& npm.cmd --prefix (Join-Path $root 'frontend') ci
if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
foreach ($pair in @(@('backend\.env.example','backend\.env'), @('frontend\.env.example','frontend\.env.local'))) {
    if (!(Test-Path -LiteralPath (Join-Path $root $pair[1]))) {
        Copy-Item -LiteralPath (Join-Path $root $pair[0]) -Destination (Join-Path $root $pair[1])
    }
}
& $venv (Join-Path $root 'scripts\prepare-data.py')
if ($LASTEXITCODE -ne 0) { throw 'Data path preparation failed. Check that all bundled data files exist.' }
Write-Host 'Setup complete. Configure your own keys as described in README.md, then run start-local.cmd.' -ForegroundColor Green
