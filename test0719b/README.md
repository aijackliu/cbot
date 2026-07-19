# test0719b · 雙 Tutorial 架構說明網頁

靜態說明頁：整合 awesome-llm-apps 兩則 tutorial，配 **gimi 繁體手繪**與架構說明。

| 模組 | 上游 |
|------|------|
| RAG 失敗診斷診所 | [rag_failure_diagnostics_clinic](https://github.com/Shubhamsaboo/awesome-llm-apps/tree/main/rag_tutorials/rag_failure_diagnostics_clinic) |
| AI 旅遊助理（記憶） | [ai_travel_agent_memory](https://github.com/Shubhamsaboo/awesome-llm-apps/tree/main/advanced_llm_apps/llm_apps_with_memory_tutorials/ai_travel_agent_memory) |

## 線上預覽

- GitHub 目錄：https://github.com/aijackliu/cbot/tree/main/test0719b  
- Pages（若已開）：https://aijackliu.github.io/cbot/test0719b/

## 本機開啟

直接開 `index.html`，或：

```bash
# 在 cbot 根目錄
npx --yes serve test0719b -p 41719
```

## 檔案

| 路徑 | 說明 |
|------|------|
| `index.html` | 說明網頁主檔 |
| `styles.css` / `explain.css` | 樣式 |
| `assets/clinic/` | 診所 3 張 gimi 圖 |
| `assets/travel-memory/` | 旅遊記憶 3 張 gimi 圖 |
| `clinic-architecture.md` | 診所架構短文 |
| `travel-memory-architecture.md` | 旅遊記憶架構長文 |

## 可運行演示

互動 API／UI 在 **`../test0721-marketing/`**（FastAPI · Redis · Qwen）。  
本目錄為**純靜態**對外講解頁，不需後端。

## 配圖

[gimi-illustration-skill](https://github.com/GiMi-Xiaomi/gimi-illustration-skill) · quirky-sketch · IP gimi · 繁體標註。  
IP 使用請遵守 skill 倉 `IP-NOTICE.md`。
