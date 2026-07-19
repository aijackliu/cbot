"""
CartMate-style customer support memory (Redis, per customer_id).

Pattern from Hands-On ai_customer_support_agent (Mem0 → Redis for this stack).
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

MEM_PREFIX = "crm:cs:mem:"
USER_SET = "crm:cs:users"
CHAT_PREFIX = "crm:cs:chat:"


def _redis():
    import redis

    return redis.Redis(
        host=config.REDIS_HOST,
        port=config.REDIS_PORT,
        decode_responses=True,
        socket_connect_timeout=2,
    )


def _norm_user(customer_id: str) -> str:
    u = (customer_id or "").strip()
    u = re.sub(r"\s+", "_", u)
    return u[:64] or "guest"


def add_memory(customer_id: str, text: str, kind: str = "fact") -> dict:
    cid = _norm_user(customer_id)
    text = (text or "").strip()
    if not text:
        raise ValueError("empty memory")
    r = _redis()
    item = {
        "id": uuid.uuid4().hex[:12],
        "memory": text[:800],
        "kind": kind,
        "ts": int(time.time()),
    }
    key = f"{MEM_PREFIX}{cid}"
    r.lpush(key, json.dumps(item, ensure_ascii=False))
    r.ltrim(key, 0, 99)
    r.sadd(USER_SET, cid)
    return item


def list_memories(customer_id: str, limit: int = 40) -> list[dict]:
    cid = _norm_user(customer_id)
    raw = _redis().lrange(f"{MEM_PREFIX}{cid}", 0, max(0, limit - 1))
    out = []
    for row in raw:
        try:
            out.append(json.loads(row))
        except json.JSONDecodeError:
            continue
    return out


def search_memories(customer_id: str, query: str, limit: int = 8) -> list[dict]:
    q = (query or "").lower()
    tokens = [t for t in re.split(r"[\s,，。；;、#]+", q) if len(t) >= 2]
    scored: list[tuple[float, dict]] = []
    for mem in list_memories(customer_id, 100):
        text = (mem.get("memory") or "").lower()
        if not text:
            continue
        score = 0.0
        if q and q in text:
            score += 3.0
        for t in tokens:
            if t in text:
                score += 1.0
        score += 0.01  # keep recent even if weak match
        if score > 0:
            scored.append((score, mem))
    scored.sort(key=lambda x: x[0], reverse=True)
    # if nothing matched, return most recent
    if not scored:
        return list_memories(customer_id, limit)
    return [m for _, m in scored[:limit]]


def clear_memories(customer_id: str) -> int:
    cid = _norm_user(customer_id)
    r = _redis()
    key = f"{MEM_PREFIX}{cid}"
    n = int(r.llen(key))
    r.delete(key)
    r.delete(f"{CHAT_PREFIX}{cid}")
    return n


def seed_demo(customer_id: str = "Alex") -> list[dict]:
    cid = _norm_user(customer_id)
    existing = list_memories(cid, 3)
    if existing:
        return existing
    samples = [
        f"{customer_id} 回報訂單 #NM-8821 延遲 3 天，已升級承運商調查。",
        f"{customer_id} 偏好 Email 通知，不要簡訊。",
        f"{customer_id} 是 NovaMart／CATCH 展示客戶，曾詢問 VIP 退換貨政策。",
        "上次對話結束於：等待物流追蹤號碼。",
    ]
    for s in samples:
        add_memory(cid, s, kind="seed")
    return list_memories(cid)


def _extract_text(message: dict) -> str:
    content = (message.get("content") or "").strip()
    reason = (message.get("reasoning_content") or "").strip()
    if content:
        return content
    cands = re.findall(r"[\u4e00-\u9fff][^。！？\n]{6,120}[。！？]", reason)
    if cands:
        return "\n".join(cands[-5:])
    return reason.strip()[-600:] if reason.strip() else "（無內容）"


def _chat_qwen(system: str, user: str, max_tokens: int = 900) -> str:
    payload = {
        "model": config.QWEN_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.35,
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


def _extract_facts(customer_id: str, user_msg: str, reply: str) -> list[str]:
    """Ask model for 0–3 short facts to store; pipe-safe lines."""
    system = (
        "從客服對話抽出應長期記住的事實（訂單號、偏好、投訴狀態）。"
        "輸出 0～3 行，每行一句繁中事實，不要編號。無關則輸出空。"
        "不要輸出思考過程。"
    )
    user = f"客戶：{customer_id}\n客戶說：{user_msg}\n客服回：{reply[:400]}\n"
    try:
        raw = _chat_qwen(system, user, max_tokens=200)
    except Exception:  # noqa: BLE001
        return []
    facts = []
    for line in raw.splitlines():
        line = line.strip(" -•\t")
        if len(line) < 6 or line.startswith("{"):
            continue
        if "無" == line or "没有" in line[:4] or "沒有需要" in line:
            continue
        facts.append(line[:200])
        if len(facts) >= 3:
            break
    return facts


def support_chat(customer_id: str, message: str) -> dict[str, Any]:
    """Recall memories → answer → store new facts (CartMate loop)."""
    cid = _norm_user(customer_id)
    message = (message or "").strip()
    if not message:
        raise ValueError("empty message")

    relevant = search_memories(cid, message, limit=8)
    mem_block = "\n".join(f"- {m.get('memory')}" for m in relevant) or "- （尚無記憶）"

    system = (
        "你是 CATCH／展示電商的客服代理 CartMate 風格助理，使用繁體中文。"
        f"客戶識別名稱：{cid}。"
        "要自然引用已知記憶（訂單、偏好、未結案問題），不要編造不存在的物流狀態。"
        "若記憶不足，可請客戶補充訂單號；可建議改用「填表」建案或「中文查庫」查 CRM。"
        f"\n【客戶記憶】\n{mem_block}\n"
    )
    reply = _chat_qwen(system, message, max_tokens=700)

    # persist chat
    r = _redis()
    chat_key = f"{CHAT_PREFIX}{cid}"
    r.rpush(
        chat_key,
        json.dumps(
            {"role": "user", "content": message, "ts": int(time.time())},
            ensure_ascii=False,
        ),
    )
    r.rpush(
        chat_key,
        json.dumps(
            {"role": "assistant", "content": reply, "ts": int(time.time())},
            ensure_ascii=False,
        ),
    )
    r.ltrim(chat_key, -40, -1)

    new_facts = _extract_facts(cid, message, reply)
    stored = []
    for f in new_facts:
        stored.append(add_memory(cid, f, kind="auto"))

    # always store a thin trail of user utterance if it looks factual
    if any(x in message for x in ("訂單", "order", "#", "延遲", "退", "偏好", "不要", "Email", "電話")):
        if not stored:
            stored.append(add_memory(cid, f"客戶提及：{message[:160]}", kind="utterance"))

    return {
        "customer_id": cid,
        "reply": reply,
        "relevant_memories": relevant,
        "new_memories": stored,
        "memories": list_memories(cid, 40),
    }


def greeting(customer_id: str) -> dict[str, Any]:
    cid = _norm_user(customer_id)
    mems = list_memories(cid, 10)
    if not mems:
        return {
            "customer_id": cid,
            "returning": False,
            "reply": f"你好，{cid}！我是 CATCH 客服 AI（記憶版）。有什麼可以幫你？",
            "memories": [],
        }
    tops = "；".join(m.get("memory", "")[:40] for m in mems[:3])
    return {
        "customer_id": cid,
        "returning": True,
        "reply": (
            f"歡迎回來，{cid}！我還記得你的紀錄。"
            f"例如：{tops}。"
            "要從上次的問題繼續，還是有新需求？"
        ),
        "memories": mems,
    }
