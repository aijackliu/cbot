# CATCH Growth · 行銷網站展示（test0721-marketing）

整合遠端：

| 服務 | 位址 |
|------|------|
| Qwen | `http://100.88.220.82:8080/v1/chat/completions` |
| Ollama | `http://100.88.220.82:11434/api/tags`（embedding + RAG 生成） |
| FastAPI | `http://100.88.220.82:9000`（glasses_backend，狀態探測） |
| Redis | `100.88.220.82:6379`（快取 + RAG 向量索引） |
| PostgreSQL | `100.88.220.82:5432` / `catch_crm` |

## 啟動

```powershell
cd test0721-marketing
.\start.ps1
```

瀏覽器：http://127.0.0.1:18721/

## 功能

- 行銷落地頁（Hero／方案／案例／詢盤）
- 真實表：`ad_daily`、`marketing_plans`、`audience_packs`、`form_submissions` 等
- Redis：文案種子、dashboard 快取
- Qwen：行銷文案生成
- Ollama：`/api/tags` 列表 + **RAG**（`qwen3-embedding:0.6b` 檢索，`qwen3:latest` 回答）
- **團隊**：假資料名冊（Redis seed）
- **知識庫**：PG 語料目錄 + 內部文章 + 可新增文章（寫 Redis，重建索引後進 RAG）
- 啟動時自動 seed 假證言／方案／團隊／知識文章／補充詢盤

### RAG API

| 方法 | 路徑 | 說明 |
|------|------|------|
| GET | `/api/ollama/tags` | 列出 Ollama 模型 |
| POST | `/api/rag/rebuild` | 重建索引（寫 Redis） |
| POST | `/api/rag/search` | 只檢索 |
| POST | `/api/rag/ask` | 檢索 + 生成 |
| GET | `/api/team` | 團隊名冊 |
| GET | `/api/knowledge` | 知識庫目錄 |
| GET | `/api/knowledge/{id}` | 文件全文 |
| POST | `/api/knowledge/articles` | 新增內部文章 |
| GET | `/api/clinic/patterns` | P01–P12 模式 |
| GET | `/api/clinic/examples` | 測試案例列表 |
| POST | `/api/clinic/diagnose` | 執行診斷 |

語料來源：`marketing_plans`、`audience_packs`、`kb_products`、`competitors`、`ad_daily` 摘要、FAQ、知識庫文章。

### RAG Failure Diagnostics Clinic

上游：`clinic/`（clone from awesome-llm-apps）  
測試頁：站內導覽 **診斷診所**（`#clinic`）  
報告輸出：`clinic/reports/rag_failure_report.json`

### 架構說明頁（雙 Tutorial）

專頁：**`/explain`**（`static/explain.html`）  
涵蓋 **rag_failure_diagnostics_clinic** + **ai_travel_agent_memory**  
gimi 繁體配圖 + 架構／API／演示腳本。

| 模組 | 演示錨點 | 上游副本 | 配圖 |
|------|----------|----------|------|
| 診斷診所 | `#clinic` | `clinic/` | `static/assets/clinic/` |
| 旅遊記憶 | `#travel` | `travel_agent_memory/` | `static/assets/travel-memory/` |

長文：`clinic-architecture.md` · `travel-memory-architecture.md`

### AI Travel Agent with Memory

上游：`travel_agent_memory/`（from awesome-llm-apps）  
測試頁：站內 **旅遊記憶**（`#travel`）+ **記憶架構**（`#travel-arch`）+ **`/explain`**  
本站實作：Redis 記憶 + Qwen（原版為 Streamlit + Mem0 + Qdrant）  
架構說明：`travel-memory-architecture.md`  
gimi 配圖：`static/assets/travel-memory/`（quirky-sketch · 繁體）

| 方法 | 路徑 |
|------|------|
| POST | `/api/travel/seed` |
| GET | `/api/travel/memory` |
| DELETE | `/api/travel/memory` |
| POST | `/api/travel/chat` |
| GET | `/api/travel/history` |
