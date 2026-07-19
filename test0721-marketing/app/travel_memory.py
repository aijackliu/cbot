"""
AI Travel Agent with Memory — API layer for demo.

Pattern adapted from awesome-llm-apps ai_travel_agent_memory
(Mem0 + Qdrant → Redis-backed memory for this stack).
"""

from __future__ import annotations

import json
import re
import time
import uuid
import urllib.error
import urllib.request
from typing import Any

import redis

from . import config

MEM_PREFIX = "mkt:travel:mem:"
USER_SET = "mkt:travel:users"
CHAT_PREFIX = "mkt:travel:chat:"


def _redis() -> redis.Redis:
    return redis.Redis(
        host=config.REDIS_HOST,
        port=config.REDIS_PORT,
        decode_responses=True,
        socket_connect_timeout=3,
    )


def _extract_reply(message: dict) -> str:
    content = (message.get("content") or "").strip()
    if content:
        return content
    reason = message.get("reasoning_content") or ""
    cands = re.findall(r"[\u4e00-\u9fff][^。！？\n]{8,160}[。！？]", reason)
    if cands:
        return "\n".join(cands[-6:])
    return reason.strip()[-1500:] if reason.strip() else "（模型未回傳內容）"


def _chat_qwen(system: str, user: str, max_tokens: int = 900) -> dict[str, Any]:
    payload = {
        "model": config.QWEN_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.4,
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
        raise RuntimeError(f"Qwen HTTP {e.code}: {err[:400]}") from e

    choice = (raw.get("choices") or [{}])[0]
    text = _extract_reply(choice.get("message") or {})
    return {
        "reply": text,
        "model": raw.get("model") or config.QWEN_MODEL,
        "usage": raw.get("usage"),
    }


def add_memory(user_id: str, text: str, role: str = "user") -> dict:
    user_id = (user_id or "").strip() or "guest"
    text = (text or "").strip()
    if not text:
        raise ValueError("empty memory text")
    r = _redis()
    mid = uuid.uuid4().hex[:12]
    item = {
        "id": mid,
        "memory": text,
        "role": role,
        "ts": int(time.time()),
    }
    key = f"{MEM_PREFIX}{user_id}"
    r.lpush(key, json.dumps(item, ensure_ascii=False))
    r.ltrim(key, 0, 199)  # keep last 200
    r.sadd(USER_SET, user_id)
    return item


def get_all_memories(user_id: str, limit: int = 50) -> list[dict]:
    user_id = (user_id or "").strip() or "guest"
    r = _redis()
    raw = r.lrange(f"{MEM_PREFIX}{user_id}", 0, max(0, limit - 1))
    out = []
    for row in raw:
        try:
            out.append(json.loads(row))
        except json.JSONDecodeError:
            continue
    return out


def search_memories(user_id: str, query: str, limit: int = 8) -> list[dict]:
    """Simple relevance: keyword overlap score (demo; Mem0 used vectors)."""
    query = (query or "").lower()
    tokens = [t for t in re.split(r"[\s,，。；;、]+", query) if len(t) >= 2]
    scored: list[tuple[float, dict]] = []
    for mem in get_all_memories(user_id, limit=200):
        text = (mem.get("memory") or "").lower()
        if not text:
            continue
        score = 0.0
        if query and query in text:
            score += 3.0
        for t in tokens:
            if t in text:
                score += 1.0
        # recency bonus
        score += min((mem.get("ts") or 0) / 1e12, 0.5)
        if score > 0:
            scored.append((score, mem))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [m for _, m in scored[:limit]]


def clear_memories(user_id: str) -> int:
    r = _redis()
    key = f"{MEM_PREFIX}{user_id}"
    n = r.llen(key)
    r.delete(key)
    r.delete(f"{CHAT_PREFIX}{user_id}")
    return int(n)


def seed_demo_user(user_id: str = "demo_traveler") -> list[dict]:
    """Seed fake travel preferences for showcase."""
    samples = [
        ("user", "我偏好不趕行程，一天最多兩個景點。"),
        ("user", "喜歡自然風景與咖啡店，不太愛主題樂園。"),
        ("user", "預算中等，雙人，喜歡坐火車而不是長途巴士。"),
        ("assistant", "已記住：慢旅行、自然與咖啡、中等預算雙人、偏好火車。"),
        ("user", "對過敏：不吃堅果。"),
    ]
    existing = get_all_memories(user_id, 5)
    if existing:
        return existing
    for role, text in samples:
        add_memory(user_id, text, role=role)
    return get_all_memories(user_id)


def chat(user_id: str, prompt: str) -> dict[str, Any]:
    user_id = (user_id or "").strip() or "guest"
    prompt = (prompt or "").strip()
    if not prompt:
        raise ValueError("empty prompt")

    relevant = search_memories(user_id, prompt, limit=8)
    context = "Relevant past information:\n"
    if relevant:
        for mem in relevant:
            context += f"- {mem.get('memory')}\n"
    else:
        context += "- (no prior memories)\n"

    system = (
        "You are a helpful travel assistant with access to past conversations and preferences. "
        "Reply in Traditional Chinese unless the user writes only in English. "
        "Use memories when relevant; do not invent past trips the user never mentioned. "
        "Give practical itinerary suggestions with rough day structure."
    )
    full_prompt = f"{context}\nHuman: {prompt}\nAI:"

    result = _chat_qwen(system, full_prompt)
    answer = result["reply"]

    # Persist like upstream: store user query + assistant answer
    add_memory(user_id, prompt, role="user")
    add_memory(user_id, answer[:800], role="assistant")

    # short chat log for UI
    r = _redis()
    chat_key = f"{CHAT_PREFIX}{user_id}"
    r.rpush(
        chat_key,
        json.dumps({"role": "user", "content": prompt, "ts": int(time.time())}, ensure_ascii=False),
    )
    r.rpush(
        chat_key,
        json.dumps(
            {"role": "assistant", "content": answer, "ts": int(time.time())},
            ensure_ascii=False,
        ),
    )
    r.ltrim(chat_key, -40, -1)

    return {
        "reply": answer,
        "model": result.get("model"),
        "usage": result.get("usage"),
        "relevant_memories": relevant,
        "user_id": user_id,
    }


def get_chat_history(user_id: str, limit: int = 40) -> list[dict]:
    r = _redis()
    raw = r.lrange(f"{CHAT_PREFIX}{user_id}", 0, -1)
    rows = []
    for row in raw[-limit:]:
        try:
            rows.append(json.loads(row))
        except json.JSONDecodeError:
            continue
    return rows
