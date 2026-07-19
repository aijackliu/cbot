#!/usr/bin/env python3
"""
Daily digest: 熱搜 + Hacker News + Karpathy RSS.

Pipeline:
  [可選] 更新熱搜（F:\\grok\\2，含 LLM 繁中）
  → HN Algolia（front/latest）
  → 92 RSS → 時間窗 → Qwen 排序
  → 合併三章節 Markdown

Usage:
  python run_digest.py
  python run_digest.py --refresh-hot
  python run_digest.py --hn-mode front --hn-top 8
  python run_digest.py --no-hn
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
from scripts.fetch_hn import fetch_hn  # noqa: E402
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
        if p.get("hn_url") and p.get("hn_url") != p.get("link"):
            lines.append(f"- **HN 討論**：{p.get('hn_url')}")
        lines.append("")
        lines.append(p.get("summary_zh") or "")
        if p.get("reason_zh"):
            lines.append("")
            lines.append(f"_{p.get('reason_zh')}_")
        lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines)


def render_hn_section(picks: list[dict], hn_stats: dict | None) -> str:
    st = hn_stats or {}
    mode = st.get("mode") or "front"
    lines = [
        "## Hacker News",
        "",
        f"> 來源：Algolia HN API · mode=`{mode}` · "
        f"{'OK' if st.get('ok', True) else '失敗'} · "
        f"抓取：`{st.get('fetched_at', '')}`",
        "",
    ]
    if st.get("error"):
        lines.append(f"_抓取失敗：{st['error']}_")
        lines.append("")
        lines.append("---")
        lines.append("")
        return "\n".join(lines)
    if not picks:
        lines.append("_無 HN 條目。_")
        lines.append("")
        lines.append("---")
        lines.append("")
        return "\n".join(lines)

    emoji = {"Breaking": "🔴", "Important": "🟡", "Notable": "🔵"}
    for i, p in enumerate(picks, 1):
        cat = p.get("category") or "Notable"
        mark = emoji.get(cat, "⚪")
        meta = p.get("summary") or ""
        lines.append(f"### {i}. {mark} {p.get('title')}")
        lines.append("")
        lines.append(
            f"- **分數**：{p.get('score', '?')} · **meta**：{meta} · **來源**：HN"
        )
        if p.get("link"):
            lines.append(f"- **文章**：{p.get('link')}")
        if p.get("hn_url"):
            lines.append(f"- **討論**：{p.get('hn_url')}")
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
    hn_picks: list[dict] | None = None,
    hn_stats: dict | None = None,
) -> str:
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines = [
        f"# 每日熱點摘要 · {day}",
        "",
        "> **熱搜** ＋ **Hacker News** ＋ **科技部落格**（Karpathy RSS）· 繁中",
        "",
        "---",
        "",
        render_hot_section(hot_payload),
        render_hn_section(hn_picks or [], hn_stats),
        render_blog_section(picks, stats, hours),
        "",
        "熱搜：公開榜接口；HN：Algolia（免 key，預設不抓全文）；"
        "部落格：RSS 標題/摘要。不構成投資建議。",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Daily digest: hot-search + HN + Karpathy RSS"
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
    ap.add_argument("--no-hot", action="store_true", help="不併入熱搜")
    ap.add_argument("--no-hn", action="store_true", help="不併入 Hacker News")
    ap.add_argument(
        "--hn-mode",
        choices=("front", "latest"),
        default="front",
        help="HN front_page（預設）或 latest",
    )
    ap.add_argument("--hn-top", type=int, default=8, help="HN 摘要條數")
    ap.add_argument(
        "--mix-hot-rank",
        action="store_true",
        help="熱搜條目與部落格混排 Top N",
    )
    ap.add_argument(
        "--mix-hn-rank",
        action="store_true",
        help="HN 與部落格混成同一 Top N（預設 HN 獨立成章）",
    )
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    step = 0
    # ── 熱搜 ──────────────────────────────────────────
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
                f"[{step}] 熱搜 date={hot_payload.get('date')} "
                f"headline={(hot_payload.get('summary') or {}).get('headline', '')[:40]}"
            )
        else:
            print(f"[{step}] 尚無熱搜 latest.json（可用 --refresh-hot）")
    step += 1

    # ── HN ────────────────────────────────────────────
    hn_items: list[dict] = []
    hn_stats: dict = {}
    hn_picks: list[dict] = []
    if not args.no_hn:
        print(f"[{step}] Fetching Hacker News (mode={args.hn_mode})…")
        hn_items, hn_stats = fetch_hn(mode=args.hn_mode, limit=max(args.hn_top, 10))
        print(
            f"    → HN {hn_stats.get('count', 0)} stories "
            f"ok={hn_stats.get('ok')}"
        )
    step += 1

    # ── blogs ─────────────────────────────────────────
    print(f"[{step}] Fetching RSS (last {args.hours}h)…")
    articles, stats = fetch_articles(
        hours=args.hours,
        workers=args.workers,
        timeout=config.FETCH_TIMEOUT,
    )
    print(
        f"    → {stats['articles_in_window']} articles, "
        f"{stats['errors']} feed errors"
    )
    step += 1

    pool = list(articles)
    for a in pool:
        a.setdefault("kind", "blog")
    if args.mix_hot_rank and hot_payload:
        hot_arts = tech_hot_as_articles(hot_payload, max_items=20)
        pool = hot_arts + pool
        print(f"    → mixed +{len(hot_arts)} hot items into blog rank pool")
    if args.mix_hn_rank and hn_items:
        pool = hn_items + pool
        print(f"    → mixed +{len(hn_items)} HN into blog rank pool")

    out_dir = ROOT / "output"
    out_dir.mkdir(exist_ok=True)
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    candidates_path = out_dir / f"candidates-{day}.json"
    with open(candidates_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "stats": stats,
                "articles": articles,
                "hn": hn_items,
                "hn_stats": hn_stats,
                "hot_date": (hot_payload or {}).get("date"),
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"    → wrote {candidates_path.name}")

    if args.fetch_only:
        print("[skip] LLM ranking (--fetch-only)")
        # raw HN without zh
        raw_hn = []
        for a in hn_items[: args.hn_top]:
            raw_hn.append(
                {
                    **a,
                    "score": a.get("points") or 5,
                    "category": "Notable",
                    "summary_zh": a.get("summary") or a.get("title"),
                    "reason_zh": "",
                }
            )
        md = render_markdown(
            [], stats, args.hours, hot_payload, raw_hn, hn_stats
        )
        out_path = args.out or (out_dir / f"digest-{day}.md")
        out_path.write_text(md, encoding="utf-8")
        print(f"Wrote {out_path}")
        return 0

    # blog rank
    if not pool:
        picks = []
        print(f"[{step}] No blog articles — skip blog rank")
    else:
        print(f"[{step}] Ranking blogs top {args.top} via Qwen…")
        picks = rank_articles(pool, top_n=args.top)
        print(f"    → {len(picks)} blog picks")
    step += 1

    # HN rank (independent chapter unless mix-hn-rank already used)
    if not args.no_hn and hn_items and not args.mix_hn_rank:
        print(f"[{step}] Ranking HN top {args.hn_top} via Qwen…")
        hn_picks = rank_articles(hn_items, top_n=args.hn_top, max_candidates=20)
        # attach hn_url from source items
        by_title = {a["title"]: a for a in hn_items}
        for p in hn_picks:
            src = by_title.get(p.get("title") or "")
            if src:
                p["hn_url"] = src.get("hn_url")
                p.setdefault("link", src.get("link"))
                p["summary"] = src.get("summary") or p.get("summary")
        print(f"    → {len(hn_picks)} HN picks")
    elif args.mix_hn_rank:
        # HN already inside picks; still show empty separate? skip separate
        hn_picks = [p for p in picks if p.get("kind") == "hn" or p.get("source") == "Hacker News"]
        picks = [p for p in picks if p not in hn_picks]
        if not hn_picks:
            hn_picks = []
    step += 1

    md = render_markdown(
        picks, stats, args.hours, hot_payload, hn_picks, hn_stats
    )
    out_path = args.out or (out_dir / f"digest-{day}.md")
    out_path.write_text(md, encoding="utf-8")
    print(f"[{step}] Wrote {out_path}")
    print("--- preview ---")
    print(md[:1800])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
