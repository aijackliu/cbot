from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import redis
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config
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
        ):
            c = fetch_one(f'SELECT COUNT(*)::int AS n FROM "{table}"')
            counts[table] = c["n"] if c else 0
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