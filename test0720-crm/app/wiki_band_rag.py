"""
Wiki 樂團 RAG — Hands-On rock_music_rag 精簡版.

Wikipedia 頁 → 切塊 → BM25 檢索 → Qwen／Gemini 有根據回答 + 來源 URL.
無 Streamlit / Gemma 強制；無 rank-bm25 依賴（內建輕量 BM25）。

https://github.com/Sumanth077/Hands-On-AI-Engineering/tree/main/rag_apps/rock_music_rag
"""

from __future__ import annotations

import json
import math
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

import redis

from . import config

INDEX_KEY = "crm:wikiband:chunks_v1"
BANDS_KEY = "crm:wikiband:bands_v1"

DEFAULT_BANDS = [
    "Nirvana",
    "Audioslave",
    "Dire Straits",
    "Green Day",
    "The Smiths",
    "Evanescence",
    "Sum 41",
    "Radiohead",
    "Queen",
    "The Beatles",
]

# BM25 params
_K1 = 1.5
_B = 0.75


def _redis() -> redis.Redis:
    return redis.Redis(
        host=config.REDIS_HOST,
        port=config.REDIS_PORT,
        decode_responses=True,
        socket_connect_timeout=3,
    )


def _load_json(key: str, default: Any) -> Any:
    try:
        raw = _redis().get(key)
        if not raw:
            return default
        return json.loads(raw)
    except Exception:  # noqa: BLE001
        return default


def _save_json(key: str, val: Any) -> None:
    _redis().set(key, json.dumps(val, ensure_ascii=False))


def _tokenize(text: str) -> list[str]:
    text = (text or "").lower()
    # latin words + CJK runs as char unigrams/bigrams
    toks: list[str] = []
    for m in re.finditer(r"[a-z0-9']+|[\u4e00-\u9fff]+", text):
        t = m.group(0)
        if re.search(r"[\u4e00-\u9fff]", t):
            for ch in t:
                toks.append(ch)
            for i in range(len(t) - 1):
                toks.append(t[i : i + 2])
        else:
            toks.append(t)
    return toks


def _split_chunks(text: str, band: str, url: str) -> list[dict[str, Any]]:
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        return []
    # ~2 sentences per chunk (rock_music_rag style)
    sents = re.split(r"(?<=[.!?。！？])\s+", text)
    sents = [s.strip() for s in sents if s.strip()]
    chunks: list[dict[str, Any]] = []
    i = 0
    cid = 0
    while i < len(sents):
        piece = " ".join(sents[i : i + 2]).strip()
        i += 2
        if len(piece) < 40:
            continue
        chunks.append(
            {
                "id": f"{band[:20]}_{cid}",
                "band": band,
                "url": url,
                "text": piece[:1200],
            }
        )
        cid += 1
    if not chunks and text:
        for j in range(0, min(len(text), 8000), 500):
            chunks.append(
                {
                    "id": f"{band[:20]}_{j}",
                    "band": band,
                    "url": url,
                    "text": text[j : j + 550],
                }
            )
    return chunks


def fetch_wikipedia(title: str, lang: str = "en") -> dict[str, Any]:
    """Fetch plain extract via MediaWiki API."""
    title = (title or "").strip()
    if not title:
        raise ValueError("團名為空")
    lang = (lang or "en").strip().lower()
    if lang not in ("en", "zh", "zh-tw", "ja"):
        lang = "en"
    if lang == "zh-tw":
        lang = "zh"
    api = f"https://{lang}.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "prop": "extracts|info",
        "explaintext": "1",
        "exsectionformat": "plain",
        "inprop": "url",
        "redirects": "1",
        "titles": title,
        "format": "json",
    }
    url = api + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "CATCH-CRM-WikiBand/1.0 (demo)"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Wikipedia HTTP {e.code}") from e

    pages = ((data.get("query") or {}).get("pages") or {})
    if not pages:
        raise ValueError(f"找不到頁面：{title}")
    page = next(iter(pages.values()))
    if page.get("missing") is not None or page.get("invalid") is not None:
        raise ValueError(f"Wikipedia 無此條目：{title}")
    extract = (page.get("extract") or "").strip()
    if len(extract) < 80:
        raise ValueError(f"條目過短或被重定向失敗：{title}")
    page_url = page.get("fullurl") or (
        f"https://{lang}.wikipedia.org/wiki/" + urllib.parse.quote(page.get("title") or title)
    )
    return {
        "title": page.get("title") or title,
        "url": page_url,
        "extract": extract[:50000],
        "lang": lang,
    }


def _bm25_scores(query: str, corpus_tokens: list[list[str]]) -> list[float]:
    """Classic BM25 over in-memory token lists."""
    if not corpus_tokens:
        return []
    q_toks = _tokenize(query)
    if not q_toks:
        return [0.0] * len(corpus_tokens)
    N = len(corpus_tokens)
    avgdl = sum(len(d) for d in corpus_tokens) / max(1, N)
    # df
    df: dict[str, int] = {}
    for doc in corpus_tokens:
        for t in set(doc):
            df[t] = df.get(t, 0) + 1
    scores = []
    for doc in corpus_tokens:
        tf: dict[str, int] = {}
        for t in doc:
            tf[t] = tf.get(t, 0) + 1
        dl = len(doc) or 1
        s = 0.0
        for t in q_toks:
            if t not in tf:
                continue
            n_q = df.get(t, 0)
            idf = math.log(1 + (N - n_q + 0.5) / (n_q + 0.5))
            freq = tf[t]
            denom = freq + _K1 * (1 - _B + _B * dl / avgdl)
            s += idf * (freq * (_K1 + 1)) / denom
        scores.append(s)
    return scores


def list_bands() -> list[dict[str, Any]]:
    bands = _load_json(BANDS_KEY, [])
    if not isinstance(bands, list):
        return []
    return list(reversed(bands))


def stats() -> dict[str, Any]:
    chunks = _load_json(INDEX_KEY, [])
    bands = list_bands()
    return {
        "ok": True,
        "bands": len(bands),
        "chunks": len(chunks) if isinstance(chunks, list) else 0,
        "items": bands[:40],
        "defaults": DEFAULT_BANDS,
        "redis": f"{config.REDIS_HOST}:{config.REDIS_PORT}",
    }


def clear() -> dict[str, Any]:
    r = _redis()
    r.delete(INDEX_KEY)
    r.delete(BANDS_KEY)
    return {"ok": True, "cleared": True}


def add_band(name: str, lang: str = "en") -> dict[str, Any]:
    page = fetch_wikipedia(name, lang=lang)
    title = page["title"]
    chunks_new = _split_chunks(page["extract"], title, page["url"])
    if not chunks_new:
        raise ValueError("無法切塊")

    all_chunks: list[dict] = _load_json(INDEX_KEY, [])
    if not isinstance(all_chunks, list):
        all_chunks = []
    # remove old chunks for same band title (case-insensitive)
    all_chunks = [
        c
        for c in all_chunks
        if (c.get("band") or "").lower() != title.lower()
    ]
    all_chunks.extend(chunks_new)
    if len(all_chunks) > 2000:
        all_chunks = all_chunks[-2000:]
    _save_json(INDEX_KEY, all_chunks)

    bands: list[dict] = _load_json(BANDS_KEY, [])
    if not isinstance(bands, list):
        bands = []
    bands = [b for b in bands if (b.get("title") or "").lower() != title.lower()]
    rec = {
        "title": title,
        "url": page["url"],
        "lang": page["lang"],
        "chunks": len(chunks_new),
        "chars": len(page["extract"]),
        "added_at": int(time.time()),
        "query_name": name,
    }
    bands.append(rec)
    _save_json(BANDS_KEY, bands)
    return {"ok": True, "band": rec, "chunks_added": len(chunks_new), "index_size": len(all_chunks)}


def load_defaults(lang: str = "en") -> dict[str, Any]:
    results = []
    errors = []
    for name in DEFAULT_BANDS:
        try:
            results.append(add_band(name, lang=lang))
        except Exception as e:  # noqa: BLE001
            errors.append({"band": name, "error": str(e)})
    return {
        "ok": True,
        "loaded": len(results),
        "errors": errors,
        "stats": stats(),
    }


def remove_band(title: str) -> dict[str, Any]:
    title = (title or "").strip()
    if not title:
        raise ValueError("title required")
    chunks: list[dict] = _load_json(INDEX_KEY, [])
    if not isinstance(chunks, list):
        chunks = []
    before = len(chunks)
    chunks = [c for c in chunks if (c.get("band") or "").lower() != title.lower()]
    _save_json(INDEX_KEY, chunks)
    bands: list[dict] = _load_json(BANDS_KEY, [])
    if not isinstance(bands, list):
        bands = []
    bands = [b for b in bands if (b.get("title") or "").lower() != title.lower()]
    _save_json(BANDS_KEY, bands)
    return {"ok": True, "removed": title, "chunks_removed": before - len(chunks)}


def retrieve(question: str, top_k: int = 5) -> list[dict[str, Any]]:
    chunks: list[dict] = _load_json(INDEX_KEY, [])
    if not isinstance(chunks, list) or not chunks:
        return []
    corpus = [_tokenize(c.get("text") or "") for c in chunks]
    scores = _bm25_scores(question, corpus)
    ranked = sorted(zip(scores, chunks), key=lambda x: x[0], reverse=True)
    out = []
    for sc, c in ranked[: max(1, min(top_k, len(ranked)))]:
        if sc <= 0 and len(out) >= 1:
            break
        out.append(
            {
                "score": round(float(sc), 4),
                "band": c.get("band"),
                "url": c.get("url"),
                "snippet": (c.get("text") or "")[:400],
            }
        )
    # if all zero, still return top by raw
    if not out:
        for sc, c in ranked[:top_k]:
            out.append(
                {
                    "score": round(float(sc), 4),
                    "band": c.get("band"),
                    "url": c.get("url"),
                    "snippet": (c.get("text") or "")[:400],
                }
            )
    return out


def _qwen_answer(question: str, context: str) -> str:
    payload = {
        "model": config.QWEN_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是搖滾音樂知識助理，使用繁體中文。"
                    "只根據提供的 Wikipedia 摘錄回答，並在句末用括號標出 cop團名或來源 URL）。"
                    "若摘錄不足，明說不知道，不要編造。"
                ),
            },
            {
                "role": "user",
                "content": f"摘錄：\n{context[:9000]}\n\n問題：{question}",
            },
        ],
        "temperature": 0.3,
        "max_tokens": 900,
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


def ask(question: str, top_k: int = 5) -> dict[str, Any]:
    q = (question or "").strip()
    if not q:
        raise ValueError("問題為空")
    hits = retrieve(q, top_k=top_k)
    if not hits:
        return {
            "ok": True,
            "answer": "知識庫尚無樂團。請先「載入預設」或新增 Wikipedia 團名。",
            "hits": [],
            "question": q,
            "model": "",
        }
    ctx = "\n\n---\n\n".join(
        f"[樂團: {h.get('band')}] ({h.get('url')})\n{h.get('snippet')}" for h in hits
    )
    try:
        answer = _qwen_answer(q, ctx)
        model = config.QWEN_MODEL
    except Exception as e:  # noqa: BLE001
        # Gemini fallback
        try:
            from . import mm_rag

            answer = mm_rag._gemini_generate(
                [
                    {
                        "text": (
                            "你是搖滾音樂助理，繁體中文。只依摘錄回答並引用來源 URL。\n\n"
                            f"{ctx}\n\n問題：{q}"
                        )
                    }
                ],
                temperature=0.3,
            )
            model = f"gemini-fallback"
        except Exception as e2:  # noqa: BLE001
            answer = f"生成失敗：{e} / {e2}"
            model = "error"

    sources = []
    seen = set()
    for h in hits:
        u = h.get("url") or ""
        if u and u not in seen:
            seen.add(u)
            sources.append({"band": h.get("band"), "url": u})

    return {
        "ok": True,
        "answer": answer,
        "question": q,
        "hits": hits,
        "sources": sources,
        "model": model,
        "retrieval": "bm25",
    }
