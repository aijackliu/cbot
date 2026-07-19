# CATCH CRM 展示台 · 架構說明

> 對象：`test0720-crm`（埠 **18720**）  
> 說明頁：`index.html` · 配圖：`assets/crm/` · gimi quirky-sketch 繁體說明

## 一句話

**真實 Postgres CRM 表 + Redis 記憶／索引 + LAN Qwen + Gemini 視聽**，  
經本機 FastAPI 串成：**客服多模態總線**、**知識庫路由**、**多模態／Wiki／農業／收據** 垂直能力。

## 四張配圖

| 檔案 | 主題 |
|------|------|
| `01-stack-overview.jpg` | LAN：FastAPI · Postgres · Redis · Qwen · Gemini |
| `02-cs-multimodal.jpg` | 文字 · 表單 · 麥克風 → 客服總線 |
| `03-kb-routing.jpg` | 一問多庫路由 + 弱命中回退 |
| `04-mmrag-hyde.jpg` | 多模態索引 + HyDE 檢索 |

## 主路徑

### 基建

```text
瀏覽器 → FastAPI :18720
  → Postgres 100.88.220.82:5432 / catch_crm
  → Redis :6379
  → Qwen :8080/v1/chat/completions
  → Gemini (Google AI Studio) 視聽
```

### 客服總線

```text
文字 | 表單 | 🎤 STT(Gemini)
  → mode: 知識庫路由 | 部門路由 | 記憶 | SQL | 填表 | CRM
```

### 知識庫路由

```text
POST /api/cs/kb-route
  classify → support | mmrag | wikiband | sql | agri | crm | form
  弱檢索 → 回退 support FAQ
```

### 多模態 RAG

```text
文字/URL/圖/音 → Redis chunks
可選 HyDE：假想答案 × N → 向量平均 → top-k → Gemini 回答
```

## 側欄地圖

| 分頁 | 能力 |
|------|------|
| 儀表板…競品 | Postgres CRM 展示 |
| 客服 AI | 多模態 + 知識庫路由 |
| 多模態 RAG | mmrag + HyDE |
| 農業客戶 | 天氣／作物／新聞工具 |
| Wiki 樂團 | Wikipedia + BM25 |
| 收據費用 | Gemini 識圖 + PG 帳本 |
| 基礎設施 | 連線探測 |

## 啟動

```powershell
cd test0720-crm
.\start.ps1
```

- 展示台：http://127.0.0.1:18720/  
- 本架構說明（靜態）：開啟 `test0719d/index.html`  
- 或 CRM 內：http://127.0.0.1:18720/crm-explain  
