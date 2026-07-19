# Attribution

Upstream tutorial from:

- https://github.com/Shubhamsaboo/awesome-llm-apps/tree/main/advanced_llm_apps/llm_apps_with_memory_tutorials/ai_travel_agent_memory
- License: Apache-2.0 (see awesome-llm-apps LICENSE)

Original stack: Streamlit + OpenAI + Mem0 + Qdrant.

Integrated into CATCH Growth (`test0721-marketing`) as:

- Web section **旅遊記憶助理** (`#travel`)
- API under `/api/travel/*`
- Memory store: **Redis** (no Qdrant required for demo)
- LLM: Qwen OpenAI-compatible endpoint

Original Streamlit entrypoint preserved:

```bash
# needs Qdrant on :6333 and OpenAI key
streamlit run travel_agent_memory.py
```
