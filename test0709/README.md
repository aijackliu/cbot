# 軸心 AI 檢測 · 靜態版 v0513best

免後端。內嵌 **16** 張真實 `0513best.pt`（imgsz=1024）推論結果。

## 預覽

```bash
cd static-export-v0513best
python -m http.server 8080
```

開啟 http://127.0.0.1:8080

或直接雙擊 `index.html`（部分瀏覽器對本地圖路徑較嚴，建議用 http.server）。

## 重新匯出

```bash
python scripts/export_static_html.py
```

## 頁面

| 檔案 | 說明 |
|------|------|
| index.html | 首頁 |
| inspection.html | 檢測（可翻頁看原圖/結果） |
| stats.html / analysis.html / suggestions.html | 統計分析 |
| judgment.html / admin.html / infra.html / retrain.html / notifications.html | 其他 |

匯出時間：2026-07-09T12:08:55.933237Z
