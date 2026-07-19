# CATCH Growth · 行銷網站展示（test0721-marketing）

整合遠端：

| 服務 | 位址 |
|------|------|
| Qwen | `http://100.88.220.82:8080/v1/chat/completions` |
| FastAPI | `http://100.88.220.82:9000`（glasses_backend，狀態探測） |
| Redis | `100.88.220.82:6379` |
| PostgreSQL | `100.88.220.82:5432` / `catch_crm` |

## 啟動

```powershell
cd test0721-marketing
.\start.ps1
```

瀏覽器：http://127.0.0.1:18721/

## 功能

- 行銷落地頁（Hero／方案／案例／詢盤）
- 真實表：`ad_daily`、`marketing_plans`、`audience_packs`、`form_submissions` 等
- Redis：文案種子、dashboard 快取
- Qwen：行銷文案生成
- 啟動時自動 seed 假證言／方案／補充詢盤
