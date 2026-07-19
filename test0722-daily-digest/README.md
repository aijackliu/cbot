# test0722-daily-digest · 每日熱點（熱搜 + 科技部落格）

合併兩路「熱門」：

1. **多平台熱搜** — 接 `F:\grok\2\hot-search`（與 `.\start.ps1` 相同：抓取 + **LLM 轉繁中**）  
2. **科技部落格** — Karpathy 向 **92 RSS** + **LAN Qwen** 打分／繁中摘要  

參考部落格管線：[Hands-On daily-news-digest](https://github.com/Sumanth077/Hands-On-AI-Engineering/tree/main/ai_agents/daily-news-digest)

## 流程

```text
[1] F:\grok\2\hot-search\fetch_hot_search.py
      → data/latest.json（主題聚類 + 各平台 Top + 繁中）

[2] sources.json (92 RSS)
      → 並行抓取 → 24h 過濾
      → Qwen Top N

[3] 合併 → output/digest-YYYY-MM-DD.md
      ## 多平台熱搜
      ## 科技部落格熱門
```

## 一鍵（建議）

```powershell
cd F:\grok\3\cbot\test0722-daily-digest
.\start.ps1
```

會依序：

1. 更新熱搜（含 LLM 繁中，路徑同 grok/2）  
2. 抓部落格 + Qwen 排序 → 寫入 `output/digest-*.md`

參數：

```powershell
.\start.ps1 -NoHot          # 不重抓熱搜，用既有 latest.json
.\start.ps1 -FetchOnly      # 不呼叫 Qwen
.\start.ps1 -MixHotRank     # 熱搜條目與部落格混排進 Top N
.\start.ps1 -Hours 48 -Top 5
```

## 僅 Python

```powershell
python -m pip install -r requirements.txt
# 熱搜：需 grok/2 依賴 httpx（見 F:\grok\2\hot-search\requirements.txt）

python run_digest.py --refresh-hot
python run_digest.py --hours 48 --top 5
python run_digest.py --mix-hot-rank
python run_digest.py --no-hot
python run_digest.py --fetch-only
```

環境變數：

| 變數 | 預設 |
|------|------|
| `HOT_SEARCH_ROOT` | `F:\grok\2\hot-search` |
| `QWEN_URL` | `http://100.88.220.82:8080/v1/chat/completions` |
| `QWEN_MODEL` | `Qwen3.6-35B-A3B-MXFP4_MOE.gguf` |
| `DIGEST_TOP_N` | `5` |
| `DIGEST_HOURS` | `24` |

## 輸出

| 檔案 | 說明 |
|------|------|
| `output/digest-*.md` | 熱搜章節 + 部落格 Top |
| `output/candidates-*.json` | RSS 候選 |
| `F:\grok\2\hot-search\data\latest.json` | 熱搜完整 JSON |

## 與 grok/2 看板的關係

- 熱搜**抓取與繁中**仍由 `F:\grok\2\hot-search` 負責（與 `F:\grok\2\start.ps1` 第 1 步一致）。  
- 本目錄負責**合併**成一份每日 Markdown，方便閱讀／存檔。  
- 美股晨會／台股行情仍在 grok/2 看板；此 digest 不重複抓行情。

## 注意

- RSS 只用標題/摘要；熱搜用公開榜接口。  
- `sources.json` 與失效 feed 需自行維護。  
- 不構成投資建議。
