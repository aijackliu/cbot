# 2330 PA Hub · 架構說明

> 算法參考：kain26/SPX-Price-Action-Compass · futu_sr_indicator.py  
> 產品目錄：工作區 `pa-2330-hub` · 埠 `:8792` · 庫 `pa_2330`

## 一句定位

本機網頁中樞：拉 **2330.TW** K 線 → Swing＋聚類算 S/R → 落 PostgreSQL → Qwen 解讀；並探活 Ollama／FastAPI／Redis／Adminer。

## 資料流

```
yfinance 2330.TW
    → bars 表 (PG)
    → sr.compute_sr_zones (strength=4, tol=0.5% 日線)
    → sr_runs 表
    → 圖表 R1–3 / S1–3
    → Qwen system 注入快照
```

## 2330 參數

| 週期 | strength | tolerance |
|------|----------|-----------|
| 日線（預設） | 4 | 0.5% |
| 週線 | 3～4 | 0.6%～1.0% |

靠近歷史高檔時上方阻力可能為空，屬正常。

## 表結構（摘要）

| 表 | 用途 |
|----|------|
| `bars` | OHLC |
| `sr_runs` | 每次分析結果 JSON |
| `sessions` / `messages` | Qwen 對話 |
| `notes` | 備註 |

## 注意

- Swing 右側確認有 look-ahead → **看圖用**，非嚴格回測訊號  
- 除權息請用還原價（yfinance auto_adjust）  
- 與富途指標可並用：富途看盤、Hub 落庫＋AI  

## 相關

- [test0714b](../test0714b/) Cordys CRM Hub  
- [test0714a](../test0714a/) 倪海廈 Web 架構  
