# 每日熱點：熱搜（grok/2）+ Karpathy 部落格摘要（Qwen 繁中）
#
# 會依序：
#   1. 更新熱搜（F:\grok\2\hot-search，含 LLM 轉繁中）
#   2. 抓取 92 RSS + Qwen 排序 → output/digest-*.md
#
# 用法：
#   .\start.ps1
#   .\start.ps1 -NoHot          # 跳過熱搜更新（仍讀既有 latest.json）
#   .\start.ps1 -FetchOnly      # 不呼叫 Qwen
#   .\start.ps1 -MixHotRank     # 熱搜條目與部落格混排 Top N

param(
    [switch]$NoHot,
    [switch]$FetchOnly,
    [switch]$MixHotRank,
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

Write-Host "==> 每日熱點摘要（熱搜 + 科技部落格）" -ForegroundColor Cyan
Write-Host "    hot-search root: $HotRoot" -ForegroundColor DarkGray
Write-Host "    Qwen:           $($env:QWEN_URL)" -ForegroundColor DarkGray

# ── 1. 熱搜（與 grok/2 start.ps1 同款抓取 + 繁中）────────────────
if (-not $NoHot) {
    $hotScript = Join-Path $HotRoot "fetch_hot_search.py"
    if (Test-Path $hotScript) {
        Write-Host "==> [1/2] 更新熱搜／LLM 繁中…" -ForegroundColor Cyan
        Push-Location $HotRoot
        try {
            & $python $hotScript --limit 30
            if ($LASTEXITCODE -ne 0) {
                Write-Host "==> 熱搜更新失敗（exit $LASTEXITCODE），仍繼續 digest" -ForegroundColor Yellow
            } else {
                Write-Host "==> 熱搜已更新" -ForegroundColor Green
            }
        } finally {
            Pop-Location
        }
    } else {
        Write-Host "==> 找不到 $hotScript，跳過熱搜更新" -ForegroundColor Yellow
    }
} else {
    Write-Host "==> 跳過熱搜更新（-NoHot），使用既有 latest.json" -ForegroundColor DarkGray
}

# ── 2. 部落格 RSS + Qwen + 合併輸出 ─────────────────────────────
Write-Host "==> [2/2] 部落格摘要 + 合併 Markdown…" -ForegroundColor Cyan
$argsList = @(
    "run_digest.py",
    "--hours", "$Hours",
    "--top", "$Top"
)
if ($FetchOnly) { $argsList += "--fetch-only" }
if ($MixHotRank) { $argsList += "--mix-hot-rank" }
# 熱搜已在上面 refresh（或 -NoHot 略過）；此處只讀 latest.json，不重複抓

& $python @argsList
if ($LASTEXITCODE -ne 0) { throw "run_digest.py 失敗" }

$day = (Get-Date).ToString("yyyy-MM-dd")
$out = Join-Path $Root "output\digest-$day.md"
Write-Host ""
Write-Host "完成。" -ForegroundColor Green
if (Test-Path $out) {
    Write-Host "摘要檔    $out" -ForegroundColor White
}
$latestHot = Join-Path $HotRoot "data\latest.json"
if (Test-Path $latestHot) {
    Write-Host "熱搜 JSON $latestHot"
    Write-Host "熱搜頁    見 grok/2 :  .\start.ps1 後開 hot-search/hot-search.html"
}
Write-Host ""
