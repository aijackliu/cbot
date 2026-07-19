"""
Lightweight customer query routing (resolve vs escalate).

Pattern from Hands-On customer_query_routing_agent, without VectorAI/Docker:
  signals + FAQ keyword retrieval + customer memory
  → Qwen orchestrator JSON
  → resolve (grounded reply) | escalate (case id + form draft hints)

Departments: returns, billing, tech, orders, general, sales.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
import uuid
from typing import Any

from . import config
from . import support_memory as csmem

DEPARTMENTS = {
    "returns": "退貨與退款",
    "billing": "帳單與付款",
    "tech": "技術支援",
    "orders": "訂單與物流",
    "sales": "業務／方案諮詢",
    "general": "一般詢問",
}

# Lightweight FAQ / policy snippets (demo seed — replace with real KB later)
FAQ_KB: list[dict[str, str]] = [
    {
        "id": "faq_return",
        "dept": "returns",
        "title": "退貨期限",
        "text": "標準商品到貨後 7 日內可申請退貨；開封耗材不適用。退款於審核後 5–10 個工作天入帳。",
    },
    {
        "id": "faq_refund",
        "dept": "returns",
        "title": "退款方式",
        "text": "退款原路退回；若信用卡已結帳，可能顯示於下一期帳單。可申請商店點數加速處理。",
    },
    {
        "id": "faq_bill",
        "dept": "billing",
        "title": "發票與請款",
        "text": "企業客戶可開立電子發票／統編；週結與月結方案需業務開通。重複扣款請提供交易編號。",
    },
    {
        "id": "faq_pay",
        "dept": "billing",
        "title": "付款方式",
        "text": "支援信用卡、ATM、企業匯款。逾期帳款將暫停加值服務直到結清。",
    },
    {
        "id": "faq_tech",
        "dept": "tech",
        "title": "登入與 API",
        "text": "無法登入請先重設密碼；API 401 多為 key 過期。SLA：企業方案工作日 4 小時內回覆。",
    },
    {
        "id": "faq_outage",
        "dept": "tech",
        "title": "服務異常",
        "text": "全面性故障會公告狀態頁。單一帳號問題請提供帳號 ID 與錯誤截圖。",
    },
    {
        "id": "faq_ship",
        "dept": "orders",
        "title": "出貨與追蹤",
        "text": "現貨 1–2 工作日出貨；可提供物流單號。延遲超過 3 日可升級承運商協查。",
    },
    {
        "id": "faq_order",
        "dept": "orders",
        "title": "改地址與取消",
        "text": "未出貨前可改地址或取消；已出貨僅能拒收退回。請提供訂單編號。",
    },
    {
        "id": "faq_plan",
        "dept": "sales",
        "title": "方案與報價",
        "text": "成長方案含 CRM 看板與 AI 文案；企業方案可客製 SLA。正式報價由業務提供。",
    },
    {
        "id": "faq_demo",
        "dept": "sales",
        "title": "預約演示",
        "text": "可於官網表單或客服協助預約 30 分鐘演示；請留下公司與需求。",
    },
]

SIGNAL_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("legal", re.compile(r"律師|法律|消保|起訴| consum|lawsuit|attorney|GDPR|個資法", re.I)),
    ("frustration", re.compile(r"爛|垃圾|詐欺|騙|氣死|受不了|扯|complaint|furious|scam", re.I)),
    ("urgent", re.compile(r"立刻|馬上|緊急|今天|asap|urgent|right now", re.I)),
    ("repeat", re.compile(r"第.?次|又|仍然|還是|again|still not|第三次", re.I)),
    ("refund_push", re.compile(r"一定要退|強制退款|chargeback|拒付", re.I)),
]


def detect_signals(text: str) -> list[str]:
    hits = []
    for name, pat in SIGNAL_RULES:
        if pat.search(text or ""):
            hits.append(name)
    return hits


def retrieve_faq(query: str, limit: int = 4) -> list[dict[str, str]]:
    q = (query or "").lower()
    tokens = [t for t in re.split(r"[\s,，。；;、]+", q) if len(t) >= 2]
    scored: list[tuple[float, dict]] = []
    for doc in FAQ_KB:
        blob = f"{doc['title']} {doc['text']} {doc['dept']}".lower()
        score = 0.0
        for t in tokens:
            if t in blob:
                score += 1.0
        if any(k in blob for k in ("退", "refund") if "退" in q or "refund" in q):
            if doc["dept"] == "returns":
                score += 0.5
        if score > 0:
            scored.append((score, doc))
    scored.sort(key=lambda x: x[0], reverse=True)
    if not scored:
        # soft default: general snippets
        return FAQ_KB[-2:]
    return [d for _, d in scored[:limit]]


def _extract_text(message: dict) -> str:
    content = (message.get("content") or "").strip()
    reason = (message.get("reasoning_content") or "").strip()
    for blob in (content, reason, f"{content}\n{reason}"):
        if blob.strip():
            return blob
    return ""


def _chat_qwen(system: str, user: str, max_tokens: int = 900) -> str:
    payload = {
        "model": config.QWEN_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
        "max_tokens": max_tokens,
        "chat_template_kwargs": {"enable_thinking": False},
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
        raise RuntimeError(f"Qwen HTTP {e.code}: {err[:400]}") from e
    choice = (raw.get("choices") or [{}])[0]
    return _extract_text(choice.get("message") or {})


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


def _fallback_decision(query: str, signals: list[str], faq: list[dict]) -> dict:
    """Deterministic fallback if LLM JSON fails."""
    action = "escalate" if any(
        s in signals for s in ("legal", "frustration", "urgent", "refund_push")
    ) else "resolve"
    dept = "general"
    q = query.lower()
    if any(k in q for k in ("退", "refund", "換貨")):
        dept = "returns"
    elif any(k in q for k in ("帳單", "發票", "付款", "扣款", "bill")):
        dept = "billing"
    elif any(k in q for k in ("登入", "api", "錯誤", "掛了", "bug")):
        dept = "tech"
    elif any(k in q for k in ("訂單", "物流", "出貨", "延遲", "order")):
        dept = "orders"
    elif any(k in q for k in ("方案", "報價", "演示", "合作")):
        dept = "sales"
    conf = "low" if not faq else ("medium" if action == "resolve" else "low")
    if action == "escalate":
        conf = "low"
    return {
        "department": dept,
        "action": action,
        "confidence": conf,
        "reason_zh": "規則後備：訊號或關鍵字判定（LLM 輸出無法解析）",
    }


def orchestrate(
    query: str,
    signals: list[str],
    faq: list[dict],
    memories: list[dict],
) -> dict[str, Any]:
    system = (
        "你是客服路由編排器。只輸出 JSON，不要思考過程：\n"
        "{\n"
        '  "department": "returns|billing|tech|orders|sales|general",\n'
        '  "action": "resolve|escalate",\n'
        '  "confidence": "high|medium|low",\n'
        '  "reason_zh": "一句繁中理由"\n'
        "}\n"
        "規則：legal/frustration/urgent/refund_push 傾向 escalate；"
        "FAQ 高度相關且無危險訊號 → resolve；資料不足 → escalate 或 low+resolve 謹慎。"
    )
    user = (
        f"查詢：{query}\n"
        f"訊號：{signals}\n"
        f"FAQ：{json.dumps(faq, ensure_ascii=False)}\n"
        f"客戶記憶：{json.dumps([m.get('memory') for m in memories[:5]], ensure_ascii=False)}\n"
    )
    try:
        raw = _chat_qwen(system, user, max_tokens=400)
        data = _parse_json(raw)
        dept = data.get("department") or "general"
        if dept not in DEPARTMENTS:
            dept = "general"
        action = data.get("action") if data.get("action") in ("resolve", "escalate") else "resolve"
        conf = data.get("confidence") if data.get("confidence") in ("high", "medium", "low") else "medium"
        # force escalate on hard signals
        if any(s in signals for s in ("legal", "frustration", "refund_push")):
            action = "escalate"
            conf = "low"
        return {
            "department": dept,
            "action": action,
            "confidence": conf,
            "reason_zh": data.get("reason_zh") or "",
        }
    except Exception:  # noqa: BLE001
        return _fallback_decision(query, signals, faq)


def _resolve_reply(query: str, dept: str, faq: list[dict], memories: list[dict]) -> str:
    ctx = "\n".join(f"- {d['title']}: {d['text']}" for d in faq)
    mem = "\n".join(f"- {m.get('memory')}" for m in memories[:5]) or "- （無）"
    system = (
        "你是 CATCH 客服，使用繁體中文。根據 FAQ 與客戶記憶回答，"
        "不要編造訂單狀態或政策外承諾。若資料不足請說明並建議提供訂單號。"
        f"部門：{DEPARTMENTS.get(dept, dept)}"
    )
    user = f"FAQ：\n{ctx}\n記憶：\n{mem}\n客戶：{query}\n"
    return _chat_qwen(system, user, max_tokens=700).strip()


def _escalate_reply(query: str, dept: str, case_id: str, reason: str) -> str:
    dept_zh = DEPARTMENTS.get(dept, dept)
    return (
        f"已為您建立升級案件 **{case_id}**，轉交【{dept_zh}】專人處理。\n"
        f"原因：{reason or '需人工審核'}。\n"
        f"預計回覆時窗：工作日 4–8 小時內（演示）。\n"
        f"請在右側「服務申請表」確認聯絡資料後提交，方便專人聯繫。"
        f"\n（您的問題摘要已記入案件，無需重述全部細節。）"
    )


def route_query(customer_id: str, message: str) -> dict[str, Any]:
    message = (message or "").strip()
    if not message:
        raise ValueError("empty message")
    cid = csmem._norm_user(customer_id)

    signals = detect_signals(message)
    faq = retrieve_faq(message, limit=4)
    memories = csmem.search_memories(cid, message, limit=6)
    decision = orchestrate(message, signals, faq, memories)

    case_id = None
    form_hints: dict[str, str] = {}
    if decision["action"] == "escalate":
        case_id = f"ESC-{uuid.uuid4().hex[:6].upper()}"
        reply = _escalate_reply(
            message, decision["department"], case_id, decision.get("reason_zh") or ""
        )
        form_hints = {
            "contact": cid if cid != "guest" else "",
            "need": f"[{DEPARTMENTS.get(decision['department'])}] {message[:400]}",
            "channel": "客服路由升級",
        }
        try:
            csmem.add_memory(
                cid,
                f"升級案件 {case_id}（{DEPARTMENTS.get(decision['department'])}）：{message[:120]}",
                kind="escalate",
            )
        except Exception:  # noqa: BLE001
            pass
    else:
        reply = _resolve_reply(message, decision["department"], faq, memories)
        try:
            csmem.add_memory(
                cid,
                f"已自動回覆（{DEPARTMENTS.get(decision['department'])}）：{message[:80]}",
                kind="resolve",
            )
        except Exception:  # noqa: BLE001
            pass

    return {
        "customer_id": cid,
        "message": message,
        "signals": signals,
        "faq_hits": faq,
        "relevant_memories": memories,
        "decision": {
            **decision,
            "department_zh": DEPARTMENTS.get(decision["department"], decision["department"]),
        },
        "action": decision["action"],
        "case_id": case_id,
        "reply": reply,
        "form_hints": form_hints,
        "ts": int(time.time()),
        "memories": csmem.list_memories(cid, 40),
    }


def list_departments() -> dict[str, str]:
    return dict(DEPARTMENTS)
