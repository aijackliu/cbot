#!/usr/bin/env python3
"""
Daily digest: Karpathy RSS 熱門文章 + 多平台熱搜（F:\\grok\\2\\hot-search）.

Pipeline:
  [可選] 更新熱搜（含 LLM 繁中）
  → 92 RSS → 24h 過濾 → Qwen 排序
  → 合併熱搜章節 → Markdown

Usage:
  python run_digest.py
  python run_digest.py --refresh-hot
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
from hot_search_bridge import (  # noqa: E402
    load_hot_payload,
    refresh_hot_search,
    render_hot_section,
    tech_hot_as_articles,
)
from rank_qwen import rank_articles  # noqa: E402
from scripts.fetch_rss import fetch_articles  # noqa: E402


def render_blog_section(picks: list[dict], stats: dict, hours: int) -> str:
    lines = [
        "## 科技部落格熱門（Karpathy 列表）",
        "",
        f"> 來源：`sources.json`（{stats.get('sources')} 個 RSS）· "
        f"過去 **{hours}h** · LAN Qwen 排序與繁中摘要",
        "",
        f"- 視窗內文章數：{stats.get('articles_in_window')}",
        f"- 抓取失敗 feed：{stats.get('errors')}",
        f"- 截止：`{stats.get('cutoff')}`",
        f"- 生成：`{stats.get('fetched_at')}`",
        "",
    ]
    emoji = {
        "Breaking": "🔴",
        "Important": "🟡",
        "Notable": "🔵",
    }
    if not picks:
        lines.append("_此時間窗沒有文章，或抓取/模型失敗。_")
        lines.append("")
        lines.append("---")
        lines.append("")
        return "\n".join(lines)

    for i, p in enumerate(picks, 1):
        cat = p.get("category") or "Notable"
        mark = emoji.get(cat, "⚪")
        score = p.get("score", "?")
        kind = p.get("kind") or "blog"
        lines.append(f"### {i}. {mark} {p.get('title')}")
        lines.append("")
        lines.append(
            f"- **分類**：{cat} · **分數**：{score} · **來源**：{p.get('source')} · **類型**：{kind}"
        )
        if p.get("published"):
            lines.append(f"- **發布**：{p.get('published')}")
        if p.get("link"):
            lines.append(f"- **連結**：{p.get('link')}")
        lines.append("")
        lines.append(p.get("summary_zh") or "")
        if p.get("reason_zh"):
            lines.append("")
            lines.append(f"_{p.get('reason_zh')}_")
        lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines)


def render_markdown(
    picks: list[dict],
    stats: dict,
    hours: int,
    hot_payload: dict | None,
) -> str:
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines = [
        f"# 每日熱點摘要 · {day}",
        "",
        "> **熱搜**（多平台）＋ **科技部落格**（Karpathy 精選 RSS）· 繁中",
        "",
        "---",
        "",
        render_hot_section(hot_payload),
        render_blog_section(picks, stats, hours),
        "",
        "部落格列表僅用 RSS 標題/摘要；熱搜來自公開榜單接口。"
        "不構成投資建議。",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Daily digest: hot-search + Karpathy RSS"
    )
    ap.add_argument("--hours", type=int, default=config.LOOKBACK_HOURS)
    ap.add_argument("--top", type=int, default=config.TOP_N)
    ap.add_argument("--workers", type=int, default=config.FETCH_WORKERS)
    ap.add_argument("--fetch-only", action="store_true", help="skip LLM ranking")
    ap.add_argument(
        "--refresh-hot",
        action="store_true",
        help=r"先跑 F:\grok\2\hot-search\fetch_hot_search.py（含 LLM 繁中）",
    )
    ap.add_argument(
        "--no-hot",
        action="store_true",
        help="不併入熱搜章節",
    )
    ap.add_argument(
        "--mix-hot-rank",
        action="store_true",
        help="把熱搜條目一併送進 Qwen 與部落格混排 Top N",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=None,
        help="output markdown path (default output/digest-YYYY-MM-DD.md)",
    )
    args = ap.parse_args()

    hot_payload = None
    if not args.no_hot:
        if args.refresh_hot:
            try:
                code = refresh_hot_search(limit=30)
                if code != 0:
                    print(f"[warn] 熱搜更新 exit={code}，改讀既有 latest.json")
            except FileNotFoundError as e:
                print(f"[warn] {e}")
        hot_payload = load_hot_payload()
        if hot_payload:
            print(
                f"[0/3] 熱搜已載入 date={hot_payload.get('date')} "
                f"headline={(hot_payload.get('summary') or {}).get('headline', '')[:40]}"
            )
        else:
            print("[0/3] 尚無熱搜 latest.json（可用 --refresh-hot）")

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

    # optional: mix hot items into ranking pool
    pool = list(articles)
    if args.mix_hot_rank and hot_payload:
        hot_arts = tech_hot_as_articles(hot_payload, max_items=20)
        # mark blogs
        for a in pool:
            a.setdefault("kind", "blog")
        pool = hot_arts + pool
        print(f"    → mixed +{len(hot_arts)} hot items into rank pool")

    out_dir = ROOT / "output"
    out_dir.mkdir(exist_ok=True)
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    candidates_path = out_dir / f"candidates-{day}.json"
    with open(candidates_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "stats": stats,
                "articles": articles,
                "hot_date": (hot_payload or {}).get("date"),
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"    → wrote {candidates_path.name}")

    if args.fetch_only:
        print("[skip] LLM ranking (--fetch-only)")
        md = render_markdown([], stats, args.hours, hot_payload)
        out_path = args.out or (out_dir / f"digest-{day}.md")
        out_path.write_text(md, encoding="utf-8")
        print(f"Wrote {out_path} (hot section only / no rank)")
        return 0

    if not pool:
        picks = []
        print("[2/3] No articles — skip Qwen")
    else:
        print(
            f"[2/3] Ranking top {args.top} via Qwen "
            f"({config.QWEN_URL})…"
        )
        picks = rank_articles(pool, top_n=args.top)
        print(f"    → {len(picks)} picks")

    md = render_markdown(picks, stats, args.hours, hot_payload)
    out_path = args.out or (out_dir / f"digest-{day}.md")
    out_path.write_text(md, encoding="utf-8")
    print(f"[3/3] Wrote {out_path}")
    print("--- preview ---")
    print(md[:1500])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
