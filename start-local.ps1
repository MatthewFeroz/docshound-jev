param([switch]$NoBrowser, [ValidateRange(1024, 65535)][int]$Port = 8001)

$ErrorActionPreference = 'Stop'
$appDirectory = Join-Path $PSScriptRoot 'backend'
$pythonPath = Join-Path $appDirectory '.venv/Scripts/python.exe'
$appUrl = "http://localhost:$Port"
$probeUrl = "http://127.0.0.1:$Port"

function Test-DocsHound {
    try {
        $health = Invoke-RestMethod -Uri "$probeUrl/health" -TimeoutSec 3
        $schema = Invoke-RestMethod -Uri "$probeUrl/openapi.json" -TimeoutSec 3
        return ($health.status -eq 'ok' -and $schema.info.title -eq 'DocsHound API')
    } catch { return $false }
}

if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'frontend/dist/index.html'))) {
    throw 'Build the frontend first: cd frontend; bun install --frozen-lockfile; bun run build'
}

if (-not (Test-DocsHound)) {
    if (-not (Test-Path -LiteralPath $pythonPath)) {
        throw 'The Python environment is missing. Follow the setup steps in README.md first.'
    }
    if (Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue) {
        throw "Port $Port is occupied by another application. Use -Port to choose an unused port."
    }
    $logDirectory = Join-Path $appDirectory 'data'
    New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $server = Start-Process -FilePath $pythonPath -ArgumentList @(
        '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', "$Port"
    ) -WorkingDirectory $appDirectory -WindowStyle Hidden -PassThru `
      -RedirectStandardOutput (Join-Path $logDirectory "server-$stamp.log") `
      -RedirectStandardError (Join-Path $logDirectory "server-$stamp.error.log")
    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        if (Test-DocsHound) { $ready = $true; break }
        $server.Refresh()
        if ($server.HasExited) { break }
        Start-Sleep -Milliseconds 500
    }
    if (-not $ready) { throw "DocsHound did not start. See the latest server log in $logDirectory." }
}

Write-Output "DocsHound is available at $appUrl"
if (-not $NoBrowser) { Start-Process $appUrl }
