# Attribution

This folder contains the upstream **RAG Failure Diagnostics Clinic** tutorial from:

- https://github.com/Shubhamsaboo/awesome-llm-apps/tree/main/rag_tutorials/rag_failure_diagnostics_clinic
- License: Apache-2.0 (see upstream LICENSE)

Integrated into CATCH Growth demo (`test0721-marketing`) as:

- Web UI section **診斷診所** (`#clinic`)
- API `POST /api/clinic/diagnose` via `app/clinic.py`
- Default model: Qwen OpenAI-compatible endpoint (`QWEN_URL`)

Original CLI entrypoint preserved: `python clinic/rag_failure_diagnostics_clinic.py`
