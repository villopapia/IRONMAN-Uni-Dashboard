# Starts the dashboard backend (:8000) and frontend (:5173) if they aren't already
# running. Safe to run repeatedly. Logs go to .\logs (gitignored via *.log).
$root = $PSScriptRoot
$logs = Join-Path $root "logs"
New-Item -ItemType Directory -Force -Path $logs | Out-Null

function Test-Port([int]$port) {
    [bool](Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
}

# The backend must start from backend\ - .env and the SQLite path are relative to it.
if (-not (Test-Port 8000)) {
    Start-Process -FilePath (Join-Path $root "backend\.venv\Scripts\python.exe") `
        -ArgumentList "-m", "uvicorn", "app.main:app", "--port", "8000" `
        -WorkingDirectory (Join-Path $root "backend") -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $logs "backend.out.log") `
        -RedirectStandardError (Join-Path $logs "backend.err.log")
}

# --host 127.0.0.1 because Vite otherwise binds IPv6-only on this machine.
if (-not (Test-Port 5173)) {
    $node = Join-Path $env:LOCALAPPDATA "NodePortable\node-v22.14.0-win-x64\node.exe"
    if (-not (Test-Path $node)) { $node = (Get-Command node -ErrorAction Stop).Source }
    Start-Process -FilePath $node `
        -ArgumentList "node_modules\vite\bin\vite.js", "--port", "5173", "--host", "127.0.0.1" `
        -WorkingDirectory (Join-Path $root "frontend") -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $logs "frontend.out.log") `
        -RedirectStandardError (Join-Path $logs "frontend.err.log")
}
