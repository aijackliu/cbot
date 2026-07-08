# 軸心 AI 檢測系統 — 靜態展示版

純 HTML/CSS/JS 介面展示，**無需後端伺服器**，所有資料為固定示意，適合放上 GitHub Pages 給客戶預覽 UI。

## 線上預覽（GitHub Pages）

1. 本目錄已置於 [cbot](https://github.com/aijackliu/cbot) 儲存庫的 `test0708/` 路徑
2. GitHub Pages 啟用後造訪：`https://aijackliu.github.io/cbot/test0708/`

## 本機預覽

直接用瀏覽器開啟 `index.html`，或使用簡易伺服器：

```bash
cd test0708
python -m http.server 8080
```

開啟 http://127.0.0.1:8080

## 頁面一覽

| 檔案 | 說明 |
|------|------|
| `index.html` | 首頁 |
| `inspection.html` | 檢測流程（批次完成狀態） |
| `judgment.html` | 判定參數設定 |
| `stats.html` | 統計 |
| `analysis.html` | 數據分析 |
| `suggestions.html` | AI 建議 |
| `notifications.html` | 通知 |
| `admin.html` | 系統管理 |
| `retrain.html` | 重新訓練總覽 |
| `retrain-dataset.html` | 選擇訓練資料 |
| `retrain-train.html` | 模型訓練（完成狀態） |

## 固定示意資料

- 機台：`MC-AOI-01`
- 工單：`WO-2026-001`
- 批次：`BATCH-DEMO-01`
- 檢測：120 組 / OK 100 / NG 20 / 合格率 83.3%
- 通知 Email：`qc@example.com`、`alert@factory.tw`

修改資料請編輯 `js/mock-data.js`。

## 與完整版的差異

| 項目 | 完整版 (`python run.py`) | 展示版 (`test0708`) |
|------|-------------------------|------------------------|
| 後端 API | 有 | 無 |
| 批次檢測 | 可實際執行 | 固定完成狀態 |
| 儲存/刪除 | 可寫入 DB | 按鈕僅提示展示 |
| 影像 | 合成樣本圖 | SVG 示意圖 |

完整操作說明見 `../docs/操作手冊.md`。