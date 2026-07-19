# 每日熱點：熱搜 + Hacker News + Karpathy 部落格
#
# 會依序：
#   1. 更新熱搜（F:\grok\2\hot-search，含 LLM 轉繁中）
#   2. HN + 92 RSS + Qwen → output/digest-*.md（含熱搜章節）
#
# 用法：
#   .\start.ps1
#   .\start.ps1 -NoHot
#   .\start.ps1 -NoHn
#   .\start.ps1 -FetchOnly
#   .\start.ps1 -HnMode latest -HnTop 10

param(
    [switch]$NoHot,
    [switch]$NoHn,
    [switch]$FetchOnly,
    [switch]$MixHotRank,
    [ValidateSet("front", "latest")]
    [string]$HnMode = "front",
    [int]$HnTop = 8,
    [int]$Hours = 24,
    [int]$Top = 5
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
Set-Location $Root

function Get-PythonExe {
    $py = Get-Command python -ErrorAction SilentlyContinue
    if ($py) { return $py.Source }
    throw "找不到 python"
}

$python = Get-PythonExe
$HotRoot = if ($env:HOT_SEARCH_ROOT) { $env:HOT_SEARCH_ROOT } else { "F:\grok\2\hot-search" }

Write-Host "==> 每日熱點（熱搜 + HN + 部落格）" -ForegroundColor Cyan
Write-Host "    hot-search: $HotRoot" -ForegroundColor DarkGray
Write-Host "    HN mode:    $HnMode top=$HnTop" -ForegroundColor DarkGray

# ── 1. 熱搜 ─────────────────────────────────────────────────────
if (-not $NoHot) {
    $hotScript = Join-Path $HotRoot "fetch_hot_search.py"
    if (Test-Path $hotScript) {
        Write-Host "==> [1/2] 更新熱搜／LLM 繁中…" -ForegroundColor Cyan
        Push-Location $HotRoot
        try {
            & $python $hotScript --limit 30
            if ($LASTEXITCODE -ne 0) {
                Write-Host "==> 熱搜更新失敗（exit $LASTEXITCODE），仍繼續" -ForegroundColor Yellow
            } else {
                Write-Host "==> 熱搜已更新" -ForegroundColor Green
            }
        } finally {
            Pop-Location
        }
    } else {
        Write-Host "==> 找不到熱搜腳本，跳過更新" -ForegroundColor Yellow
    }
} else {
    Write-Host "==> 跳過熱搜更新（-NoHot）" -ForegroundColor DarkGray
}

# ── 2. HN + 博客 + 合併 ─────────────────────────────────────────
Write-Host "==> [2/2] HN + 部落格 + 合併 Markdown…" -ForegroundColor Cyan
$argsList = @(
    "run_digest.py",
    "--hours", "$Hours",
    "--top", "$Top",
    "--hn-mode", $HnMode,
    "--hn-top", "$HnTop"
)
if ($FetchOnly) { $argsList += "--fetch-only" }
if ($MixHotRank) { $argsList += "--mix-hot-rank" }
if ($NoHn) { $argsList += "--no-hn" }
# -NoHot 只跳過重抓；digest 仍讀 latest.json 寫熱搜章

& $python @argsList
if ($LASTEXITCODE -ne 0) { throw "run_digest.py 失敗" }

$day = (Get-Date).ToString("yyyy-MM-dd")
$out = Join-Path $Root "output\digest-$day.md"
Write-Host ""
Write-Host "完成。" -ForegroundColor Green
if (Test-Path $out) { Write-Host "摘要檔    $out" -ForegroundColor White }
$latestHot = Join-Path $HotRoot "data\latest.json"
if (Test-Path $latestHot) { Write-Host "熱搜 JSON $latestHot" }
Write-Host ""
