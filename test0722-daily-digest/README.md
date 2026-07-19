# test0722-daily-digest · 科技部落格每日摘要

從 **Karpathy 向精選 tech blogs（92 RSS）** 抓取過去 24h 文章，用 **LAN Qwen** 打分並輸出 **繁中 Markdown**。

參考：[Hands-On-AI-Engineering daily-news-digest](https://github.com/Sumanth077/Hands-On-AI-Engineering/tree/main/ai_agents/daily-news-digest)  
本版改為：本機腳本 + Qwen（不綁 MiniMax / OpenClaw / Telegram）。

## 流程

```text
sources.json (92)
  → 並行 RSS
  → 過濾 lookback 小時
  → 去重
  → Qwen 選 Top N + 繁中摘要
  → output/digest-YYYY-MM-DD.md
```

## 安裝

```powershell
cd test0722-daily-digest
python -m pip install -r requirements.txt
```

## 執行

```powershell
# 完整：抓取 + Qwen 排序
python run_digest.py

# 只抓取（不調模型）
python run_digest.py --fetch-only

# 自訂
python run_digest.py --hours 48 --top 5 --workers 20
```

環境變數（可選）：

| 變數 | 預設 |
|------|------|
| `QWEN_URL` | `http://100.88.220.82:8080/v1/chat/completions` |
| `QWEN_MODEL` | `Qwen3.6-35B-A3B-MXFP4_MOE.gguf` |
| `DIGEST_TOP_N` | `5` |
| `DIGEST_HOURS` | `24` |
| `DIGEST_WORKERS` | `16` |

## 輸出

| 檔案 | 說明 |
|------|------|
| `output/candidates-*.json` | 視窗內候選（除錯） |
| `output/digest-*.md` | 每日摘要 |

## 定時（Windows）

工作排程器每天執行：

```powershell
cd F:\grok\3\cbot\test0722-daily-digest
python run_digest.py
```

## 注意

- 僅用 RSS **標題/摘要/連結**，不做全文鏡像。
- `sources.json` 需自行維護失效 feed。
- 列表源自社群整理，非 Karpathy 官方 API。
