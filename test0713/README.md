# 2026-07-13｜test0713

## A. Headless SaaS · a16z 對談筆記（網頁）

AI Agent 時代 SaaS／Headless Software 濃縮頁 + 5 張怪誕手繪配圖。

| 項目 | 內容 |
|------|------|
| **線上預覽** | https://aijackliu.github.io/cbot/test0713/headless-saas.html |
| **頁面** | `headless-saas.html` |
| **配圖** | `assets/headless-saas/`（01–05） |
| **筆記 MD** | `a16z-Headless-Software-AI-Agent-SaaS.md` |
| **策略** | `assets/headless-saas/shot-config.md` |

靜態 HTML，無需後端。點圖可放大。

---

## B. AI 眼鏡

功能盤點與時序圖素材（對照 `work0601`：glasses_app + glasses_backend）。

| 路徑 | 說明 |
|------|------|
| `AI眼鏡-定位與三航道PRD.md` | 產品定位 + 三航道 PRD |
| `AI眼鏡-定位與三航道-圖表.html` | PRD 視覺圖表板 |
| `AI眼鏡-功能盤點報告.docx` | 功能盤點報告 |
| `時序圖/` | 各功能呼叫鏈 sequence diagram |

### 時序圖對照

| 檔名 | 功能 | 主路徑 |
|------|------|--------|
| `01-天氣-直查API.png` | 查天氣（直打） | `GET /weather/current` |
| `02-天氣-語音意圖.png` | 查天氣（語音） | `POST /api/intents/parse` → get_weather |
| `03-星座運勢.png` | 星座運勢 | intents → HOROSCOPE_PROMPT stream |
| `04-食材辨識.png` | 食材辨識 | `POST /api/visual/ingredient` |
| `05-菜單翻譯.png` | 菜單翻譯 | intents + menu-translate |
| `06-三餐營養.png` | 三餐／飲食 | nutrition → diet/logs |
| `07-商品比價.png` | 商品比價 | shopping |
| `08-文件掃描OCR.png` | 文件掃描 | doc-scan |
| `09-行事曆.png` | 行事曆 | DeviceCalendar |
| `10-植物辨識.png` | 植物辨識 | nature |
| `11-景點介紹.png` | 景點介紹 | sightseeing |
| `12-海報人物Wiki.png` | 海報／人物 | person + Wiki |
