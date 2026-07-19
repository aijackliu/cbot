"""
Lightweight brand monitor (no Scrapingdog / Orq).

Sources:
  - Hacker News Algolia search
  - Google News RSS (public)
  - Local hot-search latest.json keyword match (F:\\grok\\2\\hot-search)

Analysis: single LAN Qwen call → Traditional Chinese structured brief.
Pattern simplified from Hands-On brand_monitor_agent.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from . import config

HOT_LATEST = Path(
    os.getenv("HOT_SEARCH_ROOT", r"F:\grok\2\hot-search")
) / "data" / "latest.json"


def _http_json(url: str, timeout: float = 15.0) -> Any:
    req = urllib.request.Request(
        url, headers={"User-Agent": "cbot-brand-monitor/1.0"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _http_bytes(url: str, timeout: float = 15.0) -> bytes:
    req = urllib.request.Request(
        url, headers={"User-Agent": "cbot-brand-monitor/1.0"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def collect_hn(brand: str, limit: int = 8) -> dict[str, Any]:
    q = urllib.parse.quote(brand)
    url = (
        "https://hn.algolia.com/api/v1/search"
        f"?query={q}&tags=story&hitsPerPage={limit}"
    )
    try:
        data = _http_json(url)
        hits = data.get("hits") or []
        items = []
        for h in hits[:limit]:
            title = (h.get("title") or "").strip()
            if not title:
                continue
            oid = h.get("objectID")
            items.append(
                {
                    "title": title,
                    "url": h.get("url")
                    or (f"https://news.ycombinator.com/item?id={oid}" if oid else ""),
                    "points": h.get("points"),
                    "comments": h.get("num_comments"),
                    "author": h.get("author"),
                }
            )
        return {"ok": True, "platform": "hn", "label": "Hacker News", "items": items}
    except Exception as e:  # noqa: BLE001
        return {
            "ok": False,
            "platform": "hn",
            "label": "Hacker News",
            "items": [],
            "error": str(e),
        }


def collect_google_news(brand: str, limit: int = 8) -> dict[str, Any]:
    q = urllib.parse.quote(brand)
    # Public RSS — no API key
    url = (
        "https://news.google.com/rss/search?"
        f"q={q}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    )
    try:
        raw = _http_bytes(url)
        root = ET.fromstring(raw)
        items = []
        for item in root.findall(".//item")[:limit]:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub = (item.findtext("pubDate") or "").strip()
            source_el = item.find("source")
            source = (source_el.text if source_el is not None else "") or ""
            if title:
                items.append(
                    {
                        "title": title,
                        "url": link,
                        "published": pub,
                        "source": source,
                    }
                )
        return {
            "ok": True,
            "platform": "news",
            "label": "Google News",
            "items": items,
        }
    except Exception as e:  # noqa: BLE001
        return {
            "ok": False,
            "platform": "news",
            "label": "Google News",
            "items": [],
            "error": str(e),
        }


def collect_hot_search(brand: str, limit: int = 12) -> dict[str, Any]:
    brand_l = brand.lower()
    path = HOT_LATEST
    if not path.is_file():
        return {
            "ok": False,
            "platform": "hot",
            "label": "多平台熱搜",
            "items": [],
            "error": f"找不到 {path}（可先跑 grok/2 熱搜）",
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        return {
            "ok": False,
            "platform": "hot",
            "label": "多平台熱搜",
            "items": [],
            "error": str(e),
        }

    items = []
    for plat in payload.get("platforms") or []:
        label = plat.get("label") or plat.get("platform")
        for it in plat.get("items") or []:
            title = (it.get("title") or "").strip()
            if not title:
                continue
            if brand_l not in title.lower() and brand not in title:
                # also loose: all chars of brand present for CJK short names
                if len(brand) >= 2 and brand[:2] not in title:
                    continue
            items.append(
                {
                    "title": title,
                    "url": it.get("url") or "",
                    "platform": label,
                    "rank": it.get("rank"),
                }
            )
            if len(items) >= limit:
                break
        if len(items) >= limit:
            break

    # theme bullets
    for th in (payload.get("summary") or {}).get("themes") or []:
        for b in th.get("bullets") or []:
            if brand in str(b) or brand_l in str(b).lower():
                items.append(
                    {
                        "title": str(b),
                        "url": "",
                        "platform": f"主題·{th.get('title')}",
                    }
                )

    return {
        "ok": True,
        "platform": "hot",
        "label": "多平台熱搜",
        "items": items[:limit],
        "hot_date": payload.get("date"),
    }


def _extract_text(message: dict) -> str:
    content = (message.get("content") or "").strip()
    reason = (message.get("reasoning_content") or "").strip()
    for blob in (content, reason):
        if blob:
            return blob
    return ""


def _chat_qwen(system: str, user: str, max_tokens: int = 1200) -> str:
    payload = {
        "model": config.QWEN_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.25,
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


def analyze(brand: str, channels: list[dict]) -> dict[str, Any]:
    catalog = []
    for ch in channels:
        catalog.append(
            {
                "platform": ch.get("label"),
                "ok": ch.get("ok"),
                "error": ch.get("error"),
                "items": (ch.get("items") or [])[:10],
            }
        )
    system = (
        "你是品牌情報分析師。根據各通道公開檢索結果，用繁體中文輸出 JSON：\n"
        "{\n"
        '  "headline_zh": "一句總覽",\n'
        '  "sentiment": "positive|neutral|mixed|negative|unknown",\n'
        '  "sentiment_zh": "情緒說明",\n'
        '  "key_points_zh": ["要點1","要點2"],\n'
        '  "risks_zh": ["風險1"],\n'
        '  "opportunities_zh": ["機會1"],\n'
        '  "channels": [{"platform":"…","summary_zh":"…","sentiment":"…"}]\n'
        "}\n"
        "禁止編造未出現的新聞；資料不足就寫「公開訊號有限」。不要思考過程。"
    )
    user = f"品牌：{brand}\n資料：\n{json.dumps(catalog, ensure_ascii=False)[:10000]}"
    raw = _chat_qwen(system, user)
    try:
        return _parse_json(raw)
    except (json.JSONDecodeError, ValueError):
        return {
            "headline_zh": f"{brand} 公開訊號摘要（解析降級）",
            "sentiment": "unknown",
            "sentiment_zh": raw[:400] if raw else "模型未回傳結構化結果",
            "key_points_zh": [],
            "risks_zh": [],
            "opportunities_zh": [],
            "channels": [],
            "raw_preview": (raw or "")[:500],
        }


def run_monitor(brand: str) -> dict[str, Any]:
    brand = (brand or "").strip()
    if len(brand) < 1:
        raise ValueError("brand required")

    channels = [
        collect_hot_search(brand),
        collect_hn(brand),
        collect_google_news(brand),
    ]
    brief = analyze(brand, channels)
    return {
        "brand": brand,
        "channels": channels,
        "brief": brief,
        "sources_note": (
            "輕量級：熱搜本地檔 + HN Algolia + Google News RSS + Qwen；"
            "非 Scrapingdog 全量社媒 API。"
        ),
    }
