"""
RAG Failure Diagnostics Clinic — integrated service layer.

Adapted from:
https://github.com/Shubhamsaboo/awesome-llm-apps/tree/main/rag_tutorials/rag_failure_diagnostics_clinic
Apache-2.0. Interactive CLI remains in clinic/; this module is API-friendly.
"""

from __future__ import annotations

import json
import re
import textwrap
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from . import config

# Re-export pattern library (kept in sync with upstream PATTERNS)
PATTERNS = [
    {
        "id": "P01",
        "name": "Retrieval hallucination / grounding drift",
        "summary": "Answer confidently contradicts or ignores retrieved documents.",
    },
    {
        "id": "P02",
        "name": "Chunk boundary or segmentation bug",
        "summary": "Relevant facts are split, truncated, or mis-grouped across chunks.",
    },
    {
        "id": "P03",
        "name": "Embedding mismatch / semantic vs vector distance",
        "summary": "Vector similarity does not match true semantic relevance.",
    },
    {
        "id": "P04",
        "name": "Index skew or staleness",
        "summary": "Index returns old or missing data relative to the source of truth.",
    },
    {
        "id": "P05",
        "name": "Query rewriting or router misalignment",
        "summary": "Router or rewriter sends queries to the wrong tool or dataset.",
    },
    {
        "id": "P06",
        "name": "Long-chain reasoning drift",
        "summary": "Multi-step tasks gradually forget earlier constraints or goals.",
    },
    {
        "id": "P07",
        "name": "Tool-call misuse or ungrounded tools",
        "summary": "Tools are called with wrong arguments or without proper grounding.",
    },
    {
        "id": "P08",
        "name": "Session memory leak / missing context",
        "summary": "Conversation loses important facts between turns or sessions.",
    },
    {
        "id": "P09",
        "name": "Evaluation blind spots",
        "summary": "System passes tests but fails on real incidents or edge cases.",
    },
    {
        "id": "P10",
        "name": "Startup ordering / dependency not ready",
        "summary": "Services crash or return 5xx during the first minutes after deploy.",
    },
    {
        "id": "P11",
        "name": "Config or secrets drift across environments",
        "summary": "Works locally but breaks in staging or production because of settings.",
    },
    {
        "id": "P12",
        "name": "Multi-tenant or multi-agent interference",
        "summary": "Requests or agents overwrite each other’s state or resources.",
    },
]

EXAMPLE_1 = """=== Example 1 — retrieval hallucination (P01 style) ===

Context:
You have a simple RAG chatbot that answers questions from a product FAQ.
The FAQ only covers billing rules for your SaaS product and does NOT mention anything about cryptocurrency.

User prompt:
"Can I pay my subscription with Bitcoin?"

Retrieved context (from vector store):
- "We only accept major credit cards and PayPal."
- "All payments are processed in USD."

Model answer:
"Yes, you can pay with Bitcoin. We support several cryptocurrencies through a third-party payment gateway."

Logs:
No errors. Retrieval shows the FAQ chunks above, but the model still confidently invents Bitcoin support.
"""

EXAMPLE_2 = """=== Example 2 — startup ordering / dependency not ready (P10 style) ===

Context:
You have a RAG API with three services: api-gateway, rag-worker, and vector-db (for example Qdrant or FAISS).
In local docker compose everything works.

Deployment:
In production, services are deployed on Kubernetes.

Symptom:
Right after a fresh deploy, api-gateway returns 500 errors for the first few minutes.
Logs show connection timeouts from api-gateway to vector-db.

After a few minutes, the errors disappear and the system behaves normally.
You suspect a startup race between api-gateway and vector-db but are not sure how to fix it properly.
"""

EXAMPLE_3 = """=== Example 3 — config or secrets drift (P11 style) ===

Context:
You added a new environment variable for the RAG pipeline: SECRET_RAG_KEY.
This is required by middleware that signs outgoing requests to an internal search API.

Local:
On developer machines, SECRET_RAG_KEY is defined in .env and everything works.

Production:
You deployed a new version but forgot to add SECRET_RAG_KEY to the production environment.
The first requests after deploy fail with 500 errors and "missing secret" messages in the logs.

After hot-patching the secret into production, the errors stop.
However, similar "first deploy breaks because of missing config" incidents keep happening.
"""

# CATCH marketing RAG demo incident (local stack)
EXAMPLE_CATCH = """=== Example CATCH — marketing site RAG (P04 / P01 style) ===

Context:
CATCH Growth marketing demo (test0721-marketing).
Stack: FastAPI BFF, PostgreSQL catch_crm, Redis vector index, Ollama qwen3-embedding:0.6b + qwen3:latest.
Knowledge sources: marketing_plans, audience_packs, kb_products, competitors, FAQ, Redis KB articles.

Incident:
Ops updated marketing_plans.theme and budget_ntd in Postgres.
Users asked RAG "今年行銷預算是多少？" and still received the old number.
/api/rag/search still ranks an old FAQ chunk high; /api/rag/rebuild was not run after DB update.
Sometimes the model also adds extra claims not present in retrieved hits.

Question for clinic:
Classify the primary failure pattern and give a minimal structural fix for this stack.
"""

EXAMPLES = {
    "1": {"id": "1", "title": "檢索幻覺 (P01)", "bug": EXAMPLE_1},
    "2": {"id": "2", "title": "啟動順序 / 依賴未就緒 (P10)", "bug": EXAMPLE_2},
    "3": {"id": "3", "title": "設定 / Secret 漂移 (P11)", "bug": EXAMPLE_3},
    "catch": {
        "id": "catch",
        "title": "CATCH 行銷站 RAG（未重建索引）",
        "bug": EXAMPLE_CATCH,
    },
}

REPORT_DIR = Path(__file__).resolve().parent.parent / "clinic" / "reports"


def build_system_prompt() -> str:
    header = """
You are an assistant that triages failures in LLM + RAG pipelines.

You have a library of reusable failure patterns P01–P12.
For each bug description, you must:

1. Choose exactly ONE primary pattern id from P01–P12.
2. Optionally choose up to TWO secondary candidate pattern ids.
3. Explain your reasoning in clear bullet points.
4. Propose a MINIMAL structural fix:
   - changes to retrieval, indexing, routing, evaluation, tooling, or infra
   - avoid generic advice like "add more context" or "use a better model"

You are not allowed to invent new pattern ids.
Always select from the patterns listed below.

Prefer Traditional Chinese for the final report sections when the bug text is Chinese,
but keep pattern IDs (P01–P12) in English form.

Return your answer as structured Markdown with the following sections:

- Primary pattern
- Secondary candidates (optional)
- Reasoning
- Minimal structural fix
"""
    pattern_lines = [
        f"{p['id']}: {p['name']} — {p['summary']}" for p in PATTERNS
    ]
    return textwrap.dedent(header).strip() + "\n\nFailure patterns:\n" + "\n".join(
        pattern_lines
    )


def _extract_reply(message: dict) -> str:
    content = (message.get("content") or "").strip()
    if content:
        return content
    reason = message.get("reasoning_content") or ""
    cands = re.findall(r"[\u4e00-\u9fff][^。！？\n]{10,200}[。！？]", reason)
    if cands:
        return "\n".join(cands[-8:])
    # Prefer markdown-ish tail
    if reason.strip():
        return reason.strip()[-2500:]
    return "（模型未回傳可視內容，請提高 max_tokens 後重試）"


def diagnose(bug_description: str, max_tokens: int = 1200) -> dict[str, Any]:
    bug = (bug_description or "").strip()
    if not bug:
        raise ValueError("bug_description is empty")

    system_prompt = build_system_prompt()
    payload = {
        "model": config.QWEN_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    "Here is the bug description. "
                    "Follow the pattern rules described above.\n\n" + bug
                ),
            },
        ],
        "temperature": 0.2,
        "max_tokens": max_tokens,
    }
    req = urllib.request.Request(
        config.QWEN_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Qwen HTTP {e.code}: {err[:500]}") from e

    choice = (raw.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    reply = _extract_reply(message)
    model_name = raw.get("model") or config.QWEN_MODEL

    report = {
        "bug_description": bug,
        "model": model_name,
        "assistant_markdown": reply,
        "usage": raw.get("usage"),
        "finish_reason": choice.get("finish_reason"),
        "source": "rag_failure_diagnostics_clinic",
        "upstream": "https://github.com/Shubhamsaboo/awesome-llm-apps/tree/main/rag_tutorials/rag_failure_diagnostics_clinic",
    }

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORT_DIR / "rag_failure_report.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    return {
        **report,
        "report_path": str(out_path),
        "patterns": PATTERNS,
    }


def list_examples() -> list[dict[str, str]]:
    return [
        {"id": v["id"], "title": v["title"], "preview": v["bug"][:220]}
        for v in EXAMPLES.values()
    ]


def get_example(example_id: str) -> str | None:
    item = EXAMPLES.get(example_id)
    return item["bug"] if item else None
