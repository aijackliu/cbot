# CATCH 經營戰情 · 架構（test0715a）

## 一句話

**公司總指揮台**：把官網銷售、廣告 ROAS、月度財報、年度行銷企劃、顧客輪廓接到同一頁；異常自動浮出；月結快照可追溯整年。

## 與 test0715 的關係

| 層 | test0715 | test0715a |
|----|----------|-----------|
| CRM 核心 | 客戶／商機／四水管 | 同左（仍是真相源） |
| 新增 | — | 經營戰情分析層 |
| 資料 | showcase 假 feeds | + web_orders／finance／snapshots |

```text
                    【經營戰情中心 · 總指揮台】
         KPI · 異常洞察 · 廣告 ROAS · 月結快照（12 月）
                              │
     ┌────────────┬───────────┼───────────┬────────────┐
  官網銷售     趨勢熱力     財務月報    年度企劃    顧客輪廓
  回購/品項   潛力/流失    P&L YoY    Q1–Q4 KPI   RFM/LTV
                              │
                    【CATCH CRM 核心】
              客戶 · 商機 · 活動 · 銷售 YoY
                    戰情 · 告警 · 客服 · 廣告
```

## 表（PostgreSQL `catch_crm`）

| 表 | 用途 |
|----|------|
| `web_customers` | 官網顧客、segment、RFM、LTV |
| `web_orders` | 訂單、品項 JSON、回購標記 |
| `ad_daily` | 廣告日花費／轉換／歸因營收 |
| `finance_monthly` | 月度財報 |
| `marketing_plans` | 年度行銷企劃 |
| `war_room_snapshots` | 月結快照 + anomalies |

## 可執行

工作區：`catch-crm-hub/war_room_center.py` + `server.py` 路由 `/api/war-room*`。  
Hub UI 分頁：**經營戰情**。
