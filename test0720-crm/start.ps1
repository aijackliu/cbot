# CATCH CRM Demo launcher
# Usage:  .\start.ps1
# Optional: .\start.ps1 -Port 18720 -Host 0.0.0.0 -SkipInstall

[CmdletBinding()]
param(
    [string]$ListenHost = "0.0.0.0",
    [int]$Port = 18720,
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

Write-Host "CATCH CRM Demo" -ForegroundColor Green
Write-Host "  root: $Root"
Write-Host "  url:  http://127.0.0.1:$Port/"

# Prefer py launcher, then python
$Python = $null
foreach ($cand in @("py", "python", "python3")) {
    $cmd = Get-Command $cand -ErrorAction SilentlyContinue
    if ($cmd) {
        $Python = $cmd.Source
        break
    }
}
if (-not $Python) {
    Write-Error "Python not found. Install Python 3.10+ and retry."
}

Write-Step "Python: $Python"
& $Python --version

if (-not $SkipInstall) {
    Write-Step "Install dependencies (requirements.txt)"
    & $Python -m pip install -r (Join-Path $Root "requirements.txt") --quiet
    if ($LASTEXITCODE -ne 0) {
        Write-Error "pip install failed (exit $LASTEXITCODE)"
    }
}

# Free port if already in use by previous uvicorn (best-effort)
try {
    $owners = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($pid in $owners) {
        if ($pid -and $pid -ne 0) {
            Write-Host "Port $Port in use by PID $pid — stopping it..." -ForegroundColor Yellow
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
            Start-Sleep -Milliseconds 400
        }
    }
} catch {
    # ignore if Get-NetTCPConnection unavailable
}

if (-not $NoBrowser) {
    $url = "http://127.0.0.1:$Port/"
    Start-Job -ScriptBlock {
        param($u)
        Start-Sleep -Seconds 1.5
        Start-Process $u
    } -ArgumentList $url | Out-Null
}

Write-Step "Start uvicorn  ($ListenHost`:$Port)"
Write-Host "Press Ctrl+C to stop." -ForegroundColor DarkGray
Write-Host ""

& $Python -m uvicorn app.main:app --host $ListenHost --port $Port --reload --app-dir $Root
exit $LASTEXITCODE
