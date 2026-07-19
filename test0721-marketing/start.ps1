# CATCH Marketing Site launcher
# Usage: .\start.ps1

[CmdletBinding()]
param(
    [string]$ListenHost = "0.0.0.0",
    [int]$Port = 18721,
    [switch]$SkipInstall,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
Set-Location $Root

function Write-Step([string]$msg) {
    Write-Host ""
    Write-Host "==> $msg" -ForegroundColor Cyan
}

Write-Host "CATCH Growth · Marketing Demo" -ForegroundColor Green
Write-Host "  root: $Root"
Write-Host "  url:  http://127.0.0.1:$Port/"

$Python = $null
foreach ($cand in @("py", "python", "python3")) {
    $cmd = Get-Command $cand -ErrorAction SilentlyContinue
    if ($cmd) { $Python = $cmd.Source; break }
}
if (-not $Python) { Write-Error "Python not found." }

Write-Step "Python: $Python"
& $Python --version

if (-not $SkipInstall) {
    Write-Step "Install dependencies"
    & $Python -m pip install -r (Join-Path $Root "requirements.txt") --quiet
    if ($LASTEXITCODE -ne 0) { Write-Error "pip install failed" }
}

try {
    $owners = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($procId in $owners) {
        if ($procId -and $procId -ne 0) {
            Write-Host "Port $Port in use by PID $procId — stopping..." -ForegroundColor Yellow
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
            Start-Sleep -Milliseconds 400
        }
    }
} catch { }

if (-not $NoBrowser) {
    $url = "http://127.0.0.1:$Port/"
    Start-Job -ScriptBlock {
        param($u)
        Start-Sleep -Seconds 1.5
        Start-Process $u
    } -ArgumentList $url | Out-Null
}

Write-Step "Start uvicorn ($ListenHost`:$Port)"
Write-Host "Press Ctrl+C to stop." -ForegroundColor DarkGray
& $Python -m uvicorn app.main:app --host $ListenHost --port $Port --reload --app-dir $Root
exit $LASTEXITCODE
