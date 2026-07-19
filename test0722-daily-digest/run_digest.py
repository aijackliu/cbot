#!/usr/bin/env python3
"""
Daily tech digest from Karpathy-curated RSS list (92 feeds).

Pipeline:
  sources.json → parallel RSS → 24h filter → Qwen rank → Markdown

Usage:
  python run_digest.py
  python run_digest.py --hours 48 --top 5
  python run_digest.py --fetch-only
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import config  # noqa: E402
from rank_qwen import rank_articles  # noqa: E402
from scripts.fetch_rss import fetch_articles  # noqa: E402


def render_markdown(
    picks: list[dict],
    stats: dict,
    hours: int,
) -> str:
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines = [
        f"# 科技部落格每日摘要 · {day}",
        "",
        f"> 來源：Karpathy 精選 RSS 列表（{stats.get('sources')} 個 feed）· "
        f"過去 **{hours}h** · 由 LAN Qwen 排序與繁中摘要",
        "",
        f"- 視窗內文章數：{stats.get('articles_in_window')}",
        f"- 抓取失敗 feed：{stats.get('errors')}",
        f"- 截止：`{stats.get('cutoff')}`",
        f"- 生成：`{stats.get('fetched_at')}`",
        "",
        "---",
        "",
    ]
    emoji = {
        "Breaking": "🔴",
        "Important": "🟡",
        "Notable": "🔵",
    }
    if not picks:
        lines.append("_此時間窗沒有文章，或抓取/模型失敗。_")
        return "\n".join(lines) + "\n"

    for i, p in enumerate(picks, 1):
        cat = p.get("category") or "Notable"
        mark = emoji.get(cat, "⚪")
        score = p.get("score", "?")
        lines.append(f"## {i}. {mark} {p.get('title')}")
        lines.append("")
        lines.append(
            f"- **分類**：{cat} · **分數**：{score} · **來源**：{p.get('source')}"
        )
        if p.get("published"):
            lines.append(f"- **發布**：{p.get('published')}")
        lines.append(f"- **連結**：{p.get('link')}")
        lines.append("")
        lines.append(p.get("summary_zh") or "")
        if p.get("reason_zh"):
            lines.append("")
            lines.append(f"_{p.get('reason_zh')}_")
        lines.append("")
        lines.append("---")
        lines.append("")

    lines.append("")
    lines.append(
        "列表源自社群整理之 Karpathy 向 tech blogs（`sources.json`）；"
        "僅使用 RSS 標題/摘要，不整站鏡像。"
    )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Karpathy-list daily tech digest")
    ap.add_argument("--hours", type=int, default=config.LOOKBACK_HOURS)
    ap.add_argument("--top", type=int, default=config.TOP_N)
    ap.add_argument("--workers", type=int, default=config.FETCH_WORKERS)
    ap.add_argument("--fetch-only", action="store_true", help="skip LLM ranking")
    ap.add_argument(
        "--out",
        type=Path,
        default=None,
        help="output markdown path (default output/digest-YYYY-MM-DD.md)",
    )
    args = ap.parse_args()

    print(f"[1/3] Fetching RSS (last {args.hours}h, workers={args.workers})…")
    articles, stats = fetch_articles(
        hours=args.hours,
        workers=args.workers,
        timeout=config.FETCH_TIMEOUT,
    )
    print(
        f"    → {stats['articles_in_window']} articles, "
        f"{stats['errors']} feed errors"
    )

    out_dir = ROOT / "output"
    out_dir.mkdir(exist_ok=True)
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    candidates_path = out_dir / f"candidates-{day}.json"
    with open(candidates_path, "w", encoding="utf-8") as f:
        json.dump(
            {"stats": stats, "articles": articles},
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"    → wrote {candidates_path.name}")

    if args.fetch_only:
        print("[skip] LLM ranking (--fetch-only)")
        return 0

    if not articles:
        picks = []
        print("[2/3] No articles — skip Qwen")
    else:
        print(
            f"[2/3] Ranking top {args.top} via Qwen "
            f"({config.QWEN_URL})…"
        )
        picks = rank_articles(articles, top_n=args.top)
        print(f"    → {len(picks)} picks")

    md = render_markdown(picks, stats, args.hours)
    out_path = args.out or (out_dir / f"digest-{day}.md")
    out_path.write_text(md, encoding="utf-8")
    print(f"[3/3] Wrote {out_path}")
    print("--- preview ---")
    print(md[:1200])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
