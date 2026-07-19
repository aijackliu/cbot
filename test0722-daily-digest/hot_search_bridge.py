"""
Bridge to F:\\grok\\2\\hot-search (multi-platform 熱搜 + LLM 繁中).

Default: read latest.json after optional refresh via fetch_hot_search.py.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

# Default path used by grok/2 start.ps1
DEFAULT_HOT_ROOT = Path(
    os.getenv("HOT_SEARCH_ROOT", r"F:\grok\2\hot-search")
)


def hot_root() -> Path:
    return Path(os.getenv("HOT_SEARCH_ROOT", str(DEFAULT_HOT_ROOT)))


def latest_json_path(root: Path | None = None) -> Path:
    return (root or hot_root()) / "data" / "latest.json"


def refresh_hot_search(
    root: Path | None = None,
    platforms: list[str] | None = None,
    limit: int = 30,
) -> int:
    """Run grok/2 hot-search fetcher (includes LLM 繁中 when available)."""
    root = root or hot_root()
    script = root / "fetch_hot_search.py"
    if not script.is_file():
        raise FileNotFoundError(f"找不到熱搜腳本: {script}")
    cmd = [sys.executable, str(script), "--limit", str(limit)]
    if platforms:
        cmd.extend(["--platforms", *platforms])
    print(f"==> 更新熱搜: {script}")
    proc = subprocess.run(cmd, cwd=str(root))
    return int(proc.returncode)


def load_hot_payload(root: Path | None = None) -> dict[str, Any] | None:
    path = latest_json_path(root)
    if not path.is_file():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def tech_hot_as_articles(payload: dict[str, Any], max_items: int = 25) -> list[dict]:
    """
    Flatten platform tops into article-shaped rows for optional co-ranking
    with blog digests (prefer finance/tech-ish platforms + themes).
    """
    out: list[dict] = []
    summary = payload.get("summary") or {}
    # theme bullets first (already clustered)
    for theme in summary.get("themes") or []:
        title_t = theme.get("title") or theme.get("key") or "主題"
        for b in (theme.get("bullets") or [])[:5]:
            out.append(
                {
                    "source": f"熱搜·{title_t}",
                    "title": str(b),
                    "link": "",
                    "summary": f"主題：{title_t}（多平台聚類）",
                    "published": payload.get("generated_at"),
                    "published_ts": None,
                    "kind": "hot_theme",
                }
            )
    # platform tops
    prefer = {"baidu", "toutiao", "douyin", "bilibili", "qq", "thepaper", "weibo", "zhihu"}
    for plat in payload.get("platforms") or []:
        key = plat.get("platform") or ""
        label = plat.get("label") or key
        if plat.get("error"):
            continue
        items = plat.get("items") or []
        cap = 8 if key in prefer else 4
        for it in items[:cap]:
            title = (it.get("title") or "").strip()
            if not title:
                continue
            out.append(
                {
                    "source": f"熱搜·{label}",
                    "title": title,
                    "link": it.get("url") or "",
                    "summary": it.get("heat") or f"{label} 熱搜第 {it.get('rank')}",
                    "published": payload.get("generated_at"),
                    "published_ts": None,
                    "kind": "hot_item",
                    "rank": it.get("rank"),
                }
            )
    # de-dupe by title
    seen: set[str] = set()
    unique: list[dict] = []
    for a in out:
        t = a["title"]
        if t in seen:
            continue
        seen.add(t)
        unique.append(a)
        if len(unique) >= max_items:
            break
    return unique


def render_hot_section(payload: dict[str, Any] | None, top_per_platform: int = 8) -> str:
    if not payload:
        return (
            "## 多平台熱搜\n\n"
            "_尚無熱搜資料。請先執行 "
            "`python hot_search_bridge.py --refresh` 或 "
            r"`F:\grok\2\hot-search\fetch_hot_search.py`。_"
            "\n\n---\n"
        )

    summary = payload.get("summary") or {}
    lines: list[str] = [
        "## 多平台熱搜",
        "",
        f"> 日期：`{payload.get('date')}` · 生成：`{payload.get('generated_at')}`  "
        f"· 來源：`F:\\grok\\2\\hot-search`（含 LLM 繁中）",
        "",
    ]
    if summary.get("headline"):
        lines.append(f"**總覽**：{summary['headline']}")
        lines.append("")
    if summary.get("blurb"):
        lines.append(summary["blurb"])
        lines.append("")

    themes = summary.get("themes") or []
    if themes:
        lines.append("### 主題聚類")
        lines.append("")
        for th in themes:
            badge = th.get("badge") or ""
            title = th.get("title") or th.get("key")
            lines.append(f"#### {title}" + (f" · {badge}" if badge else ""))
            for b in (th.get("bullets") or [])[:6]:
                lines.append(f"- {b}")
            lines.append("")

    research = summary.get("research") or []
    if research:
        lines.append("### 研究備註")
        lines.append("")
        for r in research:
            lab = r.get("label") or ""
            text = r.get("text") or ""
            lines.append(f"- **{lab}**：{text}")
        lines.append("")

    lines.append("### 各平台 Top")
    lines.append("")
    for plat in payload.get("platforms") or []:
        label = plat.get("label") or plat.get("platform")
        lines.append(f"#### {label}")
        if plat.get("error"):
            lines.append(f"_抓取失敗：{plat['error']}_")
            lines.append("")
            continue
        for it in (plat.get("items") or [])[:top_per_platform]:
            rank = it.get("rank") or ""
            title = it.get("title") or ""
            url = it.get("url") or ""
            if url:
                lines.append(f"{rank}. [{title}]({url})")
            else:
                lines.append(f"{rank}. {title}")
        lines.append("")

    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(description="熱搜 bridge（grok/2）")
    p.add_argument("--refresh", action="store_true", help="先執行 fetch_hot_search.py")
    p.add_argument("--root", type=Path, default=None)
    p.add_argument("--limit", type=int, default=30)
    args = p.parse_args(argv)
    root = args.root or hot_root()
    if args.refresh:
        code = refresh_hot_search(root, limit=args.limit)
        if code != 0:
            return code
    payload = load_hot_payload(root)
    if not payload:
        print(f"無 latest.json：{latest_json_path(root)}", file=sys.stderr)
        return 1
    print(f"date={payload.get('date')} platforms={len(payload.get('platforms') or [])}")
    print((payload.get("summary") or {}).get("headline", ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
