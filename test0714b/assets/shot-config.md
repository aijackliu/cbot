# 配圖策略 · cordys-crm-hub

## 批次信息
| 項 | 值 |
|----|-----|
| 生成日期 | 2026-07-14 |
| $STYLE | quirky-sketch |
| $IP | gimi |
| $RATIO | 16:9 |
| $COUNT | 4 |
| 色紀律（當次） | 場景線稿為主；軟藍 ≤4 物件；軟橙 ≤2 點睛；標籤黑字黑箭頭；繁體中文 |
| 源文 | cordys-crm-hub README + 整合 Qwen/PG/Ollama/FastAPI/Redis/Cordys |
| 輸出目錄 | gimi-illustration-skill/outputs/20260714-cordys-crm-hub/ |
| 校準圖 | gimi-writing-rules-checklist.png |

## Shot List

### Shot 01 · 總覽架構
| 字段 | 內容 |
|------|------|
| **輸出文件** | `01-stack-overview.png`（已生成 · 2026-07-14） |
| **插入位置** | 架構說明文首 |
| **錨定句** | 「本機 Hub 串遠端 PG／Qwen／Ollama／FastAPI／Redis」 |
| **核心信息** | 本機網頁中樞在中心，遠端五服務環繞；官方 Cordys 虛線可選 |
| **結構軸** | 信息聚焦 |
| **構圖** | 中心主體 + 環繞服務節點 |
| **物件表意** | Hub 瀏覽器視窗、PG 資料庫罐、Qwen 對話泡泡、Ollama 模型標籤、FastAPI 閃電門、Redis 閃電匣、虛線 Docker 箱 |
| **故事動線** | 遠端服務 → 連線到中心 Hub；Gimi 站 Hub 前指路；官方 Cordys 虛線在外 |
| **標註詞** | Hub中樞 · PG · Qwen · Ollama · FastAPI · Redis · Cordys可選 |

### Shot 02 · Qwen 對話管線
| 字段 | 內容 |
|------|------|
| **輸出文件** | `02-chat-pipeline.png`（已生成 · 2026-07-14） |
| **插入位置** | 「Qwen 助理」節 |
| **錨定句** | 「CRM 快照注入 system → Qwen 回覆 → 寫入 messages」 |
| **核心信息** | 使用者訊息經 Hub 取 CRM 快照，呼叫 Qwen，結果落 PG |
| **結構軸** | 路徑序列 |
| **構圖** | 序列邏輯 3 主步 |
| **物件表意** | 使用者輸入框、CRM 客戶／商機卡片、Qwen 閘道、messages 表卷軸 |
| **故事動線** | ①輸入 → ②注入快照+呼叫 Qwen → ③存 PG；Gimi 遞 CRM 卡 |
| **標註詞** | ①輸入 · ②Qwen · ③寫入PG · CRM快照 |

### Shot 03 · 五個網頁分頁
| 字段 | 內容 |
|------|------|
| **輸出文件** | `03-five-panels.png`（已生成 · 2026-07-14） |
| **插入位置** | 「網頁分頁」節 |
| **錨定句** | 「總覽／CRM／Qwen／資料庫後台／基建」 |
| **核心信息** | 一個網頁五分頁，各管一事 |
| **結構軸** | 對比／並置 |
| **構圖** | 五格卡片橫排或 2+3 |
| **物件表意** | 燈號儀表、客戶名片、聊天泡泡、SQL 終端、伺服器機架 |
| **故事動線** | 左到右五格；Gimi 指中間 CRM |
| **標註詞** | 總覽 · CRM · Qwen · 資料庫 · 基建 |

### Shot 04 · Hub vs 官方 Cordys
| 字段 | 內容 |
|------|------|
| **輸出文件** | `04-hub-vs-official.png`（已生成 · 2026-07-14） |
| **插入位置** | 「為什麼是 Hub／官方部署」節 |
| **錨定句** | 「Hub＝PG 輕量 CRM；官方＝Docker 完整版，資料不自動同步」 |
| **核心信息** | 兩條路徑：立刻用 Hub；有 Docker 再上官方 |
| **結構軸** | 對比 |
| **構圖** | 對比並置 |
| **物件表意** | 左輕量筆記型+PG罐；右厚 Docker 箱+MySQL；中間「不自動同步」隔板 |
| **故事動線** | 左 Hub 可用 → 右官方完整；Gimi 站中間指兩邊 |
| **標註詞** | Hub立刻用 · 官方Docker · 不同步 · 可並存 |
