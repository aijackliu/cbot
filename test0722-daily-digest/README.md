# test0722-daily-digest · 每日熱點（熱搜 + HN + 部落格）

三路合併：

1. **多平台熱搜** — `F:\grok\2\hot-search`（與 grok/2 `start.ps1` 相同，含 LLM 繁中）  
2. **Hacker News** — Algolia API（免 key；模式參考 [HN newsletter agent](https://github.com/Sumanth077/Hands-On-AI-Engineering/tree/main/ai_agents/hacker_news_newsletter_agent)）  
3. **科技部落格** — Karpathy 向 92 RSS + LAN Qwen  

## 一鍵

```powershell
cd F:\grok\3\cbot\test0722-daily-digest
.\start.ps1
```

依序：

1. 更新熱搜（LLM 繁中）  
2. 抓 HN + 92 RSS → Qwen 摘要 → `output/digest-YYYY-MM-DD.md`

### 參數

```powershell
.\start.ps1 -NoHot                 # 不重抓熱搜（仍讀 latest.json 寫入摘要）
.\start.ps1 -NoHn                  # 不要 HN
.\start.ps1 -HnMode latest -HnTop 10
.\start.ps1 -FetchOnly
.\start.ps1 -MixHotRank
```

## 僅 Python

```powershell
python run_digest.py --refresh-hot --hn-mode front --hn-top 8
python run_digest.py --no-hot --hn-mode latest
python run_digest.py --fetch-only
```

## 輸出章節

```markdown
# 每日熱點摘要
## 多平台熱搜
## Hacker News
## 科技部落格熱門（Karpathy 列表）
```

## 環境變數

| 變數 | 預設 |
|------|------|
| `HOT_SEARCH_ROOT` | `F:\grok\2\hot-search` |
| `QWEN_URL` | LAN Qwen completions |
| `DIGEST_TOP_N` | `5`（部落格） |

## 說明

- HN 預設 **front_page**（訊號較好）；`latest` 對齊 newsletter agent 的「最新 10 則」。  
- **不預設全文爬取**（版權／反爬）；用標題 + points/comments + Qwen 繁中。  
- 不構成投資建議。
