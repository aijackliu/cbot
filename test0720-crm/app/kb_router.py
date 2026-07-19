"""
Knowledge-base routing for CS bus.

Pattern from Hands-On rag_agent_with_database_routing (no Orq/Qdrant/Streamlit):
  classify → specialized store → grounded answer
  → if weak retrieval, fallback to support FAQ / escalate path

Stores:
  support  — FAQ + 客服 resolve/escalate (query_router)
  mmrag    — 多模態知識庫 (Redis)
  wikiband — Wiki 樂團 BM25
  sql      — catch_crm 只讀 NL2SQL
  agri     — 農業多工具
  crm      — CRM KPI 問答
  form     — 服務申請填表提示（不強制抽欄，回引導文）
"""

from __future__ import annotations

import json
import re
import time
import urllib.request
from typing import Any

from . import config
from . import query_router
from . import mm_rag
from . import wiki_band_rag
from . import sql_agent
from . import agri_agent
from . import support_memory as csmem

# db_id → 繁中標籤
KB_LABELS = {
    "support": "客服 FAQ／升級",
    "mmrag": "多模態知識庫",
    "wikiband": "Wiki 樂團",
    "sql": "CRM 資料庫 (SQL)",
    "agri": "農業助理",
    "crm": "CRM 指標問答",
    "form": "服務申請表",
}

KB_IDS = list(KB_LABELS.keys())


def list_databases() -> list[dict[str, str]]:
    return [{"id": k, "label_zh": v} for k, v in KB_LABELS.items()]


def _chat_qwen(system: str, user: str, max_tokens: int = 500) -> str:
    payload = {
        "model": config.QWEN_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.15,
        "max_tokens": max_tokens,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    req = urllib.request.Request(
        config.QWEN_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        raw = json.loads(resp.read().decode("utf-8"))
    msg = (raw.get("choices") or [{}])[0].get("message") or {}
    text = (msg.get("content") or msg.get("reasoning_content") or "").strip()
    return re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.I).strip()


def _parse_json(text: str) -> dict:
    text = (text or "").strip()
    text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.I)
    if "```" in text:
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if m:
            text = m.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        return json.loads(text[start : end + 1])
    raise ValueError("no json")


def _rule_route(q: str) -> dict[str, Any]:
    """Fast keyword router — reliable demo default."""
    ql = q.lower()
    # music / wiki bands
    if re.search(
        r"nirvana|audioslave|radiohead|beatles|queen|green\s*day|dire\s*straits|"
        r"evanescence|sum\s*41|smiths|樂團|搖滾|主唱|專輯|album|band\b|歌手",
        q,
        re.I,
    ):
        return {
            "database": "wikiband",
            "confidence": "high",
            "reason_zh": "關鍵字指向音樂／樂團／專輯知識",
        }
    # agri
    if re.search(
        r"農|作物|水稻|番茄|天氣|氣象|施肥|病蟲|插秧|收成|溫室|土壤",
        q,
    ):
        return {
            "database": "agri",
            "confidence": "high",
            "reason_zh": "農業／作物／天氣相關",
        }
    # sql / CRM numbers
    if re.search(
        r"多少|幾筆|統計|排行|top\s*\d|營收|管道|商機|帳戶數|客戶數|sql|查表|"
        r"lifetime|ltv|rfm|競品|opportunit",
        q,
        re.I,
    ):
        return {
            "database": "sql",
            "confidence": "high",
            "reason_zh": "需要查 CRM 結構化數據",
        }
    # form
    if re.search(r"填表|申請表|留下資料|預約演示|提交申請|聯絡方式", q):
        return {
            "database": "form",
            "confidence": "high",
            "reason_zh": "使用者要填服務申請／留資",
        }
    # support / policy
    if re.search(
        r"退貨|退款|發票|統編|訂單|物流|出貨|延遲|401|api\s*key|登入|"
        r"律師|消保|客服|投訴|付款|帳單|方案|報價",
        q,
        re.I,
    ):
        return {
            "database": "support",
            "confidence": "high",
            "reason_zh": "客服政策／訂單／技術 FAQ 路徑",
        }
    # mmrag: policy-ish + knowledge base
    if re.search(r"知識庫|文件|根據|政策全文|手冊|說明書", q):
        return {
            "database": "mmrag",
            "confidence": "medium",
            "reason_zh": "指向多模態／文件知識庫",
        }
    # CRM soft
    if re.search(r"kpi|儀表|業績|pipeline|建議業務", q, re.I):
        return {
            "database": "crm",
            "confidence": "medium",
            "reason_zh": "CRM 指標與業務建議",
        }
    # default support
    return {
        "database": "support",
        "confidence": "low",
        "reason_zh": "預設走客服 FAQ（規則未強匹配）",
    }


def classify(message: str) -> dict[str, Any]:
    """Rule first; optional Qwen refine when low confidence."""
    q = (message or "").strip()
    base = _rule_route(q)
    if base.get("confidence") == "high":
        base["method"] = "rules"
        return base

    system = (
        "你是知識庫路由器。只輸出 JSON：\n"
        "{\n"
        '  "database": "support|mmrag|wikiband|sql|agri|crm|form",\n'
        '  "confidence": "high|medium|low",\n'
        '  "reason_zh": "一句繁中理由"\n'
        "}\n"
        "support=客服政策FAQ升級；mmrag=自建文件/圖/音知識庫；"
        "wikiband=搖滾樂團Wikipedia；sql=查CRM表數字；"
        "agri=農業；crm=KPI建議；form=填申請表。"
    )
    try:
        raw = _chat_qwen(system, f"問題：{q}", max_tokens=200)
        data = _parse_json(raw)
        db = data.get("database") or base["database"]
        if db not in KB_IDS:
            db = base["database"]
        conf = data.get("confidence") if data.get("confidence") in (
            "high",
            "medium",
            "low",
        ) else "medium"
        return {
            "database": db,
            "confidence": conf,
            "reason_zh": data.get("reason_zh") or base.get("reason_zh") or "",
            "method": "qwen+rules",
        }
    except Exception:  # noqa: BLE001
        base["method"] = "rules-fallback"
        return base


def _mmrag_hit_quality(result: dict) -> float:
    hits = result.get("hits") or []
    if not hits:
        return 0.0
    return float(hits[0].get("score") or 0.0)


def _wikiband_hit_quality(result: dict) -> float:
    hits = result.get("hits") or []
    if not hits:
        return 0.0
    return float(hits[0].get("score") or 0.0)


def _run_support(customer_id: str, message: str) -> dict[str, Any]:
    r = query_router.route_query(customer_id, message)
    return {
        "handler": "support",
        "reply": r.get("reply") or "",
        "payload": r,
        "sources": [
            {"type": "faq", "title": f.get("title"), "id": f.get("id")}
            for f in (r.get("faq_hits") or [])[:5]
        ],
        "fallback_used": False,
    }


def _run_mmrag(message: str) -> dict[str, Any]:
    # prefer HyDE for short questions
    use_hyde = len(message) < 40
    r = mm_rag.query(message, top_k=5, hyde=use_hyde, n_hyde=2)
    quality = _mmrag_hit_quality(r)
    weak = not (r.get("hits")) or quality < 0.05
    # if only bow and very short kb, still allow answer if hits exist
    if weak and not (r.get("hits")):
        return {
            "handler": "mmrag",
            "reply": r.get("answer") or "多模態知識庫無命中。",
            "payload": r,
            "sources": [],
            "fallback_used": False,
            "weak_retrieval": True,
            "quality": quality,
        }
    sources = [
        {
            "type": "mmrag",
            "label": h.get("source_label"),
            "score": h.get("score"),
            "snippet": (h.get("snippet") or "")[:160],
        }
        for h in (r.get("hits") or [])[:5]
    ]
    return {
        "handler": "mmrag",
        "reply": r.get("answer") or "",
        "payload": r,
        "sources": sources,
        "fallback_used": False,
        "weak_retrieval": weak,
        "quality": quality,
        "hyde": bool(r.get("hyde")),
    }


def _run_wikiband(message: str) -> dict[str, Any]:
    r = wiki_band_rag.ask(message, top_k=5)
    quality = _wikiband_hit_quality(r)
    weak = not (r.get("hits")) or quality <= 0
    sources = [
        {
            "type": "wikiband",
            "band": h.get("band"),
            "url": h.get("url"),
            "score": h.get("score"),
        }
        for h in (r.get("hits") or [])[:5]
    ]
    return {
        "handler": "wikiband",
        "reply": r.get("answer") or "",
        "payload": r,
        "sources": sources,
        "fallback_used": False,
        "weak_retrieval": weak,
        "quality": quality,
    }


def _run_sql(message: str) -> dict[str, Any]:
    r = sql_agent.ask(message)
    ok = bool(r.get("ok"))
    return {
        "handler": "sql",
        "reply": r.get("answer_zh") or r.get("error") or "查詢完成",
        "payload": r,
        "sources": [{"type": "sql", "sql": r.get("sql"), "rows": r.get("row_count")}],
        "fallback_used": False,
        "weak_retrieval": not ok,
    }


def _run_agri(message: str) -> dict[str, Any]:
    r = agri_agent.ask(message)
    tools = r.get("tool_trace") or r.get("tools") or []
    return {
        "handler": "agri",
        "reply": r.get("answer_zh") or r.get("reply") or r.get("answer") or "",
        "payload": r,
        "sources": [{"type": "agri_tool", "detail": str(t)[:200]} for t in tools[:6]],
        "fallback_used": False,
    }


def _run_crm(message: str) -> dict[str, Any]:
    # light KPI context via qwen — mirror main._cs_crm_chat spirit
    from . import db as pg

    try:
        dash = pg.fetch_one(
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
        f"KPI：帳戶={dash.get('accounts')} 商機={dash.get('opps')} 管道={dash.get('pipeline')}。"
        "簡短可執行建議，不編造客戶名。"
    )
    reply = _chat_qwen(system, message, max_tokens=700)
    return {
        "handler": "crm",
        "reply": reply,
        "payload": {"kpis": dash},
        "sources": [{"type": "kpi", "data": dash}],
        "fallback_used": False,
    }


def _run_form(message: str) -> dict[str, Any]:
    reply = (
        "已將您導向「服務申請表」流程。請切換模式為「填表」，"
        "或直接在右側表單填寫公司／聯絡人／需求後提交。\n"
        f"您剛才說的：「{message[:200]}」可一併貼到「需求」欄。"
    )
    return {
        "handler": "form",
        "reply": reply,
        "payload": {"suggest_mode": "form", "need_hint": message[:400]},
        "sources": [],
        "fallback_used": False,
        "form_hints": {
            "need": message[:400],
            "channel": "知識庫路由·填表",
        },
    }


def _dispatch(db: str, customer_id: str, message: str) -> dict[str, Any]:
    if db == "mmrag":
        return _run_mmrag(message)
    if db == "wikiband":
        return _run_wikiband(message)
    if db == "sql":
        return _run_sql(message)
    if db == "agri":
        return _run_agri(message)
    if db == "crm":
        return _run_crm(message)
    if db == "form":
        return _run_form(message)
    return _run_support(customer_id, message)


def route_and_answer(customer_id: str, message: str) -> dict[str, Any]:
    """
    Main entry: classify → retrieve/answer → optional support fallback.
    """
    t0 = time.time()
    message = (message or "").strip()
    if not message:
        raise ValueError("empty message")
    cid = csmem._norm_user(customer_id)

    decision = classify(message)
    db = decision.get("database") or "support"
    if db not in KB_IDS:
        db = "support"

    result = _dispatch(db, cid, message)
    fallback_chain: list[str] = [db]

    # Weak retrieval → support FAQ (except when already support / form)
    weak = bool(result.get("weak_retrieval"))
    if weak and db not in ("support", "form", "crm", "agri"):
        fb = _run_support(cid, message)
        fb["fallback_used"] = True
        fb["fallback_from"] = db
        fb["primary_result"] = {
            "handler": result.get("handler"),
            "quality": result.get("quality"),
            "reply_preview": (result.get("reply") or "")[:200],
        }
        # Prefer support reply but mention primary was weak
        prefix = (
            f"〔知識庫「{KB_LABELS.get(db, db)}」命中偏弱，改走客服 FAQ〕\n"
        )
        fb["reply"] = prefix + (fb.get("reply") or "")
        result = fb
        fallback_chain.append("support")

    # Soft memory note
    try:
        csmem.add_memory(
            cid,
            f"KB路由→{db}：{message[:80]}",
            kind="kb_route",
        )
    except Exception:  # noqa: BLE001
        pass

    elapsed_ms = int((time.time() - t0) * 1000)
    out = {
        "ok": True,
        "customer_id": cid,
        "message": message,
        "routing": {
            "database": db,
            "database_zh": KB_LABELS.get(db, db),
            "confidence": decision.get("confidence"),
            "reason_zh": decision.get("reason_zh"),
            "method": decision.get("method"),
        },
        "reply": result.get("reply") or "",
        "handler": result.get("handler"),
        "sources": result.get("sources") or [],
        "fallback_used": bool(result.get("fallback_used")),
        "fallback_chain": fallback_chain,
        "payload": result.get("payload"),
        "form_hints": result.get("form_hints"),
        "elapsed_ms": elapsed_ms,
        # convenience for UI that reuses route panel
        "decision": {
            "department": db,
            "department_zh": KB_LABELS.get(db, db),
            "action": "fallback" if result.get("fallback_used") else "resolve",
            "confidence": decision.get("confidence"),
            "reason_zh": decision.get("reason_zh"),
        },
        "action": "fallback" if result.get("fallback_used") else "resolve",
    }
    # escalate form hints from support path
    if result.get("handler") == "support":
        pl = result.get("payload") or {}
        if pl.get("form_hints"):
            out["form_hints"] = pl["form_hints"]
        if pl.get("case_id"):
            out["case_id"] = pl["case_id"]
            out["action"] = pl.get("action") or out["action"]
            out["decision"] = pl.get("decision") or out["decision"]
    return out
