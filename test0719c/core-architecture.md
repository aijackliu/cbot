# CATCH Growth · 核心架構說明

> 對象：`行銷站核心（CATCH Growth）` 行銷站本體  
> **不含** `ai_travel_agent_memory`、`rag_failure_diagnostics_clinic`  
> 說明頁：本頁 index.html · 配圖：`assets/core/` · gimi 繁體

## 一句話

**真實 CRM 表驅動行銷看板**，加上 **Qwen 文案** 與 **Ollama 知識庫 RAG**，全部經本機 FastAPI 連到 LAN 服務。

## 三張配圖

| 檔案 | 主題 |
|------|------|
| `01-stack-overview.jpg` | LAN：FastAPI · Postgres · Redis · Qwen · Ollama |
| `02-metrics-board.jpg` | 庫表 → 看板 → 詢盤 |
| `03-ai-rag.jpg` | AI 文案 × 知識庫 RAG |

## 主路徑

### 看板

```text
#metrics → /api/marketing/overview → Postgres → Redis cache → KPI
```

### AI 文案

```text
#ai → /api/ai/copy → Qwen → 文案
```

### RAG

```text
語料（PG + 內部文章）→ /api/rag/rebuild → Redis 向量
提問 → /api/rag/ask → embed 檢索 → 生成
```

## 邊界

| 在核心內 | 不在本頁 |
|----------|----------|
| 落地頁、方案、案例、詢盤 | 旅遊記憶 Tutorial |
| 團隊、知識庫、RAG | 診斷診所 P01–P12 |
| 基建探測 | — |

## 啟動

```powershell
cd 行銷站核心（CATCH Growth）
.\start.ps1
```

瀏覽器：http://127.0.0.1:18721/ · 架構：http://127.0.0.1:18721/core-explain
