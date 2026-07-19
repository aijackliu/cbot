"""
Agentic form-fill (demo): multi-turn chat fills a CRM service form.

Inspired by Hands-On agentic-form-filler pattern, but uses LAN Qwen only
(no Landing AI / MiniMax).
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

# Demo form: 客服／業務服務申請
FORM_TEMPLATE = {
    "id": "service_request",
    "title": "客服服務申請表",
    "description": "對話補齊欄位後可提交（演示寫入 Redis）",
    "fields": [
        {
            "key": "company",
            "label": "公司名稱",
            "required": True,
            "placeholder": "例：CATCH 數位",
        },
        {
            "key": "contact",
            "label": "聯絡人",
            "required": True,
            "placeholder": "姓名",
        },
        {
            "key": "phone",
            "label": "電話",
            "required": True,
            "placeholder": "09xx…",
        },
        {
            "key": "email",
            "label": "Email",
            "required": False,
            "placeholder": "name@example.com",
        },
        {
            "key": "need",
            "label": "需求說明",
            "required": True,
            "placeholder": "想解決什麼問題？",
            "multiline": True,
        },
        {
            "key": "budget",
            "label": "預算區間",
            "required": False,
            "placeholder": "例：30–50 萬／年",
        },
        {
            "key": "timeline",
            "label": "期望時程",
            "required": False,
            "placeholder": "例：本季內",
        },
        {
            "key": "channel",
            "label": "來源管道",
            "required": False,
            "placeholder": "官網／介紹／廣告",
        },
    ],
}

REDIS_DRAFT = "crm:form:draft:"
REDIS_SUBMIT = "crm:form:submissions"


def _extract_text(message: dict) -> str:
    content = (message.get("content") or "").strip()
    reason = (message.get("reasoning_content") or "").strip()
    for blob in (content, reason, f"{content}\n{reason}"):
        if "{" in blob and "}" in blob:
            return blob
    if content:
        return content
    cands = re.findall(r"[\u4e00-\u9fff][^。！？\n]{6,120}[。！？]", reason)
    if cands:
        return "\n".join(cands[-4:])
    return reason.strip()[-800:] if reason.strip() else ""


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


def _parse_json_obj(text: str) -> dict:
    text = (text or "").strip()
    text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.I)
    if "```" in text:
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if m:
            text = m.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("expected object")
    return data


def empty_values() -> dict[str, str]:
    return {f["key"]: "" for f in FORM_TEMPLATE["fields"]}


def missing_fields(values: dict[str, str]) -> list[dict]:
    out = []
    for f in FORM_TEMPLATE["fields"]:
        if not f.get("required"):
            continue
        v = (values.get(f["key"]) or "").strip()
        if not v:
            out.append({"key": f["key"], "label": f["label"]})
    return out


def merge_values(base: dict[str, str], patch: dict) -> dict[str, str]:
    out = dict(base or empty_values())
    for f in FORM_TEMPLATE["fields"]:
        k = f["key"]
        if k in patch and patch[k] is not None:
            s = str(patch[k]).strip()
            if s and s.lower() not in ("null", "none", "未知", "n/a"):
                out[k] = s
    return out


def form_turn(
    user_message: str,
    values: dict[str, str] | None = None,
    history: list[dict] | None = None,
) -> dict[str, Any]:
    """One agentic turn: extract fields + reply + next question."""
    current = merge_values(empty_values(), values or {})
    keys = [f["key"] for f in FORM_TEMPLATE["fields"]]
    labels = {f["key"]: f["label"] for f in FORM_TEMPLATE["fields"]}
    missing = missing_fields(current)

    system = (
        "你是 CATCH CRM 客服填表助理。用繁體中文。\n"
        "任務：從使用者訊息抽出表單欄位，回覆親切短句，並指出還缺什麼。\n"
        "只輸出一個 JSON 物件，不要思考過程。格式：\n"
        '{"fields":{"company":"…",...},"reply":"…","ask_next":"下一個要問的問題或空字串"}\n'
        f"可填 key：{keys}\n"
        f"中文標籤：{json.dumps(labels, ensure_ascii=False)}\n"
        "fields 只含這次能確定的欄位；不要編造電話或 Email。"
    )
    hist = ""
    if history:
        for h in history[-6:]:
            hist += f"{h.get('role','user')}: {h.get('content','')}\n"
    user = (
        f"目前已填：{json.dumps(current, ensure_ascii=False)}\n"
        f"仍缺必填：{[m['label'] for m in missing]}\n"
        f"最近對話：\n{hist}\n"
        f"使用者本則：{user_message}"
    )

    raw = _chat_qwen(system, user, max_tokens=700)
    try:
        data = _parse_json_obj(raw)
    except (json.JSONDecodeError, ValueError):
        data = {
            "fields": {},
            "reply": "我收到了。請再提供公司名稱、聯絡人與需求說明，我幫你填表。",
            "ask_next": "請問公司名稱與聯絡人是？",
        }

    patch = data.get("fields") if isinstance(data.get("fields"), dict) else {}
    new_values = merge_values(current, patch)
    still = missing_fields(new_values)
    reply = (data.get("reply") or "").strip()
    ask = (data.get("ask_next") or "").strip()
    if not reply:
        if still:
            reply = f"已更新部分欄位。還需要：{'、'.join(m['label'] for m in still)}。"
        else:
            reply = "表單必填已齊，請右側確認後按「提交申請」。"
    if still and not ask:
        ask = f"還請補充：{still[0]['label']}？"
    if not still:
        ask = ""

    return {
        "values": new_values,
        "missing": still,
        "complete": len(still) == 0,
        "reply": reply,
        "ask_next": ask,
        "patched_keys": list(patch.keys()) if patch else [],
    }


def apply_manual(values: dict[str, str]) -> dict[str, Any]:
    v = merge_values(empty_values(), values)
    still = missing_fields(v)
    return {
        "values": v,
        "missing": still,
        "complete": len(still) == 0,
    }


def save_draft(session_id: str, values: dict[str, str]) -> None:
    import redis

    r = redis.Redis(
        host=config.REDIS_HOST,
        port=config.REDIS_PORT,
        decode_responses=True,
        socket_connect_timeout=2,
    )
    r.setex(
        f"{REDIS_DRAFT}{session_id}",
        86400,
        json.dumps(values, ensure_ascii=False),
    )


def submit_form(values: dict[str, str], session_id: str | None = None) -> dict:
    v = merge_values(empty_values(), values)
    still = missing_fields(v)
    if still:
        raise ValueError(
            "缺少必填：" + "、".join(m["label"] for m in still)
        )
    import redis

    r = redis.Redis(
        host=config.REDIS_HOST,
        port=config.REDIS_PORT,
        decode_responses=True,
        socket_connect_timeout=2,
    )
    sid = session_id or uuid.uuid4().hex[:12]
    rec = {
        "id": uuid.uuid4().hex[:12],
        "session_id": sid,
        "form_id": FORM_TEMPLATE["id"],
        "values": v,
        "ts": int(time.time()),
    }
    r.lpush(REDIS_SUBMIT, json.dumps(rec, ensure_ascii=False))
    r.ltrim(REDIS_SUBMIT, 0, 99)
    r.delete(f"{REDIS_DRAFT}{sid}")
    return rec


def list_submissions(limit: int = 20) -> list[dict]:
    import redis

    r = redis.Redis(
        host=config.REDIS_HOST,
        port=config.REDIS_PORT,
        decode_responses=True,
        socket_connect_timeout=2,
    )
    rows = r.lrange(REDIS_SUBMIT, 0, max(0, limit - 1))
    out = []
    for row in rows:
        try:
            out.append(json.loads(row))
        except json.JSONDecodeError:
            continue
    return out
