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
from pydantic import BaseModel, Field

from . import config
from .clinic import diagnose as clinic_diagnose
from .clinic import get_example as clinic_get_example
from .clinic import list_examples as clinic_list_examples
from .clinic import PATTERNS as CLINIC_PATTERNS
from .db import execute, fetch_all, fetch_one, json_safe
from .rag import (
    answer_with_rag,
    get_knowledge_doc,
    list_knowledge_base,
    list_ollama_models,
    rebuild_index,
    search as rag_search,
)
from .seed import SEED_KEY, TEAM, run_seed

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(title="CATCH Marketing Site", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _redis() -> redis.Redis:
    return redis.Redis(
        host=config.REDIS_HOST,
        port=config.REDIS_PORT,
        decode_responses=True,
        socket_connect_timeout=2,
    )


def _http_get(url: str, timeout: float = 4.0) -> tuple[bool, str, Any]:
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                data = body[:240]
            return True, f"HTTP {resp.status}", data
    except Exception as e:  # noqa: BLE001
        return False, str(e), None


def _extract_qwen_text(message: dict) -> str:
    content = (message.get("content") or "").strip()
    if content:
        return content
    reason = message.get("reasoning_content") or ""
    cands = re.findall(r"[\u4e00-\u9fff][^。！？\n]{8,120}[。！？]", reason)
    if cands:
        return cands[-1].strip()
    m = re.search(r"`([^`\n]{10,160})`", reason)
    if m and re.search(r"[\u4e00-\u9fff]", m.group(1)):
        return m.group(1).strip()
    return (reason.strip()[-500:] if reason.strip() else "（模型未回傳可視內容）")


@app.on_event("startup")
def on_startup() -> None:
    try:
        run_seed()
    except Exception:  # noqa: BLE001
        pass


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "service": "catch-marketing-demo"}


@app.post("/api/seed")
def api_seed() -> dict:
    try:
        return {"ok": True, **run_seed()}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, str(e)) from e


@app.get("/api/infra/status")
def infra_status() -> dict:
    services: dict[str, Any] = {}

    ok, detail, data = _http_get("http://100.88.220.82:8080/v1/models", 5)
    model_id = config.QWEN_MODEL
    if ok and isinstance(data, dict):
        arr = data.get("data") or data.get("models") or []
        if arr:
            model_id = arr[0].get("id") or arr[0].get("model") or model_id
    services["qwen"] = {
        "ok": ok,
        "detail": detail,
        "url": config.QWEN_URL,
        "model": model_id,
    }

    ok, detail, data = _http_get(f"{config.REMOTE_FASTAPI}/health", 4)
    services["remote_fastapi"] = {
        "ok": ok,
        "detail": detail,
        "url": config.REMOTE_FASTAPI,
        "health": data,
        "note": "glasses_backend",
    }

    try:
        r = _redis()
        t0 = time.time()
        r.ping()
        services["redis"] = {
            "ok": True,
            "detail": f"ping {round((time.time() - t0) * 1000)}ms",
            "url": f"redis://{config.REDIS_HOST}:{config.REDIS_PORT}",
            "keys": r.dbsize(),
        }
    except Exception as e:  # noqa: BLE001
        services["redis"] = {
            "ok": False,
            "detail": str(e),
            "url": f"redis://{config.REDIS_HOST}:{config.REDIS_PORT}",
        }

    try:
        t0 = time.time()
        row = fetch_one("SELECT current_database() AS db")
        services["postgresql"] = {
            "ok": True,
            "detail": f"query {round((time.time() - t0) * 1000)}ms",
            "url": f"postgresql://{config.PG_HOST}:{config.PG_PORT}/{config.PG_DB}",
            "database": row["db"] if row else config.PG_DB,
        }
    except Exception as e:  # noqa: BLE001
        services["postgresql"] = {
            "ok": False,
            "detail": str(e),
            "url": f"postgresql://{config.PG_HOST}:{config.PG_PORT}/{config.PG_DB}",
        }

    # Ollama tags
    try:
        t0 = time.time()
        models = list_ollama_models()
        names = [m.get("name") for m in models if m.get("name")]
        services["ollama"] = {
            "ok": True,
            "detail": f"tags {round((time.time() - t0) * 1000)}ms · {len(names)} models",
            "url": config.OLLAMA_TAGS_URL,
            "models": names,
            "embed_model": config.OLLAMA_EMBED_MODEL,
            "chat_model": config.OLLAMA_CHAT_MODEL,
        }
    except Exception as e:  # noqa: BLE001
        services["ollama"] = {
            "ok": False,
            "detail": str(e),
            "url": config.OLLAMA_TAGS_URL,
        }

    return {"ok": all(s.get("ok") for s in services.values()), "services": services}


@app.get("/api/ollama/tags")
def ollama_tags() -> dict:
    try:
        models = list_ollama_models()
        return {
            "ok": True,
            "url": config.OLLAMA_TAGS_URL,
            "count": len(models),
            "models": [
                {
                    "name": m.get("name"),
                    "size": m.get("size"),
                    "parameter_size": (m.get("details") or {}).get("parameter_size"),
                    "family": (m.get("details") or {}).get("family"),
                }
                for m in models
            ],
        }
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Ollama tags error: {e}") from e


class RagQuery(BaseModel):
    question: str = Field(..., min_length=2, max_length=500)
    top_k: int = Field(5, ge=1, le=10)


@app.post("/api/rag/rebuild")
def rag_rebuild() -> dict:
    try:
        meta = rebuild_index()
        return {"ok": True, "meta": meta}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"RAG rebuild failed: {e}") from e


@app.post("/api/rag/search")
def rag_search_api(body: RagQuery) -> dict:
    try:
        hits = rag_search(body.question, top_k=body.top_k)
        return {
            "ok": True,
            "question": body.question,
            "hits": hits,
            "embed_model": config.OLLAMA_EMBED_MODEL,
        }
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"RAG search failed: {e}") from e


@app.post("/api/rag/ask")
def rag_ask(body: RagQuery) -> dict:
    try:
        result = answer_with_rag(body.question, top_k=body.top_k)
        return {"ok": True, "question": body.question, **result}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"RAG ask failed: {e}") from e


@app.get("/api/team")
def api_team() -> dict:
    """Demo team roster (Redis seed + fallback constant)."""
    members = TEAM
    try:
        r = _redis()
        raw = r.get(SEED_KEY)
        if raw:
            data = json.loads(raw)
            if data.get("team"):
                members = data["team"]
    except Exception:  # noqa: BLE001
        pass
    depts: dict[str, int] = {}
    for m in members:
        d = m.get("dept") or "其他"
        depts[d] = depts.get(d, 0) + 1
    return {
        "ok": True,
        "count": len(members),
        "departments": depts,
        "members": members,
        "org": {
            "name": "CATCH Growth",
            "mission": "讓中小餐飲與零售品牌用得起可追蹤的成長系統",
            "hq": "台北 · 遠端協作",
        },
    }


@app.get("/api/knowledge")
def api_knowledge() -> dict:
    try:
        data = list_knowledge_base()
        return {"ok": True, **data}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"knowledge list failed: {e}") from e


@app.get("/api/knowledge/{doc_id}")
def api_knowledge_doc(doc_id: str) -> dict:
    doc = get_knowledge_doc(doc_id)
    if not doc:
        raise HTTPException(404, "document not found")
    return {"ok": True, "doc": doc}


class KbArticleIn(BaseModel):
    title: str = Field(..., min_length=2, max_length=120)
    category: str = Field("自訂", max_length=40)
    summary: str = Field("", max_length=300)
    body: str = Field(..., min_length=4, max_length=4000)
    owner: str = Field("展示用戶", max_length=40)


@app.get("/api/clinic/patterns")
def api_clinic_patterns() -> dict:
    return {"ok": True, "patterns": CLINIC_PATTERNS}


@app.get("/api/clinic/examples")
def api_clinic_examples() -> dict:
    return {"ok": True, "examples": clinic_list_examples()}


@app.get("/api/clinic/examples/{example_id}")
def api_clinic_example(example_id: str) -> dict:
    bug = clinic_get_example(example_id)
    if not bug:
        raise HTTPException(404, "example not found")
    return {"ok": True, "id": example_id, "bug": bug}


class ClinicIn(BaseModel):
    bug_description: str = Field(..., min_length=20, max_length=12000)
    max_tokens: int = Field(1200, ge=256, le=4096)


@app.post("/api/clinic/diagnose")
def api_clinic_diagnose(body: ClinicIn) -> dict:
    """RAG Failure Diagnostics Clinic (upstream awesome-llm-apps)."""
    try:
        result = clinic_diagnose(body.bug_description, max_tokens=body.max_tokens)
        return {"ok": True, **result}
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"clinic failed: {e}") from e


@app.post("/api/knowledge/articles")
def api_knowledge_add(body: KbArticleIn) -> dict:
    """Append a demo KB article to Redis and return it (call rebuild for RAG)."""
    import uuid

    from .seed import KB_EXTRA_KEY

    art = {
        "id": f"kb-user-{uuid.uuid4().hex[:8]}",
        "category": body.category,
        "title": body.title,
        "summary": body.summary or body.body[:80],
        "body": body.body,
        "owner": body.owner,
        "tags": ["user", "demo"],
    }
    try:
        r = _redis()
        raw = r.get(KB_EXTRA_KEY)
        items = json.loads(raw) if raw else []
        items.insert(0, art)
        r.set(KB_EXTRA_KEY, json.dumps(items, ensure_ascii=False))
        r.delete("mkt:demo:overview")
        return {"ok": True, "article": art, "hint": "請執行 /api/rag/rebuild 以納入向量索引"}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, str(e)) from e


@app.get("/api/marketing/overview")
def marketing_overview() -> dict:
    cache_key = "mkt:demo:overview"
    try:
        r = _redis()
        cached = r.get(cache_key)
        if cached:
            data = json.loads(cached)
            data["cache"] = "hit"
            return data
    except Exception:  # noqa: BLE001
        r = None

    plan = fetch_one(
        """
        SELECT year, theme, budget_ntd, status, kpis, body_md
        FROM marketing_plans
        ORDER BY year DESC NULLS LAST
        LIMIT 1
        """
    )
    ads = fetch_one(
        """
        SELECT COALESCE(SUM(spend_ntd),0)::bigint AS spend,
               COALESCE(SUM(impressions),0)::bigint AS impressions,
               COALESCE(SUM(clicks),0)::bigint AS clicks,
               COALESCE(SUM(conversions),0)::bigint AS conversions,
               COALESCE(SUM(revenue_attr_ntd),0)::bigint AS revenue
        FROM ad_daily
        """
    )
    by_platform = fetch_all(
        """
        SELECT platform,
               COALESCE(SUM(spend_ntd),0)::bigint AS spend,
               COALESCE(SUM(clicks),0)::bigint AS clicks,
               COALESCE(SUM(conversions),0)::bigint AS conversions,
               COALESCE(SUM(revenue_attr_ntd),0)::bigint AS revenue
        FROM ad_daily
        GROUP BY platform
        ORDER BY spend DESC NULLS LAST
        """
    )
    audiences = fetch_all(
        """
        SELECT code, name, short_name, family, estimated_size, ansoff_axis, description
        FROM audience_packs
        WHERE COALESCE(active, true)
        ORDER BY sort_order NULLS LAST, name
        LIMIT 12
        """
    )
    products = fetch_all(
        """
        SELECT sku, name, category, active
        FROM product_catalog
        WHERE COALESCE(active, true)
        ORDER BY category, name
        LIMIT 12
        """
    )
    leads = fetch_all(
        """
        SELECT name, email, company, interest, status, source, created_at
        FROM form_submissions
        ORDER BY created_at DESC NULLS LAST
        LIMIT 12
        """
    )
    competitors = fetch_all(
        """
        SELECT name, category, threat_level, website
        FROM competitors
        WHERE COALESCE(active, true)
        ORDER BY sort_order NULLS LAST
        LIMIT 8
        """
    )
    orders = fetch_one(
        """
        SELECT COUNT(*)::int AS n,
               COALESCE(SUM(amount_ntd),0)::bigint AS revenue
        FROM web_orders
        """
    )

    # creative content from redis seed
    creative = {"testimonials": [], "cases": [], "pricing": []}
    try:
        rr = _redis()
        raw = rr.get(SEED_KEY)
        if raw:
            creative = json.loads(raw)
    except Exception:  # noqa: BLE001
        from .seed import CASES, PRICING, TESTIMONIALS

        creative = {
            "testimonials": TESTIMONIALS,
            "cases": CASES,
            "pricing": PRICING,
        }

    spend = ads["spend"] if ads else 0
    clicks = ads["clicks"] if ads else 0
    conversions = ads["conversions"] if ads else 0
    rev = ads["revenue"] if ads else 0
    ctr = round(clicks / max(ads["impressions"] or 1, 1) * 100, 2) if ads else 0
    cpa = int(spend / max(conversions, 1)) if ads else 0
    roas = round(rev / max(spend, 1), 2) if ads else 0

    data = {
        "cache": "miss",
        "brand": {
            "name": "CATCH Growth",
            "tagline": "把行銷預算變成可追蹤的成長",
            "subtitle": "廣告 · 受眾 · CRM · AI 文案，一站展示",
        },
        "plan": json_safe(plan),
        "kpis": {
            "ad_spend_ntd": spend,
            "ad_clicks": clicks,
            "ad_conversions": conversions,
            "ad_revenue_ntd": rev,
            "ctr_pct": ctr,
            "cpa_ntd": cpa,
            "roas": roas,
            "web_orders": orders["n"] if orders else 0,
            "web_revenue_ntd": orders["revenue"] if orders else 0,
            "budget_ntd": plan["budget_ntd"] if plan else 0,
            "audience_packs": len(audiences),
            "leads": len(leads),
        },
        "by_platform": [json_safe(x) for x in by_platform],
        "audiences": [json_safe(x) for x in audiences],
        "products": [json_safe(x) for x in products],
        "leads": [json_safe(x) for x in leads],
        "competitors": [json_safe(x) for x in competitors],
        "testimonials": creative.get("testimonials") or [],
        "cases": creative.get("cases") or [],
        "pricing": creative.get("pricing") or [],
    }
    try:
        if r is not None:
            r.setex(cache_key, 45, json.dumps(data, ensure_ascii=False, default=str))
    except Exception:  # noqa: BLE001
        pass
    return data


class LeadIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    email: str = Field(..., min_length=3, max_length=120)
    company: str = Field("", max_length=120)
    interest: str = Field("", max_length=200)
    message: str = Field("", max_length=1000)


@app.post("/api/leads")
def create_lead(body: LeadIn) -> dict:
    import uuid

    try:
        execute(
            """
            INSERT INTO form_submissions
              (id, form_type, name, email, phone, company, stores, interest,
               message, source, payload, status, created_at)
            VALUES
              (%s, 'lead', %s, %s, '', %s, 1, %s,
               %s, 'marketing_site', '{}'::jsonb, 'new', NOW())
            """,
            (
                str(uuid.uuid4()),
                body.name,
                body.email,
                body.company or "未填",
                body.interest or "產品咨詢",
                body.message or "來自行銷網站表單",
            ),
        )
        try:
            r = _redis()
            r.delete("mkt:demo:overview")
        except Exception:  # noqa: BLE001
            pass
        return {"ok": True, "message": "已收到，我們會盡快聯絡（展示站寫入 catch_crm）"}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"寫入失敗: {e}") from e


class CopyIn(BaseModel):
    topic: str = Field(..., min_length=2, max_length=200)
    tone: str = Field("專業但親和", max_length=40)
    channel: str = Field("官網首屏", max_length=40)


@app.post("/api/ai/copy")
def ai_copy(body: CopyIn) -> dict:
    overview = None
    try:
        overview = marketing_overview()
    except Exception:  # noqa: BLE001
        pass
    k = (overview or {}).get("kpis") or {}
    system = (
        "你是繁體中文的行銷文案總監。輸出精煉、可直接上稿的文案。"
        "不要用英文思考過程。不要誇大無法驗證的數字。"
        f"可參考展示數據：廣告花費={k.get('ad_spend_ntd')}、"
        f"歸因營收={k.get('ad_revenue_ntd')}、ROAS={k.get('roas')}。"
    )
    plan = (overview or {}).get("plan") or {}
    if plan.get("theme"):
        system += f"年度行銷主題：{plan.get('theme')}。"
    user = (
        f"頻道：{body.channel}\n語氣：{body.tone}\n主題：{body.topic}\n\n"
        "請輸出：\n"
        "1) 主標題（18字內）\n"
        "2) 副標（40字內）\n"
        "3) 三個賣點短句\n"
        "4) CTA 按鈕文案\n"
        "5) 一則社群貼文（80–120字）"
    )
    payload = {
        "model": config.QWEN_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": 1024,
        "temperature": 0.5,
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
        raise HTTPException(502, f"Qwen HTTP {e.code}: {err[:400]}") from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Qwen error: {e}") from e

    choice = (raw.get("choices") or [{}])[0]
    text = _extract_qwen_text(choice.get("message") or {})
    try:
        r = _redis()
        r.lpush(
            "mkt:demo:copy_log",
            json.dumps({"topic": body.topic, "out": text[:400], "t": int(time.time())}, ensure_ascii=False),
        )
        r.ltrim("mkt:demo:copy_log", 0, 29)
    except Exception:  # noqa: BLE001
        pass
    return {"copy": text, "model": raw.get("model") or config.QWEN_MODEL}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/styles.css")
def styles() -> FileResponse:
    return FileResponse(STATIC_DIR / "styles.css", media_type="text/css")


@app.get("/app.js")
def app_js() -> FileResponse:
    return FileResponse(STATIC_DIR / "app.js", media_type="application/javascript")
