# CATCH CRM 展示站（test0720-crm）

整合遠端基礎建設，並讀取 PostgreSQL `catch_crm` 既有假資料做 CRM 展示。

| 服務 | 位址 |
|------|------|
| Qwen Chat | `http://100.88.220.82:8080/v1/chat/completions` |
| FastAPI（glasses_backend） | `http://100.88.220.82:9000` |
| Redis | `100.88.220.82:6379` |
| PostgreSQL | `100.88.220.82:5432` / DB `catch_crm` |

## 啟動

**PowerShell（推薦）**

```powershell
cd test0720-crm
.\start.ps1
```

可選參數：

```powershell
.\start.ps1 -Port 18720 -SkipInstall -NoBrowser
```

**手動**

```bash
cd test0720-crm
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 18720 --reload
```

瀏覽器開啟：http://127.0.0.1:18720/

## 功能

- 儀表板 KPI（帳戶／商機／電商客戶與營收）
- 客戶帳戶、銷售機會管道、電商客戶、競品
- **客服 AI · 路由**（側欄總線）：輕量路由 + 記憶 + 填表 + 中文查庫  
  - 路由：`POST /api/cs/route` · `GET /api/cs/departments`  
  - 記憶：`/api/cs/memory` · `/api/cs/chat` · `/api/cs/seed` · `/api/cs/greeting`  
  - 填表：`/api/forms/*` · SQL：`/api/sql/*`（只讀白名單）  
- **農業客戶**（側欄分頁，與總線並列）：多工具農業助理  
  - `POST /api/agri/ask` · `GET /api/agri/samples` · `GET /api/agri/crops`  
  - 天氣（wttr.in／OpenWeather）· 作物曆 · 農業新聞 RSS · Qwen（參考 llm_agri_bot）
- 基礎設施狀態（Qwen / FastAPI / Redis / Postgres）
- Qwen 業務助理（帶 CRM 指標上下文）
- Redis 快取 dashboard 30 秒

預設帳密僅供內網展示：Postgres `postgres/postgres`。
