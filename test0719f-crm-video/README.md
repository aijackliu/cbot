# CATCH CRM 架構說明片（HyperFrames）

把 [test0719d](../test0719d) 靜態說明頁做成 **約 45 秒** 16:9 影片。

- 引擎：[HyperFrames](https://github.com/heygen-com/hyperframes)（HTML → MP4）
- 素材：`test0719d/assets/crm` 四張 gimi 配圖

## 預覽

```powershell
cd F:\grok\3\cbot\test0719f-crm-video
npm run dev
```

瀏覽器開啟 CLI 印出的預覽網址。

## 渲染

本機 FFmpeg **無 libx264** 時，請用 WebM（已驗證成功）：

```powershell
cd F:\grok\3\cbot\test0719f-crm-video
npx hyperframes@0.7.64 render --format webm -o renders/crm-architecture.webm
```

已產出：

```text
renders/crm-architecture.webm   # 約 45s · 4.2 MB · 1920×1080
```

若之後裝了完整 FFmpeg（含 libx264），可直接：

```powershell
npm run render
# 或
npx hyperframes@0.7.64 render --format mp4
```

## 檢查

```powershell
npm run check
```

## 場景結構

| 秒 | 內容 |
|----|------|
| 0–7 | 標題：客服總線 + 多庫 RAG |
| 6.5–15.5 | ① LAN 基建 |
| 15–24 | ② 客服多模態 |
| 23.5–32.5 | ③ 知識庫路由 |
| 32–40 | ④ mmrag · HyDE · 垂直 |
| 39.5–45 | 怎麼開（埠與路徑） |
