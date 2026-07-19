"""Parallel RSS fetch + lookback filter."""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

import feedparser
import requests

ROOT = Path(__file__).resolve().parent.parent


def _parse_entry_time(entry: dict) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                pass
    for key in ("published", "updated"):
        raw = entry.get(key)
        if not raw:
            continue
        try:
            dt = parsedate_to_datetime(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except (TypeError, ValueError, IndexError, OverflowError):
            continue
    return None


def _fetch_one(source: dict, timeout: float) -> list[dict[str, Any]]:
    name = source.get("name") or "unknown"
    url = source.get("xmlUrl") or ""
    if not url:
        return []
    headers = {"User-Agent": "cbot-daily-digest/1.0 (+local)"}
    try:
        r = requests.get(url, timeout=timeout, headers=headers)
        r.raise_for_status()
        parsed = feedparser.parse(r.content)
    except Exception as e:  # noqa: BLE001
        return [{"_error": str(e), "source": name}]

    out: list[dict[str, Any]] = []
    for entry in parsed.entries or []:
        title = (entry.get("title") or "").strip()
        link = (entry.get("link") or "").strip()
        if not title or not link:
            continue
        summary = (entry.get("summary") or entry.get("description") or "").strip()
        # strip crude HTML
        if "<" in summary:
            import re

            summary = re.sub(r"<[^>]+>", " ", summary)
            summary = re.sub(r"\s+", " ", summary).strip()
        if len(summary) > 400:
            summary = summary[:400] + "…"
        ts = _parse_entry_time(entry)
        out.append(
            {
                "source": name,
                "title": title,
                "link": link,
                "summary": summary,
                "published": ts.isoformat() if ts else None,
                "published_ts": ts.timestamp() if ts else None,
            }
        )
    return out


def load_sources(path: Path | None = None) -> list[dict]:
    p = path or (ROOT / "sources.json")
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def fetch_articles(
    sources: list[dict] | None = None,
    hours: int = 24,
    workers: int = 16,
    timeout: float = 12.0,
) -> tuple[list[dict], dict]:
    sources = sources or load_sources()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    errors: list[dict] = []
    articles: list[dict] = []

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {
            ex.submit(_fetch_one, src, timeout): src.get("name") for src in sources
        }
        for fut in as_completed(futs):
            rows = fut.result()
            for row in rows:
                if "_error" in row:
                    errors.append(row)
                    continue
                ts = row.get("published_ts")
                if ts is None:
                    # keep undated but mark — optional drop
                    continue
                try:
                    ts_f = float(ts)
                    # reject nonsense timestamps
                    if ts_f < 946684800 or ts_f > time.time() + 86400 * 2:
                        continue
                    pub_dt = datetime.fromtimestamp(ts_f, tz=timezone.utc)
                except (OSError, OverflowError, ValueError, TypeError):
                    continue
                if pub_dt < cutoff:
                    continue
                articles.append(row)

    # de-dupe by link
    seen: set[str] = set()
    unique: list[dict] = []
    for a in sorted(
        articles, key=lambda x: x.get("published_ts") or 0, reverse=True
    ):
        link = a["link"]
        if link in seen:
            continue
        seen.add(link)
        unique.append(a)

    stats = {
        "sources": len(sources),
        "errors": len(errors),
        "articles_in_window": len(unique),
        "cutoff": cutoff.isoformat(),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "error_samples": errors[:8],
    }
    return unique, stats


if __name__ == "__main__":
    arts, st = fetch_articles(hours=48)
    print(json.dumps(st, ensure_ascii=False, indent=2))
    print("sample:", arts[0]["title"] if arts else "(none)")
