# 2026-07-14｜test0714

## 記憶三層架構 · knowledge-hub · rag · Memory River

三層並聯記憶管線說明頁 + 3 張 Gimi 怪誕手繪配圖（gimi-illustration）。

| 項目 | 內容 |
|------|------|
| **線上預覽** | https://aijackliu.github.io/cbot/test0714/ |
| **頁面** | `index.html` |
| **配圖** | `assets/memory-layers/`（01–03） |
| **架構 MD** | `memory-layers-architecture.md` |
| **策略** | `assets/memory-layers/shot-config.md` |

### 三層分工

| 層 | 一句話 |
|----|--------|
| knowledge-hub | 人寫的唯一真相（SoR） |
| rag-memory-lab | 對真相找段落（證據卡） |
| Memory River | Agent 工作記憶（偏好／約定） |

宿主：**Grok**。升格單向、人確認；禁止自動雙向同步。

### 配圖

1. `01-three-layers.jpg` — 三層並聯 · 禁止混存  
2. `02-grok-routing.jpg` — 路由：門牌 / 證據 / 偏好  
3. `03-promote-checklist.jpg` — 升格不是自動同步  

靜態 HTML，無需後端。配圖風格：quirky-sketch · Gimi IP。

