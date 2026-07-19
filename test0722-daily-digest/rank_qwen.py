"""Score / rank articles with LAN Qwen (OpenAI-compatible)."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any

import config


def _extract_text(message: dict) -> str:
    content = (message.get("content") or "").strip()
    reason = (message.get("reasoning_content") or "").strip()
    # Prefer JSON-looking blobs from either field
    for blob in (content, reason, f"{content}\n{reason}"):
        if "[" in blob and "]" in blob:
            return blob
    if content:
        return content
    return reason


def _chat(system: str, user: str, max_tokens: int = 2000) -> str:
    payload = {
        "model": config.QWEN_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.15,
        "max_tokens": max_tokens,
    }
    # hint some servers to skip long chain-of-thought
    payload["chat_template_kwargs"] = {"enable_thinking": False}
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
        raise RuntimeError(f"Qwen HTTP {e.code}: {err[:500]}") from e

    choice = (raw.get("choices") or [{}])[0]
    return _extract_text(choice.get("message") or {})


def _parse_pipe_lines(text: str, top_n: int) -> list[dict]:
    """Fallback format: INDEX|score|Category|summary_zh|reason_zh"""
    rows: list[dict] = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "|" not in line:
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 4:
            continue
        try:
            idx = int(re.sub(r"[^\d-]", "", parts[0]))
            score = float(re.sub(r"[^\d.]", "", parts[1]) or "5")
        except ValueError:
            continue
        cat = parts[2] if parts[2] in ("Breaking", "Important", "Notable") else "Notable"
        rows.append(
            {
                "index": idx,
                "score": score,
                "category": cat,
                "summary_zh": parts[3] if len(parts) > 3 else "",
                "reason_zh": parts[4] if len(parts) > 4 else "",
            }
        )
        if len(rows) >= top_n:
            break
    return rows


def _parse_json_list(text: str) -> list[dict]:
    text = (text or "").strip()
    # drop common think wrappers
    text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.I)
    text = re.sub(r"<reasoning>[\s\S]*?</reasoning>", "", text, flags=re.I)
    if "```" in text:
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if m:
            text = m.group(1).strip()
    # try full / bracket slice / first array via raw_decode
    candidates: list[str] = [text]
    start = text.find("[")
    end = text.rfind("]")
    if start >= 0 and end > start:
        candidates.insert(0, text[start : end + 1])
    for cand in candidates:
        try:
            data = json.loads(cand)
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and isinstance(data.get("items"), list):
                return data["items"]
        except json.JSONDecodeError:
            pass
        if start >= 0:
            try:
                data, _ = json.JSONDecoder().raw_decode(text[start:])
                if isinstance(data, list):
                    return data
            except json.JSONDecodeError:
                pass
    raise ValueError(f"expected JSON array, got: {text[:200]!r}")


def rank_articles(
    articles: list[dict[str, Any]],
    top_n: int | None = None,
    max_candidates: int | None = None,
) -> list[dict[str, Any]]:
    top_n = top_n if top_n is not None else config.TOP_N
    max_candidates = (
        max_candidates
        if max_candidates is not None
        else config.MAX_CANDIDATES_FOR_LLM
    )
    if not articles:
        return []

    batch = articles[:max_candidates]
    lines = []
    for i, a in enumerate(batch):
        lines.append(
            f"[{i}] source={a.get('source')}\n"
            f"title={a.get('title')}\n"
            f"summary={a.get('summary') or '(none)'}\n"
            f"link={a.get('link')}\n"
        )
    catalog = "\n---\n".join(lines)

    system = (
        "You are a tech news editor for engineers. "
        "Prefer depth, security, novel systems; skip marketing fluff. "
        "Write summary_zh and reason_zh in Traditional Chinese. "
        "Do NOT write chain-of-thought. Output data only."
    )
    user = (
        f"Pick top {top_n} articles. Output EXACTLY {top_n} lines, nothing else.\n"
        "Each line format (pipe-separated):\n"
        "INDEX|SCORE|CATEGORY|繁中摘要|繁中為何重要\n"
        "CATEGORY is Breaking or Important or Notable. SCORE is 0-10.\n"
        "INDEX is the number in [i]. Sort by SCORE desc.\n"
        "Example:\n"
        "3|9|Important|……|……\n\n"
        f"{catalog}"
    )

    raw = _chat(system, user, max_tokens=1800)
    picks: list[dict] = []
    try:
        picks = _parse_json_list(raw)
    except (json.JSONDecodeError, ValueError):
        picks = _parse_pipe_lines(raw, top_n)

    if not picks:
        try:
            from pathlib import Path

            Path(__file__).resolve().parent.joinpath(
                "output", "_last_rank_raw.txt"
            ).write_text(raw or "", encoding="utf-8")
        except OSError:
            pass
        out = []
        for a in batch[:top_n]:
            out.append(
                {
                    **a,
                    "score": 5,
                    "category": "Notable",
                    "summary_zh": (a.get("summary") or a.get("title") or "")[:280],
                    "reason_zh": "（模型未回傳可解析格式；改以時間排序）",
                }
            )
        return out
    ranked: list[dict[str, Any]] = []
    for p in picks:
        try:
            idx = int(p.get("index"))
        except (TypeError, ValueError):
            continue
        if idx < 0 or idx >= len(batch):
            continue
        base = dict(batch[idx])
        base["score"] = p.get("score")
        base["category"] = p.get("category") or "Notable"
        base["summary_zh"] = p.get("summary_zh") or base.get("summary") or ""
        base["reason_zh"] = p.get("reason_zh") or ""
        ranked.append(base)

    if not ranked:
        for a in batch[:top_n]:
            ranked.append(
                {
                    **a,
                    "score": 5,
                    "category": "Notable",
                    "summary_zh": a.get("summary") or a.get("title"),
                    "reason_zh": "（模型未回傳有效 index）",
                }
            )
    return ranked[:top_n]
