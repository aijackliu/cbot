# 2026-07-14｜test0714c

## 2330 PA Hub · 支阻 / Qwen / PG / Redis / FastAPI

台積電 **2330.TW** 價格行為支阻網頁中樞說明頁。算法同源 [SPX Price Action Compass](https://github.com/kain26/SPX-Price-Action-Compass) / `futu_sr_indicator.py`，日線容差改為 **0.5%**。

| 項目 | 內容 |
|------|------|
| **線上預覽** | https://aijackliu.github.io/cbot/test0714c/ |
| **頁面** | `index.html` |
| **架構** | `architecture.md` |
| **本機產品** | 工作區 `pa-2330-hub` → `http://127.0.0.1:8792/` |

### 服務地圖

| 服務 | 端點 |
|------|------|
| Hub | `127.0.0.1:8792` |
| Qwen | `:8080/v1/chat/completions` |
| Ollama | `:11434/api/tags` |
| FastAPI | `:9000` |
| Redis | `:6379` |
| PostgreSQL | `:5432` / `pa_2330` |
| Adminer | `:5050` |

### 本機啟動

```powershell
cd pa-2330-hub
pip install -r requirements.txt
python setup_postgres.py
python server.py
```

靜態 HTML 無需後端；完整分析需本機 Hub + 遠端 PG／Qwen。
