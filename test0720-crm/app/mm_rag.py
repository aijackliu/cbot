"""
Lightweight Multimodal RAG (Hands-On multimodal_rag 精簡版)
+ HyDE retrieval (Hands-On hyde_rag 精簡版).

- Sources: text / URL / image / audio (no ChromaDB, no LangChain)
- Index: Redis (crm:mmrag:*) + local media under data/mm_rag/
- Embed: Gemini text-embedding-004 (fallback: bag-of-words cosine)
- Optional HyDE: generate N hypothetical answers → embed → average → retrieve
- Answer: Gemini (+ media re-attach); Qwen fallback

Patterns:
  multimodal_rag · hyde_rag
  https://github.com/Sumanth077/Hands-On-AI-Engineering
"""

from __future__ import annotations

import base64
import hashlib
import html
import json
import math
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

import redis

from . import config

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "mm_rag"
INDEX_KEY = "crm:mmrag:chunks_v1"
SOURCES_KEY = "crm:mmrag:sources_v1"

CHUNK_SIZE = 480
CHUNK_OVERLAP = 80
TOP_K = 5
HYDE_N_DEFAULT = 3

MEDIA_PROMPTS = {
    "image": (
        "用繁體中文詳細描述這張圖：可見文字、物件、場景、版面與任何對客服／產品有用的資訊。"
    ),
    "audio": (
        "用繁體中文完整轉寫並描述這段音訊：語音原文、語調、背景音與重點摘要。"
    ),
}


def _redis() -> redis.Redis:
    return redis.Redis(
        host=config.REDIS_HOST,
        port=config.REDIS_PORT,
        decode_responses=True,
        socket_connect_timeout=3,
    )


def _gemini_key() -> str:
    key = config.GOOGLE_AI_API_KEY or ""
    if not key:
        raise RuntimeError("未設定 GOOGLE_AI_API_KEY")
    return key


def _gen_model() -> str:
    return (
        getattr(config, "GEMINI_AUDIO_MODEL", None)
        or config.GEMINI_VISION_MODEL
        or "gemini-2.0-flash"
    )


def _embed_model() -> str:
    return getattr(config, "GEMINI_EMBED_MODEL", None) or "text-embedding-004"


def _chunk(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        return []
    if len(text) <= size:
        return [text]
    out: list[str] = []
    i = 0
    step = max(1, size - overlap)
    while i < len(text):
        out.append(text[i : i + size])
        i += step
    return out


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return -1.0
    dot = na = nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0 or nb <= 0:
        return -1.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def _bow_vec(text: str) -> list[float]:
    """Fallback bag over hashed tokens + CJK char bigrams (fixed dim)."""
    dim = 384
    vec = [0.0] * dim
    text = (text or "").lower()
    tokens = re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]+", text)
    features: list[str] = []
    for t in tokens:
        features.append(t)
        # character unigrams / bigrams for Chinese recall
        if re.search(r"[\u4e00-\u9fff]", t):
            for ch in t:
                features.append(ch)
            for i in range(len(t) - 1):
                features.append(t[i : i + 2])
    if not features:
        return vec
    for t in features:
        h = int(hashlib.md5(t.encode("utf-8")).hexdigest(), 16)
        vec[h % dim] += 1.0
    n = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / n for x in vec]


def embed_text(text: str) -> tuple[list[float], str]:
    """Return (vector, method). Prefer Gemini embedding API."""
    text = (text or "").strip()[:6000]
    if not text:
        return [], "empty"
    key = config.GOOGLE_AI_API_KEY
    if key:
        model = _embed_model()
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:embedContent?key={urllib.parse.quote(key, safe='')}"
        )
        body = {
            "model": f"models/{model}",
            "content": {"parts": [{"text": text}]},
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
            emb = (
                (raw.get("embedding") or {}).get("values")
                or (raw.get("embeddings") or [{}])[0].get("values")
            )
            if emb:
                return [float(x) for x in emb], f"gemini:{model}"
        except Exception:  # noqa: BLE001
            pass
    return _bow_vec(text), "bow-fallback"


def _gemini_generate(parts: list[dict], temperature: float = 0.3) -> str:
    key = _gemini_key()
    model = _gen_model()
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={urllib.parse.quote(key, safe='')}"
    )
    body = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": 4096,
        },
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini HTTP {e.code}: {err[:500]}") from e
    cands = raw.get("candidates") or []
    if not cands:
        raise RuntimeError("Gemini 無 candidates")
    text = "".join(
        p.get("text") or ""
        for p in ((cands[0].get("content") or {}).get("parts") or [])
    ).strip()
    text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.I).strip()
    if not text:
        raise RuntimeError("Gemini 回傳空白")
    return text


def _describe_media(data: bytes, mime: str, kind: str) -> str:
    b64 = base64.b64encode(data).decode("ascii")
    prompt = MEDIA_PROMPTS.get(kind, "用繁體中文詳細描述此媒體。")
    return _gemini_generate(
        [
            {"text": prompt},
            {"inline_data": {"mime_type": mime, "data": b64}},
        ],
        temperature=0.2,
    )


def _load_chunks() -> list[dict[str, Any]]:
    try:
        raw = _redis().get(INDEX_KEY)
        if not raw:
            return []
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except Exception:  # noqa: BLE001
        return []


def _save_chunks(chunks: list[dict[str, Any]]) -> None:
    _redis().set(INDEX_KEY, json.dumps(chunks, ensure_ascii=False))


def _load_sources() -> list[dict[str, Any]]:
    try:
        raw = _redis().get(SOURCES_KEY)
        if not raw:
            return []
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except Exception:  # noqa: BLE001
        return []


def _save_sources(sources: list[dict[str, Any]]) -> None:
    _redis().set(SOURCES_KEY, json.dumps(sources, ensure_ascii=False))


def _append_source(src: dict[str, Any], chunk_rows: list[dict[str, Any]]) -> dict[str, Any]:
    chunks = _load_chunks()
    chunks.extend(chunk_rows)
    # cap index size for demo
    if len(chunks) > 400:
        chunks = chunks[-400:]
    _save_chunks(chunks)
    sources = _load_sources()
    sources.append(src)
    if len(sources) > 80:
        sources = sources[-80:]
    _save_sources(sources)
    return {"ok": True, "source": src, "chunks_added": len(chunk_rows), "index_size": len(chunks)}


def stats() -> dict[str, Any]:
    chunks = _load_chunks()
    sources = _load_sources()
    by_type: dict[str, int] = {}
    for s in sources:
        t = s.get("source_type") or "unknown"
        by_type[t] = by_type.get(t, 0) + 1
    return {
        "ok": True,
        "sources": len(sources),
        "chunks": len(chunks),
        "by_type": by_type,
        "items": list(reversed(sources[-30:])),
        "redis": f"{config.REDIS_HOST}:{config.REDIS_PORT}",
        "embed_model": _embed_model(),
        "gen_model": _gen_model(),
    }


def clear_index() -> dict[str, Any]:
    try:
        r = _redis()
        r.delete(INDEX_KEY)
        r.delete(SOURCES_KEY)
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"Redis clear failed: {e}") from e
    # keep media files (optional cleanup)
    return {"ok": True, "cleared": True}


def add_text(text: str, label: str = "貼上文字") -> dict[str, Any]:
    text = (text or "").strip()
    if not text:
        raise ValueError("文字為空")
    parts = _chunk(text)
    sid = uuid.uuid4().hex[:10]
    rows = []
    emb_method = ""
    for i, p in enumerate(parts):
        vec, method = embed_text(p)
        emb_method = method
        rows.append(
            {
                "id": f"{sid}_{i}",
                "source_id": sid,
                "source_type": "text",
                "source_label": label[:120],
                "text": p,
                "embedding": vec,
                "media_path": "",
                "mime_type": "",
            }
        )
    src = {
        "id": sid,
        "label": label[:120],
        "source_type": "text",
        "chunks": len(rows),
        "embed": emb_method,
        "created_at": int(time.time()),
    }
    return _append_source(src, rows)


def add_url(url: str) -> dict[str, Any]:
    url = (url or "").strip()
    if not url.startswith("http"):
        raise ValueError("URL 需以 http(s) 開頭")
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "CATCH-CRM-MMRAG/1.0"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=25) as resp:
        raw = resp.read()
        ctype = (resp.headers.get("Content-Type") or "").lower()
    if "html" in ctype or raw[:200].lstrip().lower().startswith(b"<!doctype") or b"<html" in raw[:500].lower():
        try:
            text = raw.decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            text = raw.decode("latin-1", errors="replace")
        # crude HTML strip
        text = re.sub(r"(?is)<(script|style|nav|footer|header|aside)[^>]*>.*?</\1>", " ", text)
        text = re.sub(r"(?is)<[^>]+>", " ", text)
        text = html.unescape(text)
        text = re.sub(r"\s+", " ", text).strip()
    else:
        text = raw.decode("utf-8", errors="replace")
    if len(text) < 40:
        raise ValueError("網頁正文過短或抓取失敗")
    return add_text(text[:50000], label=url[:160])


def _save_media(data: bytes, mime: str, kind: str) -> tuple[str, str]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ext = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
        "audio/webm": ".webm",
        "audio/ogg": ".ogg",
        "audio/mpeg": ".mp3",
        "audio/mp4": ".m4a",
        "audio/wav": ".wav",
    }.get(mime, ".bin")
    name = f"{kind}_{uuid.uuid4().hex[:12]}{ext}"
    path = DATA_DIR / name
    path.write_bytes(data)
    return str(path), name


def add_media(
    data: bytes,
    mime_type: str,
    kind: str,
    label: str | None = None,
) -> dict[str, Any]:
    if kind not in ("image", "audio"):
        raise ValueError("僅支援 image / audio")
    if not data:
        raise ValueError("檔案為空")
    if len(data) > 12 * 1024 * 1024:
        raise ValueError("檔案過大（max 12MB）")
    mime = (mime_type or "").split(";")[0].strip().lower()
    if kind == "image" and mime not in (
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/gif",
    ):
        mime = "image/jpeg"
    if kind == "audio":
        if mime in ("audio/webm", "video/webm"):
            mime = "audio/webm"
        elif not mime.startswith("audio/"):
            mime = "audio/webm"

    desc = _describe_media(data, mime, kind)
    media_path, fname = _save_media(data, mime, kind)
    parts = _chunk(desc) or [desc]
    sid = uuid.uuid4().hex[:10]
    rows = []
    emb_method = ""
    for i, p in enumerate(parts):
        vec, method = embed_text(p)
        emb_method = method
        rows.append(
            {
                "id": f"{sid}_{i}",
                "source_id": sid,
                "source_type": kind,
                "source_label": (label or fname)[:120],
                "text": p,
                "embedding": vec,
                "media_path": media_path,
                "mime_type": mime,
            }
        )
    src = {
        "id": sid,
        "label": (label or fname)[:120],
        "source_type": kind,
        "chunks": len(rows),
        "embed": emb_method,
        "media_file": fname,
        "created_at": int(time.time()),
        "preview": desc[:200],
    }
    return _append_source(src, rows)


def _average_vectors(vectors: list[list[float]]) -> list[float]:
    """Element-wise mean; skip empty / mismatched dims."""
    cleaned = [v for v in vectors if v]
    if not cleaned:
        return []
    dim = len(cleaned[0])
    same = [v for v in cleaned if len(v) == dim]
    if not same:
        return cleaned[0]
    acc = [0.0] * dim
    for v in same:
        for i, x in enumerate(v):
            acc[i] += float(x)
    n = float(len(same))
    return [x / n for x in acc]


def _qwen_chat(system: str, user: str, max_tokens: int = 800, temperature: float = 0.5) -> str:
    payload = {
        "model": config.QWEN_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    req = urllib.request.Request(
        config.QWEN_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = json.loads(resp.read().decode("utf-8"))
    msg = (raw.get("choices") or [{}])[0].get("message") or {}
    text = (msg.get("content") or msg.get("reasoning_content") or "").strip()
    return re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.I).strip()


def generate_hypothetical_docs(question: str, n: int = HYDE_N_DEFAULT) -> tuple[list[str], str]:
    """
    HyDE step 1: LLM writes N hypothetical knowledge-base passages
    that *would* answer the question (not the real retrieval yet).
    Returns (docs, generator_tag).
    """
    n = max(1, min(int(n or HYDE_N_DEFAULT), 5))
    system = (
        "你是知識庫寫手。根據使用者問題，寫出可能出現在官方文件／FAQ／政策中的"
        "假想答案段落（繁體中文）。不要寫「假設」「我認為」「無法回答」。"
        "只輸出正文，不要標題編號以外的說明。"
    )
    user = (
        f"問題：{question}\n\n"
        f"請產出恰好 {n} 段互不重複的假想知識庫段落，每段 2–5 句。"
        f"段落之間只用一行分隔符 === 隔開。"
    )
    generator = "qwen"
    try:
        raw = _qwen_chat(system, user, max_tokens=900, temperature=0.55)
    except Exception:  # noqa: BLE001
        generator = "gemini"
        try:
            raw = _gemini_generate(
                [{"text": system + "\n\n" + user}],
                temperature=0.55,
            )
        except Exception as e:  # noqa: BLE001
            # last resort: use question itself as single "hypothesis"
            return [question], f"fallback-query ({e})"

    parts = [p.strip() for p in re.split(r"\n?\s*===\s*\n?", raw) if p.strip()]
    # also split numbered lists if model ignored ===
    if len(parts) < n and re.search(r"(?m)^\s*[1-9][\.\)]\s+", raw):
        parts = [
            re.sub(r"^\s*[1-9][\.\)]\s*", "", p).strip()
            for p in re.split(r"(?m)\s*(?=[1-9][\.\)]\s+)", raw)
            if p.strip() and not re.fullmatch(r"[1-9][\.\)]\s*", p.strip())
        ]
        parts = [p for p in parts if len(p) > 12]

    docs = parts[:n] if parts else [raw[:600] if raw else question]
    if len(docs) < n and raw and len(docs) == 1:
        # pad by re-using with slight variant marker (still useful for embed diversity less so)
        while len(docs) < n:
            docs.append(docs[0])
    return docs, generator


def hyde_query_vector(
    question: str,
    n: int = HYDE_N_DEFAULT,
) -> tuple[list[float], str, list[str], str]:
    """
    Build HyDE retrieval vector = mean(embed(hypothetical_doc_i)).
    Returns (vector, embed_method, hypo_docs, hypo_generator).
    """
    docs, gen = generate_hypothetical_docs(question, n=n)
    vectors: list[list[float]] = []
    methods: list[str] = []
    for d in docs:
        v, m = embed_text(d)
        if v:
            vectors.append(v)
            methods.append(m)
    if not vectors:
        v, m = embed_text(question)
        return v, m, docs, gen
    avg = _average_vectors(vectors)
    method = methods[0] if methods else "hyde"
    if any(x != methods[0] for x in methods[1:]):
        method = "hyde-mixed"
    else:
        method = f"hyde-avg({len(vectors)}×{method})"
    return avg, method, docs, gen


def query(
    question: str,
    top_k: int = TOP_K,
    hyde: bool = False,
    n_hyde: int = HYDE_N_DEFAULT,
) -> dict[str, Any]:
    q = (question or "").strip()
    if not q:
        raise ValueError("問題為空")
    chunks = _load_chunks()
    if not chunks:
        return {
            "ok": True,
            "answer": "知識庫尚無來源。請先加入文字、URL、圖片或音訊。",
            "question": q,
            "hits": [],
            "embed_method": "",
            "hyde": bool(hyde),
            "hypothetical_docs": [],
        }

    hypo_docs: list[str] = []
    hypo_gen = ""
    if hyde:
        qvec, emb_method, hypo_docs, hypo_gen = hyde_query_vector(q, n=n_hyde)
        # scoring text for BOW mismatch path: join hypos
        score_text = "\n".join(hypo_docs) if hypo_docs else q
    else:
        qvec, emb_method = embed_text(q)
        score_text = q

    scored: list[tuple[float, dict]] = []
    for c in chunks:
        vec = c.get("embedding") or []
        # if dim mismatch (gemini vs bow), re-embed text with bow for this pair
        if not vec or (qvec and len(vec) != len(qvec)):
            vec = _bow_vec(c.get("text") or "")
            score = _cosine(_bow_vec(score_text), vec)
        else:
            score = _cosine(qvec, vec)
        scored.append((score, c))
    scored.sort(key=lambda x: x[0], reverse=True)
    k = max(1, min(top_k, len(scored)))
    top = scored[:k]

    hits = []
    context_blocks = []
    media_parts: list[dict] = []
    seen_media: set[str] = set()

    for score, c in top:
        label = c.get("source_label") or c.get("source_id")
        hits.append(
            {
                "score": round(float(score), 4),
                "source_type": c.get("source_type"),
                "source_label": label,
                "snippet": (c.get("text") or "")[:280],
            }
        )
        context_blocks.append(
            f"[來源: {label} | 類型: {c.get('source_type')} | score={score:.3f}]\n{c.get('text') or ''}"
        )
        mp = c.get("media_path") or ""
        if mp and mp not in seen_media and Path(mp).is_file():
            seen_media.add(mp)
            try:
                raw = Path(mp).read_bytes()
                mime = c.get("mime_type") or "application/octet-stream"
                media_parts.append(
                    {
                        "inline_data": {
                            "mime_type": mime,
                            "data": base64.b64encode(raw).decode("ascii"),
                        }
                    }
                )
            except Exception:  # noqa: BLE001
                pass

    system = (
        "你是 CATCH CRM 多模態知識助理，使用繁體中文。"
        "只根據提供的檢索上下文（與附加媒體）回答，並在關鍵句後用括號標出來源標籤。"
        "若上下文不足，請明確說明。"
        "不要把「假想文件」當成真實來源；假想文件僅用於檢索，回答必須依據下方上下文。"
    )
    parts: list[dict] = [{"text": system + "\n\n上下文：\n\n" + "\n\n---\n\n".join(context_blocks)}]
    parts.extend(media_parts)
    parts.append({"text": f"\n問題：{q}\n\n請給出有根據的回答（含引用）："})

    try:
        answer = _gemini_generate(parts, temperature=0.25)
        model = _gen_model()
    except Exception as e:  # noqa: BLE001
        # fallback: text-only via Qwen if Gemini fails
        answer = _qwen_answer(q, "\n\n".join(context_blocks))
        model = f"qwen-fallback ({e})"

    return {
        "ok": True,
        "answer": answer,
        "question": q,
        "hits": hits,
        "embed_method": emb_method,
        "model": model,
        "media_attached": len(media_parts),
        "hyde": bool(hyde),
        "n_hyde": int(n_hyde) if hyde else 0,
        "hypothetical_docs": hypo_docs if hyde else [],
        "hyde_generator": hypo_gen if hyde else "",
    }


def _qwen_answer(question: str, context: str) -> str:
    payload = {
        "model": config.QWEN_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "依上下文用繁體中文回答，並標出來源。不足則說明。",
            },
            {
                "role": "user",
                "content": f"上下文：\n{context[:8000]}\n\n問題：{question}",
            },
        ],
        "temperature": 0.3,
        "max_tokens": 1200,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    req = urllib.request.Request(
        config.QWEN_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = json.loads(resp.read().decode("utf-8"))
    msg = (raw.get("choices") or [{}])[0].get("message") or {}
    text = (msg.get("content") or msg.get("reasoning_content") or "").strip()
    return re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.I).strip() or "（空）"
