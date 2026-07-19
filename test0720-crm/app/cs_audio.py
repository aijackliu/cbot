"""
CS bus voice input: browser mic → Gemini (no GPU) → transcript text.
Transcript then feeds route / support / form / sql / crm handlers.
"""

from __future__ import annotations

import base64
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from . import config

TRANSCRIBE_PROMPT = (
    "你是客服語音轉寫引擎。請把這段客戶錄音轉成繁體中文文字。"
    "只輸出客戶所說內容的純文字，不要加引號、標題、解釋或時間戳。"
    "若幾乎聽不清，輸出：【聽不清】並簡短註明原因。"
    "若是英文或其他語言，請轉寫原文並在括號內附繁中大意。"
)


def _normalize_mime(mime_type: str | None) -> str:
    mime = (mime_type or "audio/webm").split(";")[0].strip().lower()
    if mime in ("audio/webm", "video/webm"):
        return "audio/webm"
    if mime in ("audio/mp4", "audio/m4a", "audio/x-m4a"):
        return "audio/mp4"
    if mime in ("audio/ogg", "audio/opus"):
        return "audio/ogg"
    if mime.startswith("audio/"):
        return mime
    return "audio/webm"


def _extract_text(raw: dict[str, Any]) -> str:
    cands = raw.get("candidates") or []
    if not cands:
        fb = raw.get("promptFeedback") or {}
        raise RuntimeError(
            f"Gemini 無 candidates：{json.dumps(fb, ensure_ascii=False)[:400]}"
        )
    parts = ((cands[0].get("content") or {}).get("parts")) or []
    text = "".join(p.get("text") or "" for p in parts).strip()
    text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.I).strip()
    if not text:
        raise RuntimeError("Gemini 回傳空白轉寫")
    return text


def transcribe_audio(audio_bytes: bytes, mime_type: str = "audio/webm") -> dict[str, Any]:
    """Speech → text via Google AI Studio Gemini (no local model / GPU)."""
    key = config.GOOGLE_AI_API_KEY
    if not key:
        raise RuntimeError(
            "未設定 GOOGLE_AI_API_KEY。請在 .env 填入 Google AI Studio 金鑰。"
        )
    if not audio_bytes:
        raise RuntimeError("音訊為空")
    if len(audio_bytes) > 12 * 1024 * 1024:
        raise RuntimeError("音訊過大（請錄 30 秒內）")

    model = getattr(config, "GEMINI_AUDIO_MODEL", None) or config.GEMINI_VISION_MODEL or "gemini-2.0-flash"
    mime = _normalize_mime(mime_type)
    b64 = base64.b64encode(audio_bytes).decode("ascii")
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={urllib.parse.quote(key, safe='')}"
    )
    body = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": TRANSCRIBE_PROMPT},
                    {"inline_data": {"mime_type": mime, "data": b64}},
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 2048,
        },
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini HTTP {e.code}: {err[:600]}") from e

    text = _extract_text(raw)
    # strip common wrappers
    if text.startswith("「") and text.endswith("」"):
        text = text[1:-1].strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'“”":
        text = text[1:-1].strip()
    return {
        "transcript": text,
        "model": model,
        "mime_type": mime,
        "bytes": len(audio_bytes),
    }
