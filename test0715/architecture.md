# CATCH CRM · 架構（test0715）

## 一句話

**自有 CATCH CRM** 為公司數位核心；廣告／B 端告警／客服是進水管；戰情只讀匯總。不要官方 Cordys 映像。

## 元件

| 元件 | 角色 |
|------|------|
| CATCH CRM Hub (`catch-crm-hub`) | 網頁 UI + API :8791 |
| PostgreSQL `catch_crm` | 客戶／商機／活動／對話 |
| Qwen :8080 | 銷售助理（注入 CRM 快照） |
| Ollama / Redis / FastAPI | 基建探活（可選） |

## 資料流

| 來源 | 寫入 CRM |
|------|----------|
| FB 廣告建檔／對帳 | opportunity.source + activity(kind=ad) |
| B 端 09:00 告警 | activity(kind=alert)；人認領改 stage |
| LINE 客服草稿 | activity(kind=cs)；升級建商機 |
| 新戶表單 | account |
| 戰情／中控 | **只讀** |

## 與 35 套系統

編制成約 **12 條管線**（見 knowledge-hub `2026-07-15-CRM核心-35套配合與裁撤.md`）。  
對外不講 35 個互不相干系統。
