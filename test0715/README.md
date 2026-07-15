# 2026-07-15｜test0715

## CATCH CRM Hub · 自有 CRM 核心展示

以 **CATCH** 為品牌的 CRM 中樞說明頁：客戶／商機為唯一真相，**戰情 · 告警 · 客服 · 廣告** 為四條進／出水管。  
**不依賴**官方 CordysCRM Docker。

| 項目 | 內容 |
|------|------|
| **線上預覽** | https://aijackliu.github.io/cbot/test0715/ |
| **頁面** | `index.html` |
| **假資料** | `assets/showcase.json`（展示用） |
| **架構** | `architecture.md` |
| **可執行本體** | 工作區 `catch-crm-hub` → `http://127.0.0.1:8791/` |

### 核心主張

```text
CATCH CRM（客戶·商機·活動）
        ↑ 進水
  廣告 · B端告警 · 客服 · 表單
        ↓ 只讀
     戰情看板 / 中控捷徑
```

### 本機跑完整版

```powershell
cd J:\grok\34\catch-crm-hub
pip install -r requirements.txt
python setup_postgres.py
python seed_demo.py --force
python server.py
# http://127.0.0.1:8791/
```

| 服務 | 端點 |
|------|------|
| Hub | `127.0.0.1:8791` |
| PostgreSQL | `100.88.220.82:5432` / `catch_crm` |
| Qwen | `:8080/v1/chat/completions` |
| Ollama | `:11434/api/tags` |
| Redis | `:6379` |
| Adminer | `:5050` |

靜態頁無需後端；完整 CRUD／Qwen 需本機 Hub。
