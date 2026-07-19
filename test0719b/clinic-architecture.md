# RAG 失敗診斷診所 · 架構與說明

> 上游：[rag_failure_diagnostics_clinic](https://github.com/Shubhamsaboo/awesome-llm-apps/tree/main/rag_tutorials/rag_failure_diagnostics_clinic)  
> 本站：`test0719b 說明頁 · 可運行 `test0721-marketing` · `#clinic`  
> 配圖：gimi-illustration · quirky-sketch · 繁體 · `assets/clinic/`

## 一句話

貼上真實 RAG／LLM 故障描述 → 對照 **P01–P12** 可複用模式 → 輸出**主因 + 最小結構修復**（不是「換更大模型」）。

## 主路徑

1. 貼上故障（範例或自寫）  
2. 診所 system prompt 載入 P01–P12  
3. Qwen 選唯一主模式 + 次要候選 + 結構修復建議  
4. 可寫入 `clinic/reports/` JSON  

## 與本站 RAG 關係

| | 行銷站 RAG | 診斷診所 |
|--|------------|----------|
| 目的 | 回答知識庫問題 | **診斷**為何答錯 |
| 儲存 | Redis 向量／KB 文檔 | 報告 JSON |
| 模型 | Ollama embed + Qwen | Qwen 分類 |

兩者**不共用**記憶；診所可診斷「本站 RAG」故障案例。
