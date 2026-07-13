# 2026-07-13｜AI 眼鏡

功能盤點與時序圖素材（對照 `work0601`：glasses_app + glasses_backend）。

## 檔案

| 路徑 | 說明 |
|------|------|
| `AI眼鏡-定位與三航道PRD.md` | **產品定位 + 三航道 PRD**（決策／執行入口） |
| `AI眼鏡-定位與三航道-圖表.html` | PRD 視覺圖表板（瀏覽器開啟／可列印） |
| `AI眼鏡-功能盤點報告.docx` | 功能盤點報告（程式碼對照版） |
| `時序圖/` | 各功能呼叫鏈 sequence diagram |

## 時序圖對照

| 檔名 | 功能 | 主路徑 |
|------|------|--------|
| `01-天氣-直查API.png` | 查天氣（直打） | `GET /weather/current` |
| `02-天氣-語音意圖.png` | 查天氣（語音） | `POST /api/intents/parse` → get_weather |
| `03-星座運勢.png` | 星座運勢 | intents → HOROSCOPE_PROMPT stream |
| `04-食材辨識.png` | 食材辨識 | `POST /api/visual/ingredient` |
| `05-菜單翻譯.png` | 菜單翻譯 | intents + `POST /api/visual/menu-translate` |
| `06-三餐營養.png` | 三餐／飲食 | `/visual/nutrition` → `/diet/logs` |
| `07-商品比價.png` | 商品比價 | intents + `POST /api/visual/shopping` |
| `08-文件掃描OCR.png` | 文件掃描 | `POST /visual/doc-scan` |
| `09-行事曆.png` | 行事曆 | action → DeviceCalendar |
| `10-植物辨識.png` | 植物辨識 | `POST /api/visual/nature` |
| `11-景點介紹.png` | 景點介紹 | `POST /api/visual/sightseeing` |
| `12-海報人物Wiki.png` | 海報／人物 | `POST /api/visual/person` + Wiki |

## 整理備註

- 原 13 張「無標題」截圖已依功能重命名並收入 `時序圖/`。
- `無標題 (6).png` 與 `(7).png` 內容相同（商品比價），已刪除重複。
