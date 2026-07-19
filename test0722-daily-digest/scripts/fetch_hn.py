"""Hacker News via Algolia API (no key). Pattern from HN newsletter agent."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import requests

ALGOLIA_FRONT = "https://hn.algolia.com/api/v1/search"
ALGOLIA_LATEST = "https://hn.algolia.com/api/v1/search_by_date"


def _hit_to_item(hit: dict) -> dict[str, Any] | None:
    title = (hit.get("title") or hit.get("story_title") or "").strip()
    if not title:
        return None
    url = hit.get("url") or ""
    object_id = hit.get("objectID") or hit.get("story_id")
    hn_url = f"https://news.ycombinator.com/item?id={object_id}" if object_id else ""
    link = url or hn_url
    pts = hit.get("points")
    comments = hit.get("num_comments")
    author = hit.get("author") or ""
    created = hit.get("created_at")
    # short "summary" from available meta (no full scrape by default — safer)
    bits = []
    if pts is not None:
        bits.append(f"{pts} points")
    if comments is not None:
        bits.append(f"{comments} comments")
    if author:
        bits.append(f"by {author}")
    summary = " · ".join(bits)
    return {
        "source": "Hacker News",
        "title": title,
        "link": link,
        "hn_url": hn_url,
        "summary": summary,
        "points": pts,
        "num_comments": comments,
        "author": author,
        "published": created,
        "published_ts": None,
        "kind": "hn",
    }


def fetch_hn(
    mode: str = "front",
    limit: int = 10,
    timeout: float = 20.0,
) -> tuple[list[dict], dict]:
    """
    mode:
      front  — front_page (better signal)
      latest — newest stories (newsletter-agent style)
    """
    mode = (mode or "front").lower()
    headers = {"User-Agent": "cbot-daily-digest/1.0 (+local)"}
    try:
        if mode == "latest":
            r = requests.get(
                ALGOLIA_LATEST,
                params={"tags": "story", "hitsPerPage": limit},
                timeout=timeout,
                headers=headers,
            )
        else:
            r = requests.get(
                ALGOLIA_FRONT,
                params={"tags": "front_page", "hitsPerPage": limit},
                timeout=timeout,
                headers=headers,
            )
        r.raise_for_status()
        data = r.json()
    except Exception as e:  # noqa: BLE001
        return [], {
            "ok": False,
            "error": str(e),
            "mode": mode,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

    hits = data.get("hits") or []
    items: list[dict] = []
    for h in hits[:limit]:
        it = _hit_to_item(h)
        if it:
            items.append(it)

    stats = {
        "ok": True,
        "mode": mode,
        "count": len(items),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "nbHits": data.get("nbHits"),
    }
    return items, stats


if __name__ == "__main__":
    arts, st = fetch_hn("front", 10)
    print(json.dumps(st, ensure_ascii=False, indent=2))
    for a in arts[:3]:
        print("-", a["title"][:80], a.get("points"))
