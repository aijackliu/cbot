# 2026-07-15｜test0715a

## CATCH 經營戰情中心 · 公司總指揮台

在 [test0715](../test0715/) CRM 四水管之上，加上**經營戰情**：官網銷售＋廣告＋月度財報整合、異常洞察、月結快照可追溯整年。

| 項目 | 內容 |
|------|------|
| **線上預覽** | https://aijackliu.github.io/cbot/test0715a/ |
| **頁面** | `index.html` |
| **假資料** | `assets/war-room.json` · `showcase.json` · `sales.json` |
| **架構** | `architecture.md` |
| **可執行本體** | 工作區 `catch-crm-hub` → `http://127.0.0.1:8791/` 分頁「經營戰情」 |

### 六大模組

| 模組 | 說明 |
|------|------|
| **經營戰情中心** | 總指揮台：KPI、異常、廣告 ROAS、月結快照 |
| **官網銷售分析** | 訂單、回購、客群、品項 |
| **月度趨勢／熱力／潛力流失** | 趨勢、SKU 熱力矩陣、潛力與流失名單 |
| **報表分析（財務）** | 月度 P&L、營收 YoY |
| **年度行銷企劃** | 四季焦點、預算、KPI |
| **官網顧客輪廓** | RFM 分層、高 LTV TOP |

### 本機跑完整版

```powershell
cd J:\grok\34\catch-crm-hub
pip install -r requirements.txt
python setup_postgres.py
python seed_demo.py --force
# 經營戰情示範（官網訂單／財報／快照）
# 或網頁「經營戰情 → 灌入示範數據」
python -c "import war_room_center as w; print(w.seed_war_room(force=True))"
python server.py
# http://127.0.0.1:8791/ → 分頁「經營戰情」
```

| API | 用途 |
|-----|------|
| `GET /api/war-room` | 總指揮台一次打包 |
| `GET /api/war-room/website-sales` | 官網銷售 |
| `GET /api/war-room/trends` | 趨勢／熱力／潛力流失 |
| `GET /api/war-room/finance` | 財務月報 |
| `GET /api/war-room/marketing-plan` | 年度企劃 |
| `GET /api/war-room/customers` | 顧客輪廓 |
| `POST /api/war-room/seed` | 灌示範數據 |

靜態頁無需後端；完整 CRUD／Qwen／即時查詢需本機 Hub。
