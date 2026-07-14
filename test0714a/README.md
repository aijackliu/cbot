# 2026-07-14｜test0714a

## 倪海廈 Web 架構 · Qwen · Postgres · Ollama

把 [nihaixia](https://github.com/jangviktor-web/nihaixia) skill 網頁化的架構說明頁 + 3 張 Gimi 怪誕手繪配圖。

| 項目 | 內容 |
|------|------|
| **線上預覽** | https://aijackliu.github.io/cbot/test0714a/ |
| **頁面** | `index.html` |
| **配圖** | `assets/`（01–03） |
| **架構 MD** | `architecture.md` |
| **策略** | `assets/shot-config.md` |

### 四端分工

| 端 | 一句話 |
|----|--------|
| 網頁 | 對話 / 知識庫 / 後台 / 基建 |
| 書庫 | 本機 skill md（真相） |
| Qwen | `:8080` 生成倪師視角 |
| Postgres + Ollama | 對話落庫 · 模型標籤 |

### 配圖

1. `01-stack-overview.jpg` — 四端並聯 · 各站其職  
2. `02-chat-pipeline.jpg` — 提問 → 摘錄 → system → Qwen → 落庫  
3. `03-four-panels.jpg` — 四頁使用地圖  

靜態 HTML，無需後端。完整可對話產品在工作區 `nihaixia-web`（`.\start.ps1` → `:8790`）。  
配圖風格：quirky-sketch · Gimi IP（[gimi-illustration-skill](https://github.com/GiMi-Xiaomi/gimi-illustration-skill)）。
