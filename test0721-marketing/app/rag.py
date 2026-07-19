"""Lightweight RAG over marketing/CRM docs using Ollama embeddings."""

from __future__ import annotations

import json
import math
import re
import time
import urllib.request
from typing import Any

import redis

from . import config
from .db import fetch_all, fetch_one

INDEX_KEY = "mkt:rag:index_v1"
META_KEY = "mkt:rag:meta_v1"


def _redis() -> redis.Redis:
    return redis.Redis(
        host=config.REDIS_HOST,
        port=config.REDIS_PORT,
        decode_responses=True,
        socket_connect_timeout=3,
    )


def _http_json(url: str, payload: dict, timeout: float = 120) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def list_ollama_models() -> list[dict]:
    req = urllib.request.Request(config.OLLAMA_TAGS_URL, method="GET")
    with urllib.request.urlopen(req, timeout=8) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data.get("models") or []


def embed_text(text: str) -> list[float]:
    text = (text or "").strip()
    if not text:
        return []
    # truncate very long chunks for embedding API
    text = text[:4000]
    out = _http_json(
        f"{config.OLLAMA_BASE}/api/embeddings",
        {"model": config.OLLAMA_EMBED_MODEL, "prompt": text},
        timeout=90,
    )
    emb = out.get("embedding") or []
    return [float(x) for x in emb]


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return -1.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0 or nb <= 0:
        return -1.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def _chunk(text: str, size: int = 420, overlap: int = 60) -> list[str]:
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        return []
    if len(text) <= size:
        return [text]
    out = []
    i = 0
    while i < len(text):
        out.append(text[i : i + size])
        i += max(size - overlap, 1)
    return out


def build_documents() -> list[dict[str, str]]:
    """Collect docs from Postgres + static marketing knowledge."""
    docs: list[dict[str, str]] = []

    plan = fetch_one(
        "SELECT year, theme, budget_ntd, status, body_md FROM marketing_plans "
        "ORDER BY year DESC NULLS LAST LIMIT 1"
    )
    if plan:
        body = plan.get("body_md") or ""
        docs.append(
            {
                "id": "plan-main",
                "source": "marketing_plans",
                "title": f"{plan.get('year')} {plan.get('theme')}",
                "text": f"年度行銷計畫：{plan.get('theme')}。預算 {plan.get('budget_ntd')} NTD。"
                f"狀態 {plan.get('status')}。{body}",
            }
        )

    for row in fetch_all(
        "SELECT code, name, short_name, family, description, inclusion_rules, "
        "exclusion_rules, suggested_ads, estimated_size "
        "FROM audience_packs WHERE COALESCE(active,true) LIMIT 20"
    ):
        docs.append(
            {
                "id": f"aud-{row.get('code')}",
                "source": "audience_packs",
                "title": row.get("short_name") or row.get("name") or "",
                "text": (
                    f"受眾包 {row.get('name')}（{row.get('code')}）。"
                    f"家族 {row.get('family')}。規模約 {row.get('estimated_size')}。"
                    f"{row.get('description') or ''} 納入：{row.get('inclusion_rules') or ''}。"
                    f"排除：{row.get('exclusion_rules') or ''}。"
                    f"建議投放：{row.get('suggested_ads') or ''}。"
                ),
            }
        )

    for row in fetch_all(
        "SELECT sku, name, category, spec_summary, allergens, shelf_life, "
        "pack_unit, moq, keywords FROM kb_products WHERE COALESCE(active,true) LIMIT 40"
    ):
        docs.append(
            {
                "id": f"sku-{row.get('sku')}",
                "source": "kb_products",
                "title": row.get("name") or row.get("sku") or "",
                "text": (
                    f"產品 {row.get('name')} SKU {row.get('sku')} 分類 {row.get('category')}。"
                    f"{row.get('spec_summary') or ''} 過敏原 {row.get('allergens') or '—'}。"
                    f"保存 {row.get('shelf_life') or '—'} 包裝 {row.get('pack_unit') or '—'} "
                    f"MOQ {row.get('moq') or '—'} 關鍵字 {row.get('keywords') or ''}。"
                ),
            }
        )

    for row in fetch_all(
        "SELECT name, category, threat_level, notes, website FROM competitors "
        "WHERE COALESCE(active,true) LIMIT 15"
    ):
        docs.append(
            {
                "id": f"comp-{row.get('name')}",
                "source": "competitors",
                "title": row.get("name") or "",
                "text": (
                    f"競品 {row.get('name')} 類別 {row.get('category')} "
                    f"威脅 {row.get('threat_level')}。{row.get('notes') or ''} "
                    f"網站 {row.get('website') or ''}。"
                ),
            }
        )

    ads = fetch_one(
        "SELECT COALESCE(SUM(spend_ntd),0)::bigint AS spend, "
        "COALESCE(SUM(clicks),0)::bigint AS clicks, "
        "COALESCE(SUM(conversions),0)::bigint AS conversions, "
        "COALESCE(SUM(revenue_attr_ntd),0)::bigint AS revenue "
        "FROM ad_daily"
    )
    if ads:
        spend = ads["spend"] or 1
        roas = round((ads["revenue"] or 0) / max(spend, 1), 2)
        docs.append(
            {
                "id": "ads-summary",
                "source": "ad_daily",
                "title": "廣告總覽指標",
                "text": (
                    f"廣告總花費 {ads['spend']} NTD，點擊 {ads['clicks']}，"
                    f"轉換 {ads['conversions']}，歸因營收 {ads['revenue']} NTD，"
                    f"ROAS 約 {roas}。"
                ),
            }
        )

    # static FAQ for demo
    faqs = [
        (
            "faq-roas",
            "什麼是 ROAS",
            "ROAS 是廣告花費回報率，等於歸因營收除以廣告花費。CATCH Growth 展示站用 ad_daily 彙總計算。",
        ),
        (
            "faq-crm",
            "如何預約演示",
            "在行銷網站底部填寫姓名與 Email，表單會寫入 catch_crm.form_submissions，狀態為 new。",
        ),
        (
            "faq-stack",
            "技術堆疊",
            "展示站使用 FastAPI BFF、PostgreSQL catch_crm、Redis 快取、"
            "Qwen OpenAI 相容端點，以及 Ollama embedding 做 RAG。",
        ),
        (
            "faq-pricing",
            "方案價格",
            "Starter 月費約 NT$9,800，Growth 約 NT$28,000，Enterprise 專案報價。此為展示假資料非正式報價。",
        ),
    ]
    for fid, title, text in faqs:
        docs.append({"id": fid, "source": "faq", "title": title, "text": text})

    return docs


def rebuild_index() -> dict[str, Any]:
    docs = build_documents()
    chunks: list[dict] = []
    for doc in docs:
        for i, part in enumerate(_chunk(doc["text"])):
            emb = embed_text(f"{doc['title']}\n{part}")
            if not emb:
                continue
            chunks.append(
                {
                    "id": f"{doc['id']}#{i}",
                    "doc_id": doc["id"],
                    "source": doc["source"],
                    "title": doc["title"],
                    "text": part,
                    "embedding": emb,
                }
            )
            time.sleep(0.02)

    meta = {
        "built_at": time.time(),
        "doc_count": len(docs),
        "chunk_count": len(chunks),
        "embed_model": config.OLLAMA_EMBED_MODEL,
        "dim": len(chunks[0]["embedding"]) if chunks else 0,
    }
    r = _redis()
    # store without huge duplicate: keep embeddings
    r.set(INDEX_KEY, json.dumps(chunks, ensure_ascii=False))
    r.set(META_KEY, json.dumps(meta, ensure_ascii=False))
    return meta


def load_index() -> tuple[list[dict], dict]:
    r = _redis()
    raw = r.get(INDEX_KEY)
    meta_raw = r.get(META_KEY)
    if not raw:
        meta = rebuild_index()
        raw = r.get(INDEX_KEY)
        meta_raw = r.get(META_KEY)
    chunks = json.loads(raw or "[]")
    meta = json.loads(meta_raw or "{}")
    return chunks, meta


def search(query: str, top_k: int = 5) -> list[dict]:
    chunks, _ = load_index()
    q = embed_text(query)
    if not q:
        return []
    scored = []
    for ch in chunks:
        emb = ch.get("embedding") or []
        score = cosine(q, emb)
        scored.append(
            {
                "id": ch.get("id"),
                "doc_id": ch.get("doc_id"),
                "source": ch.get("source"),
                "title": ch.get("title"),
                "text": ch.get("text"),
                "score": round(score, 4),
            }
        )
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[: max(1, min(top_k, 10))]


def answer_with_rag(question: str, top_k: int = 5) -> dict[str, Any]:
    hits = search(question, top_k=top_k)
    context = "\n\n".join(
        f"[{i+1}] ({h['source']}) {h['title']}\n{h['text']}" for i, h in enumerate(hits)
    )
    prompt = (
        "你是 CATCH Growth 行銷知識助理。只能根據下列檢索內容回答，使用繁體中文。"
        "若內容不足請明說不知道，不要編造數字。\n\n"
        f"【檢索內容】\n{context}\n\n"
        f"【問題】{question}\n\n"
        "【回答】請先給結論，再列引用編號。"
    )
    out = _http_json(
        f"{config.OLLAMA_BASE}/api/generate",
        {
            "model": config.OLLAMA_CHAT_MODEL,
            "prompt": prompt,
            "stream": False,
            "think": False,
            "options": {"num_predict": 512, "temperature": 0.2},
        },
        timeout=180,
    )
    answer = (out.get("response") or "").strip()
    return {
        "answer": answer,
        "hits": hits,
        "model": config.OLLAMA_CHAT_MODEL,
        "embed_model": config.OLLAMA_EMBED_MODEL,
    }
