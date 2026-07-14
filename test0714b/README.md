# 2026-07-14｜test0714b

## Cordys CRM Hub 架構 · Qwen · PG · FastAPI · Redis · Ollama

整合 [CordysCRM](https://github.com/1Panel-dev/CordysCRM) 生態與 tailnet 基建的網頁中樞說明頁 + **4 張** Gimi 怪誕手繪配圖。

| 項目 | 內容 |
|------|------|
| **線上預覽** | https://aijackliu.github.io/cbot/test0714b/ |
| **頁面** | `index.html` |
| **配圖** | `assets/`（01–04） |
| **架構 MD** | `architecture.md` |
| **策略** | `assets/shot-config.md` |

### 服務地圖

| 服務 | 端點 |
|------|------|
| Hub | `127.0.0.1:8791`（本機） |
| Qwen | `:8080/v1/chat/completions` |
| Ollama | `:11434/api/tags` |
| FastAPI | `:9000` glasses_backend |
| Redis | `:6379` |
| PostgreSQL | `:5432` / `cordys_hub` |
| Adminer | `:5050` |
| 官方 Cordys（可選） | `:8081` Docker |

### 配圖

1. `01-stack-overview.jpg` — Hub 中樞與周邊服務  
2. `02-chat-pipeline.jpg` — 輸入 → Qwen＋CRM 快照 → 寫入 PG  
3. `03-five-panels.jpg` — 總覽／CRM／Qwen／資料庫／基建  
4. `04-hub-vs-official.jpg` — Hub 立刻用 vs 官方 Docker（不同步）  

靜態 HTML，無需後端。完整可跑產品在工作區 `cordys-crm-hub`（`.\start.ps1` → `:8791`）。  
配圖風格：quirky-sketch · Gimi IP（[gimi-illustration-skill](https://github.com/GiMi-Xiaomi/gimi-illustration-skill)）。
