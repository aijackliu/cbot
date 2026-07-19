from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import redis
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config
from . import form_fill
from . import sql_agent
from . import support_memory as csmem
from . import query_router
from . import agri_agent
from . import receipt_expense
from . import cs_audio
from . import mm_rag
from . import wiki_band_rag
from . import kb_router
from .db import fetch_all, fetch_one, json_safe

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(title="CATCH CRM Demo", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _redis() -> redis.Redis:
    return redis.Redis(
        host=config.REDIS_HOST,
        port=config.REDIS_PORT,
        socket_connect_timeout=2,
        decode_responses=True,
    )


def _http_get(url: str, timeout: float = 4.0) -> tuple[bool, str, Any]:
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                data = body[:200]
            return True, f"HTTP {resp.status}", data
    except Exception as e:  # noqa: BLE001
        return False, str(e), None


def _extract_qwen_text(message: dict) -> str:
    content = (message.get("content") or "").strip()
    if content:
        return content
    reason = message.get("reasoning_content") or ""
    # Prefer final-looking Chinese sentences from reasoning models
    candidates = re.findall(
        r"[\u4e00-\u9fff][^。！？\n]{6,80}[。！？]",
        reason,
    )
    if candidates:
        return candidates[-1].strip()
    # Code-fence style final answers
    m = re.search(r"`([^`\n]{8,120})`", reason)
    if m and re.search(r"[\u4e00-\u9fff]", m.group(1)):
        return m.group(1).strip()
    if reason.strip():
        return reason.strip()[-400:]
    return "（模型未回傳可視內容，請提高 max_tokens 或稍後重試）"


class ChatIn(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    context: str | None = None


class FormTurnIn(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    values: dict[str, str] | None = None
    history: list[dict] | None = None
    session_id: str | None = None


class FormSubmitIn(BaseModel):
    values: dict[str, str]
    session_id: str | None = None


class SqlAskIn(BaseModel):
    question: str = Field(..., min_length=2, max_length=2000)


class CsMemIn(BaseModel):
    customer_id: str = Field(..., min_length=1, max_length=64)
    text: str | None = Field(None, max_length=800)


class CsChatIn(BaseModel):
    customer_id: str = Field(..., min_length=1, max_length=64)
    message: str = Field(..., min_length=1, max_length=4000)


class CsRouteIn(BaseModel):
    customer_id: str = Field("Alex", min_length=1, max_length=64)
    message: str = Field(..., min_length=1, max_length=4000)


class CsKbRouteIn(BaseModel):
    customer_id: str = Field("Alex", min_length=1, max_length=64)
    message: str = Field(..., min_length=1, max_length=4000)


class AgriAskIn(BaseModel):
    question: str = Field(..., min_length=2, max_length=2000)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "service": "catch-crm-demo"}


@app.get("/api/infra/status")
def infra_status() -> dict:
    """Probe Qwen, remote FastAPI, Redis, PostgreSQL."""
    services: dict[str, Any] = {}

    # Qwen / llama.cpp
    ok, detail, data = _http_get("http://100.88.220.82:8080/v1/models", timeout=5)
    model_id = None
    if ok and isinstance(data, dict):
        arr = data.get("data") or data.get("models") or []
        if arr:
            model_id = arr[0].get("id") or arr[0].get("model") or arr[0].get("name")
    services["qwen"] = {
        "url": config.QWEN_URL,
        "ok": ok,
        "detail": detail,
        "model": model_id or config.QWEN_MODEL,
    }

    # Remote glasses FastAPI
    ok, detail, data = _http_get(f"{config.REMOTE_FASTAPI}/health", timeout=4)
    services["remote_fastapi"] = {
        "url": config.REMOTE_FASTAPI,
        "ok": ok,
        "detail": detail,
        "health": data,
        "note": "glasses_backend（視覺／天氣等 API，非 CRM 核心）",
    }

    # Redis
    try:
        r = _redis()
        t0 = time.time()
        pong = r.ping()
        r.setex("crm:demo:heartbeat", 120, str(int(time.time())))
        services["redis"] = {
            "url": f"redis://{config.REDIS_HOST}:{config.REDIS_PORT}",
            "ok": bool(pong),
            "detail": f"ping {round((time.time() - t0) * 1000)}ms",
            "keys_sample": r.dbsize(),
        }
    except Exception as e:  # noqa: BLE001
        services["redis"] = {
            "url": f"redis://{config.REDIS_HOST}:{config.REDIS_PORT}",
            "ok": False,
            "detail": str(e),
        }

    # PostgreSQL catch_crm
    try:
        t0 = time.time()
        row = fetch_one("SELECT current_database() AS db, now() AS ts")
        counts = {}
        for table in (
            "accounts",
            "opportunities",
            "web_customers",
            "web_orders",
            "activities",
            "competitors",
            "receipt_expenses",
        ):
            try:
                c = fetch_one(f'SELECT COUNT(*)::int AS n FROM "{table}"')
                counts[table] = c["n"] if c else 0
            except Exception:  # noqa: BLE001
                counts[table] = None
        services["postgresql"] = {
            "url": f"postgresql://{config.PG_HOST}:{config.PG_PORT}/{config.PG_DB}",
            "ok": True,
            "detail": f"query {round((time.time() - t0) * 1000)}ms",
            "database": row["db"] if row else config.PG_DB,
            "counts": counts,
        }
    except Exception as e:  # noqa: BLE001
        services["postgresql"] = {
            "url": f"postgresql://{config.PG_HOST}:{config.PG_PORT}/{config.PG_DB}",
            "ok": False,
            "detail": str(e),
        }

    all_ok = all(s.get("ok") for s in services.values())
    return {"ok": all_ok, "services": services}


@app.get("/api/dashboard")
def dashboard() -> dict:
    cache_key = "crm:demo:dashboard"
    try:
        r = _redis()
        cached = r.get(cache_key)
        if cached:
            data = json.loads(cached)
            data["cache"] = "hit"
            return data
    except Exception:  # noqa: BLE001
        r = None

    accounts = fetch_one("SELECT COUNT(*)::int AS n FROM accounts")
    opps = fetch_one(
        """
        SELECT COUNT(*)::int AS n,
               COALESCE(SUM(amount_ntd),0)::bigint AS pipeline
        FROM opportunities
        WHERE stage IS DISTINCT FROM 'closed_lost'
        """
    )
    customers = fetch_one("SELECT COUNT(*)::int AS n FROM web_customers")
    orders = fetch_one(
        """
        SELECT COUNT(*)::int AS n,
               COALESCE(SUM(amount_ntd),0)::bigint AS revenue
        FROM web_orders
        """
    )
    by_stage = fetch_all(
        """
        SELECT stage, COUNT(*)::int AS n,
               COALESCE(SUM(amount_ntd),0)::bigint AS amount
        FROM opportunities
        GROUP BY stage
        ORDER BY n DESC
        """
    )
    recent_acts = fetch_all(
        """
        SELECT a.id, a.kind, a.subject, a.body, a.created_at,
               acc.name AS account_name
        FROM activities a
        LEFT JOIN accounts acc ON acc.id = a.account_id
        ORDER BY a.created_at DESC NULLS LAST
        LIMIT 8
        """
    )
    top_customers = fetch_all(
        """
        SELECT name, segment, order_count, lifetime_value, risk_flag, last_order_date
        FROM web_customers
        ORDER BY lifetime_value DESC NULLS LAST
        LIMIT 6
        """
    )
    war = fetch_all(
        """
        SELECT snap_month, title, summary, metrics, created_at
        FROM war_room_snapshots
        ORDER BY created_at DESC NULLS LAST
        LIMIT 3
        """
    )

    data = {
        "cache": "miss",
        "kpis": {
            "accounts": accounts["n"] if accounts else 0,
            "opportunities": opps["n"] if opps else 0,
            "pipeline_ntd": opps["pipeline"] if opps else 0,
            "web_customers": customers["n"] if customers else 0,
            "web_orders": orders["n"] if orders else 0,
            "web_revenue_ntd": orders["revenue"] if orders else 0,
        },
        "pipeline_by_stage": [json_safe(x) for x in by_stage],
        "recent_activities": [json_safe(x) for x in recent_acts],
        "top_customers": [json_safe(x) for x in top_customers],
        "war_room": [json_safe(x) for x in war],
    }

    try:
        if r is not None:
            r.setex(cache_key, 30, json.dumps(data, ensure_ascii=False, default=str))
    except Exception:  # noqa: BLE001
        pass
    return data


@app.get("/api/accounts")
def accounts() -> dict:
    rows = fetch_all(
        """
        SELECT id, name, industry, stores, stage, source, owner, notes, created_at
        FROM accounts
        ORDER BY updated_at DESC NULLS LAST, created_at DESC NULLS LAST
        LIMIT 100
        """
    )
    return {"items": [json_safe(x) for x in rows]}


@app.get("/api/opportunities")
def opportunities() -> dict:
    rows = fetch_all(
        """
        SELECT o.id, o.title, o.amount_ntd, o.stage, o.probability, o.close_date,
               o.competitor, o.package_code, o.notes, o.created_at,
               a.name AS account_name
        FROM opportunities o
        LEFT JOIN accounts a ON a.id = o.account_id
        ORDER BY o.amount_ntd DESC NULLS LAST
        LIMIT 100
        """
    )
    return {"items": [json_safe(x) for x in rows]}


@app.get("/api/customers")
def customers() -> dict:
    rows = fetch_all(
        """
        SELECT id, name, email, phone, segment, rfm_score, order_count,
               lifetime_value, last_order_date, risk_flag
        FROM web_customers
        ORDER BY lifetime_value DESC NULLS LAST
        LIMIT 100
        """
    )
    return {"items": [json_safe(x) for x in rows]}


@app.get("/api/competitors")
def competitors() -> dict:
    rows = fetch_all(
        """
        SELECT c.id, c.code, c.name, c.category, c.threat_level, c.website, c.notes,
               (
                 SELECT COUNT(*)::int FROM competitor_signals s
                 WHERE s.competitor_id = c.id
               ) AS signal_count
        FROM competitors c
        WHERE COALESCE(c.active, true)
        ORDER BY c.sort_order NULLS LAST, c.name
        """
    )
    return {"items": [json_safe(x) for x in rows]}


# ----- Agentic form fill (客服填表) -----


@app.get("/api/forms/template")
def form_template() -> dict:
    return {"ok": True, "template": form_fill.FORM_TEMPLATE}


@app.post("/api/forms/turn")
def form_turn(body: FormTurnIn) -> dict:
    """Multi-turn: user message → extract fields + agent reply + missing list."""
    try:
        result = form_fill.form_turn(
            body.message,
            values=body.values,
            history=body.history,
        )
        if body.session_id:
            try:
                form_fill.save_draft(body.session_id, result["values"])
            except Exception:  # noqa: BLE001
                pass
        return {"ok": True, "session_id": body.session_id, **result}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"form turn failed: {e}") from e


@app.post("/api/forms/apply")
def form_apply(body: FormSubmitIn) -> dict:
    """Manual field edits from UI."""
    return {"ok": True, **form_fill.apply_manual(body.values)}


@app.post("/api/forms/submit")
def form_submit(body: FormSubmitIn) -> dict:
    try:
        rec = form_fill.submit_form(body.values, session_id=body.session_id)
        return {"ok": True, "submission": rec}
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"submit failed: {e}") from e


@app.get("/api/forms/submissions")
def form_submissions(limit: int = 20) -> dict:
    try:
        return {"ok": True, "items": form_fill.list_submissions(limit=limit)}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, str(e)) from e


# ----- NL → SQL (read-only) -----


@app.get("/api/sql/schema")
def sql_schema() -> dict:
    try:
        return {"ok": True, **sql_agent.get_schema()}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"schema failed: {e}") from e


@app.get("/api/sql/samples")
def sql_samples() -> dict:
    return {
        "ok": True,
        "items": [
            "目前有多少客戶帳戶？",
            "管道金額最高的 5 個商機是哪些？",
            "各銷售階段的商機數量與金額？",
            "電商客戶營收 Top 5？",
            "最近 10 筆活動是什麼？",
            "競品威脅等級分布？",
        ],
    }


@app.post("/api/sql/ask")
def sql_ask(body: SqlAskIn) -> dict:
    """
    Agentic NL2SQL: skill + schema + SELECT-only execute + zh answer.
    Pattern from Hands-On agentic_sql_search; Qwen + catch_crm.
    """
    try:
        result = sql_agent.ask(body.question)
        return result
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"sql agent failed: {e}") from e


# ----- CartMate-style support memory (Redis) -----


@app.get("/api/cs/memory")
def cs_memory_list(customer_id: str = "Alex", limit: int = 40) -> dict:
    try:
        mems = csmem.list_memories(customer_id, limit=limit)
        return {
            "ok": True,
            "customer_id": csmem._norm_user(customer_id),
            "results": mems,
            "count": len(mems),
        }
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, str(e)) from e


@app.post("/api/cs/memory")
def cs_memory_add(body: CsMemIn) -> dict:
    try:
        if not (body.text or "").strip():
            raise HTTPException(400, "text required")
        item = csmem.add_memory(body.customer_id, body.text or "", kind="manual")
        return {"ok": True, "item": item}
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, str(e)) from e


@app.delete("/api/cs/memory")
def cs_memory_clear(customer_id: str = "Alex") -> dict:
    try:
        n = csmem.clear_memories(customer_id)
        return {"ok": True, "cleared": n, "customer_id": csmem._norm_user(customer_id)}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, str(e)) from e


@app.post("/api/cs/seed")
def cs_memory_seed(customer_id: str = "Alex") -> dict:
    try:
        mems = csmem.seed_demo(customer_id)
        greet = csmem.greeting(customer_id)
        return {"ok": True, "memories": mems, "greeting": greet}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, str(e)) from e


@app.get("/api/cs/greeting")
def cs_greeting(customer_id: str = "Alex") -> dict:
    try:
        return {"ok": True, **csmem.greeting(customer_id)}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, str(e)) from e


@app.post("/api/cs/chat")
def cs_chat(body: CsChatIn) -> dict:
    """Support chat with recall → answer → store facts (CartMate loop)."""
    try:
        return {"ok": True, **csmem.support_chat(body.customer_id, body.message)}
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"cs chat failed: {e}") from e


@app.get("/api/cs/departments")
def cs_departments() -> dict:
    return {"ok": True, "departments": query_router.list_departments()}


@app.post("/api/cs/route")
def cs_route(body: CsRouteIn) -> dict:
    """
    Lightweight query routing: signals + FAQ + memory → resolve|escalate.
    Pattern from customer_query_routing_agent (no VectorAI).
    """
    try:
        return {"ok": True, **query_router.route_query(body.customer_id, body.message)}
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"route failed: {e}") from e


@app.get("/api/cs/kb/databases")
def cs_kb_databases() -> dict:
    """List knowledge stores available to the KB router."""
    return {"ok": True, "databases": kb_router.list_databases()}


@app.post("/api/cs/kb-route")
def cs_kb_route(body: CsKbRouteIn) -> dict:
    """
    Multi-KB routing: classify → support|mmrag|wikiband|sql|agri|crm|form
    → answer; weak retrieval falls back to support FAQ.
    Pattern from rag_agent_with_database_routing (no Orq/Qdrant).
    """
    try:
        return kb_router.route_and_answer(body.customer_id, body.message)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"kb-route failed: {e}") from e


@app.post("/api/cs/voice")
async def cs_voice(
    file: UploadFile = File(...),
    mode: str = Form("route"),
    customer_id: str = Form("Alex"),
    form_values: str = Form(""),
    form_history: str = Form(""),
    session_id: str = Form(""),
) -> dict:
    """
    CS multi-modal voice: mic audio → Gemini STT → same bus as text
    (route | support | form | sql | crm). No GPU / local ASR.
    """
    raw = await file.read()
    if not raw:
        raise HTTPException(400, "empty audio")
    if len(raw) > 12 * 1024 * 1024:
        raise HTTPException(400, "audio too large (max 12MB)")
    mime = file.content_type or "audio/webm"
    try:
        stt = cs_audio.transcribe_audio(raw, mime)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"voice STT failed: {e}") from e

    transcript = (stt.get("transcript") or "").strip()
    if not transcript or transcript.startswith("【聽不清】"):
        return {
            "ok": False,
            "error": "無法辨識語音",
            "transcript": transcript,
            "stt": stt,
        }

    m = (mode or "route").strip().lower()
    out: dict[str, Any] = {
        "ok": True,
        "input": "mic",
        "mode": m,
        "transcript": transcript,
        "stt": stt,
        "customer_id": customer_id,
    }

    try:
        if m == "support":
            out.update(csmem.support_chat(customer_id, transcript))
        elif m in ("kb", "kbroute", "kb-route"):
            kb = kb_router.route_and_answer(customer_id, transcript)
            out.update(kb)
            out["mode"] = "kb"
        elif m == "form":
            try:
                values = json.loads(form_values) if form_values.strip() else {}
            except json.JSONDecodeError:
                values = {}
            try:
                history = json.loads(form_history) if form_history.strip() else []
            except json.JSONDecodeError:
                history = []
            if not isinstance(values, dict):
                values = {}
            if not isinstance(history, list):
                history = []
            result = form_fill.form_turn(
                transcript,
                values=values,
                history=history,
            )
            if session_id and result.get("values"):
                try:
                    form_fill.save_draft(session_id, result["values"])
                except Exception:  # noqa: BLE001
                    pass
            out["form"] = result
            out["reply"] = result.get("reply") or ""
            if result.get("ask_next"):
                out["reply"] = (out["reply"] + "\n" + result["ask_next"]).strip()
        elif m == "sql":
            out["sql"] = sql_agent.ask(transcript)
            out["reply"] = (out["sql"] or {}).get("answer_zh") or (
                out["sql"] or {}
            ).get("error") or "完成"
        elif m == "crm":
            out.update(_cs_crm_chat(transcript))
        else:
            # default: lightweight route
            routed = query_router.route_query(customer_id, transcript)
            out.update(routed)
            out["action"] = routed.get("action")
            out["decision"] = routed.get("decision")
            out["reply"] = routed.get("reply")
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"voice bus failed ({m}): {e}") from e

    return out


def _cs_crm_chat(message: str) -> dict:
    """Minimal CRM KPI chat (same spirit as /api/ai/chat)."""
    # Prefer existing endpoint logic by calling qwen with short context
    try:
        dash = fetch_one(
            """
            SELECT
              (SELECT COUNT(*)::int FROM accounts) AS accounts,
              (SELECT COUNT(*)::int FROM opportunities) AS opps,
              (SELECT COALESCE(SUM(amount),0)::float FROM opportunities) AS pipeline
            """
        ) or {}
    except Exception:  # noqa: BLE001
        dash = {}
    system = (
        "你是 CATCH CRM 業務助理，繁體中文。"
        f"目前 KPI：帳戶={dash.get('accounts')} 商機={dash.get('opps')} "
        f"管道金額={dash.get('pipeline')}。"
        "簡短實用回答。"
    )
    payload = {
        "model": config.QWEN_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": message},
        ],
        "temperature": 0.3,
        "max_tokens": 600,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    req = urllib.request.Request(
        config.QWEN_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
        msg = (raw.get("choices") or [{}])[0].get("message") or {}
        reply = (msg.get("content") or msg.get("reasoning_content") or "").strip()
        reply = re.sub(r"<think>[\s\S]*?</think>", "", reply, flags=re.I).strip()
        return {"reply": reply or "（空回應）"}
    except Exception as e:  # noqa: BLE001
        return {"reply": f"CRM 問答失敗：{e}"}


# ----- Agriculture vertical (tool-calling bus sibling tab) -----


@app.get("/api/agri/crops")
def agri_crops() -> dict:
    return {"ok": True, "crops": agri_agent.list_crops()}


@app.get("/api/agri/samples")
def agri_samples() -> dict:
    return {"ok": True, "items": agri_agent.sample_questions()}


@app.post("/api/agri/ask")
def agri_ask(body: AgriAskIn) -> dict:
    """
    Multi-tool agri assistant: weather + crop calendar + news search → Qwen.
    Pattern from llm_agri_bot; LAN Qwen, no Mistral required.
    """
    try:
        return {"ok": True, **agri_agent.ask(body.question)}
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"agri agent failed: {e}") from e


# ----- Receipt OCR + expense ledger (Gemini vision + optional Qwen polish) -----


class ExpenseSaveIn(BaseModel):
    vendor: str | None = None
    date: str | None = None
    currency: str | None = "TWD"
    subtotal: float | None = None
    tax: float | None = None
    total: float | None = None
    category: str | None = "其他"
    notes: str | None = None
    line_items: list[dict] | None = None
    summary_zh: str | None = None


@app.post("/api/expenses/extract")
async def expenses_extract(
    file: UploadFile = File(...),
    polish: bool = Form(True),
) -> dict:
    """Vision extract via Google AI Studio Gemini; optional Qwen category polish."""
    raw = await file.read()
    if not raw:
        raise HTTPException(400, "empty file")
    if len(raw) > 12 * 1024 * 1024:
        raise HTTPException(400, "file too large (max 12MB)")
    mime = file.content_type or "image/jpeg"
    if mime not in ("image/jpeg", "image/png", "image/webp", "image/gif"):
        mime = "image/jpeg"
    try:
        extracted = receipt_expense.extract_and_optionally_polish(
            raw, mime_type=mime, polish=polish
        )
        return {
            "ok": True,
            "extracted": extracted,
            "vision": "gemini",
            "qwen_url": config.QWEN_URL,
        }
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"extract failed: {e}") from e


@app.post("/api/expenses")
def expenses_save(body: ExpenseSaveIn) -> dict:
    try:
        data = body.model_dump()
        if body.summary_zh and not data.get("notes"):
            data["notes"] = body.summary_zh
        rec = receipt_expense.save_expense(data, image_bytes=None)
        return {"ok": True, "expense": rec}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, str(e)) from e


@app.post("/api/expenses/extract-and-save")
async def expenses_extract_and_save(
    file: UploadFile = File(...),
    polish: bool = Form(True),
) -> dict:
    raw = await file.read()
    if not raw:
        raise HTTPException(400, "empty file")
    mime = file.content_type or "image/jpeg"
    try:
        extracted = receipt_expense.extract_and_optionally_polish(
            raw, mime_type=mime, polish=polish
        )
        rec = receipt_expense.save_expense(
            extracted, image_bytes=raw, mime_type=mime
        )
        return {"ok": True, "extracted": extracted, "expense": rec}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, str(e)) from e


@app.get("/api/expenses")
def expenses_list(limit: int = 50) -> dict:
    try:
        return {
            "ok": True,
            "items": receipt_expense.list_expenses(limit=limit),
            "by_category": receipt_expense.summary_by_category(),
        }
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, str(e)) from e


@app.delete("/api/expenses/{expense_id}")
def expenses_delete(expense_id: str) -> dict:
    ok = receipt_expense.delete_expense(expense_id)
    if not ok:
        raise HTTPException(404, "not found")
    return {"ok": True, "deleted": expense_id}


@app.post("/api/ai/chat")
def ai_chat(body: ChatIn) -> dict:
    """Proxy to local Qwen OpenAI-compatible endpoint with CRM context."""
    dash = None
    try:
        dash = dashboard()
    except Exception:  # noqa: BLE001
        pass

    kpis = (dash or {}).get("kpis") or {}
    system = (
        "你是 CATCH CRM 的業務助理，使用繁體中文回答。"
        "根據提供的 CRM 指標與用戶問題給出簡潔、可執行的建議。"
        "不要編造不存在的客戶名稱；可引用管道金額與階段。"
        f"目前指標：accounts={kpis.get('accounts')}, "
        f"opportunities={kpis.get('opportunities')}, "
        f"pipeline_ntd={kpis.get('pipeline_ntd')}, "
        f"web_customers={kpis.get('web_customers')}, "
        f"web_orders={kpis.get('web_orders')}, "
        f"web_revenue_ntd={kpis.get('web_revenue_ntd')}。"
    )
    if body.context:
        system += f" 補充上下文：{body.context[:1500]}"

    payload = {
        "model": config.QWEN_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": body.message},
        ],
        "max_tokens": 1024,
        "temperature": 0.4,
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
        raise HTTPException(status_code=502, detail=f"Qwen HTTP {e.code}: {err[:500]}") from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Qwen error: {e}") from e

    choice = (raw.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    text = _extract_qwen_text(message)

    # log lightly to redis
    try:
        r = _redis()
        r.lpush(
            "crm:demo:ai_log",
            json.dumps(
                {"q": body.message[:200], "a": text[:300], "t": int(time.time())},
                ensure_ascii=False,
            ),
        )
        r.ltrim("crm:demo:ai_log", 0, 49)
    except Exception:  # noqa: BLE001
        pass

    return {
        "reply": text,
        "model": raw.get("model") or config.QWEN_MODEL,
        "usage": raw.get("usage"),
        "finish_reason": choice.get("finish_reason"),
    }


# ----- Multimodal RAG (Hands-On multimodal_rag · lightweight) -----


class MmRagTextIn(BaseModel):
    text: str
    label: str | None = "貼上文字"


class MmRagUrlIn(BaseModel):
    url: str


class MmRagAskIn(BaseModel):
    question: str
    top_k: int | None = 5
    hyde: bool | None = False
    n_hyde: int | None = 3


@app.get("/api/mmrag/stats")
def mmrag_stats() -> dict:
    try:
        return mm_rag.stats()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, str(e)) from e


@app.delete("/api/mmrag")
def mmrag_clear() -> dict:
    try:
        return mm_rag.clear_index()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, str(e)) from e


@app.post("/api/mmrag/text")
def mmrag_add_text(body: MmRagTextIn) -> dict:
    try:
        return mm_rag.add_text(body.text, label=body.label or "貼上文字")
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, str(e)) from e


@app.post("/api/mmrag/url")
def mmrag_add_url(body: MmRagUrlIn) -> dict:
    try:
        return mm_rag.add_url(body.url)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, str(e)) from e


@app.post("/api/mmrag/media")
async def mmrag_add_media(
    file: UploadFile = File(...),
    kind: str = Form("image"),
    label: str = Form(""),
) -> dict:
    raw = await file.read()
    if not raw:
        raise HTTPException(400, "empty file")
    mime = file.content_type or "application/octet-stream"
    k = (kind or "image").strip().lower()
    if k not in ("image", "audio"):
        # auto-detect
        if mime.startswith("audio") or mime in ("video/webm",):
            k = "audio"
        else:
            k = "image"
    try:
        return mm_rag.add_media(
            raw,
            mime_type=mime,
            kind=k,
            label=label or file.filename or k,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, str(e)) from e


@app.post("/api/mmrag/ask")
def mmrag_ask(body: MmRagAskIn) -> dict:
    """
    RAG ask. Optional HyDE: hypothetical docs → embed average → retrieve.
    """
    try:
        return mm_rag.query(
            body.question,
            top_k=body.top_k or 5,
            hyde=bool(body.hyde),
            n_hyde=body.n_hyde or 3,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, str(e)) from e


# ----- Wiki 樂團 RAG (Hands-On rock_music_rag · BM25) -----


class WikiBandIn(BaseModel):
    name: str
    lang: str | None = "en"


class WikiBandAskIn(BaseModel):
    question: str
    top_k: int | None = 5


class WikiBandRemoveIn(BaseModel):
    title: str


@app.get("/api/wikiband/stats")
def wikiband_stats() -> dict:
    try:
        return wiki_band_rag.stats()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, str(e)) from e


@app.delete("/api/wikiband")
def wikiband_clear() -> dict:
    try:
        return wiki_band_rag.clear()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, str(e)) from e


@app.post("/api/wikiband/add")
def wikiband_add(body: WikiBandIn) -> dict:
    try:
        return wiki_band_rag.add_band(body.name, lang=body.lang or "en")
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, str(e)) from e


@app.post("/api/wikiband/defaults")
def wikiband_defaults(lang: str = "en") -> dict:
    try:
        return wiki_band_rag.load_defaults(lang=lang or "en")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, str(e)) from e


@app.post("/api/wikiband/remove")
def wikiband_remove(body: WikiBandRemoveIn) -> dict:
    try:
        return wiki_band_rag.remove_band(body.title)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, str(e)) from e


@app.post("/api/wikiband/ask")
def wikiband_ask(body: WikiBandAskIn) -> dict:
    try:
        return wiki_band_rag.ask(body.question, top_k=body.top_k or 5)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, str(e)) from e


@app.get("/api/remote/overview")
def remote_overview() -> dict:
    """Show remote FastAPI openapi summary for demo integration panel."""
    ok, detail, data = _http_get(f"{config.REMOTE_FASTAPI}/openapi.json", timeout=6)
    paths = []
    title = None
    if ok and isinstance(data, dict):
        title = (data.get("info") or {}).get("title")
        paths = sorted((data.get("paths") or {}).keys())[:30]
    return {
        "ok": ok,
        "detail": detail,
        "title": title,
        "base": config.REMOTE_FASTAPI,
        "paths_sample": paths,
    }


# Static files (css/js) — register after API routes
@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/styles.css")
def styles() -> FileResponse:
    return FileResponse(STATIC_DIR / "styles.css", media_type="text/css")


@app.get("/app.js")
def app_js() -> FileResponse:
    return FileResponse(STATIC_DIR / "app.js", media_type="application/javascript")


@app.get("/crm-explain")
@app.get("/crm-explain.html")
def crm_explain_page() -> FileResponse:
    """gimi Traditional Chinese architecture explain page."""
    return FileResponse(STATIC_DIR / "crm-explain.html")


@app.get("/crm-explain-styles.css")
def crm_explain_styles() -> FileResponse:
    return FileResponse(STATIC_DIR / "crm-explain-styles.css", media_type="text/css")


@app.get("/crm-explain-extra.css")
def crm_explain_extra() -> FileResponse:
    return FileResponse(STATIC_DIR / "crm-explain-extra.css", media_type="text/css")


app.mount(
    "/assets/crm-explain",
    StaticFiles(directory=str(STATIC_DIR / "assets" / "crm-explain")),
    name="crm_explain_assets",
)

