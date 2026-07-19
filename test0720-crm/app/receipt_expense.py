"""
Receipt OCR + expense ledger.

Vision: Google AI Studio Gemini (GOOGLE_AI_API_KEY).
Optional text polish: LAN Qwen at QWEN_URL.
Ledger: PostgreSQL catch_crm.receipt_expenses (100.88.220.82:5432).
Receipt image files stay local under data/receipts/.
"""

from __future__ import annotations

import base64
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from . import config
from . import db as pg

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
RECEIPT_DIR = DATA_DIR / "receipts"

CATEGORIES = [
    "餐飲",
    "交通",
    "辦公",
    "農資",
    "設備",
    "住宿",
    "通訊",
    "其他",
]


def _ensure_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    pg.execute(
        """
        CREATE TABLE IF NOT EXISTS receipt_expenses (
          id TEXT PRIMARY KEY,
          vendor TEXT,
          date TEXT,
          currency TEXT,
          subtotal DOUBLE PRECISION,
          tax DOUBLE PRECISION,
          total DOUBLE PRECISION,
          category TEXT,
          notes TEXT,
          line_items_json TEXT,
          image_path TEXT,
          raw_json TEXT,
          created_at BIGINT
        )
        """
    )


def _parse_json_obj(text: str) -> dict:
    text = (text or "").strip()
    text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.I)
    if "```" in text:
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if m:
            text = m.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        return json.loads(text[start : end + 1])
    raise ValueError("no JSON object in model output")


def gemini_extract_receipt(
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
) -> dict[str, Any]:
    key = config.GOOGLE_AI_API_KEY
    if not key:
        raise RuntimeError(
            "未設定 GOOGLE_AI_API_KEY（Google AI Studio）。"
            "請在 test0720-crm/.env 填入金鑰。"
        )
    model = config.GEMINI_VISION_MODEL or "gemini-2.0-flash"
    b64 = base64.b64encode(image_bytes).decode("ascii")
    prompt = (
        "You are a receipt OCR system. Extract structured data from this receipt/invoice image.\n"
        "Return ONLY a JSON object (no markdown, no thinking):\n"
        "{\n"
        '  "vendor": "store name",\n'
        '  "date": "YYYY-MM-DD or empty",\n'
        '  "currency": "TWD/USD/…",\n'
        '  "subtotal": number or null,\n'
        '  "tax": number or null,\n'
        '  "total": number or null,\n'
        '  "category": "one of 餐飲,交通,辦公,農資,設備,住宿,通訊,其他",\n'
        '  "line_items": [{"name":"…","qty":1,"price":0}],\n'
        '  "notes": "short note",\n'
        '  "vendor_zh": "店家名繁中若可",\n'
        '  "summary_zh": "一句繁中摘要"\n'
        "}\n"
        "If unclear, use null/empty. Prefer Traditional Chinese for summary_zh and category."
    )
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={urllib.parse.quote(key, safe='')}"
    )
    body = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": mime_type or "image/jpeg",
                            "data": b64,
                        }
                    },
                ]
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
        raise RuntimeError(f"Gemini HTTP {e.code}: {err[:500]}") from e

    # parse candidates
    cands = raw.get("candidates") or []
    text = ""
    if cands:
        parts = ((cands[0].get("content") or {}).get("parts")) or []
        text = "".join(p.get("text") or "" for p in parts)
    if not text:
        raise RuntimeError("Gemini 未回傳文字")
    data = _parse_json_obj(text)
    data["_vision_model"] = model
    data["_raw_text_preview"] = text[:300]
    return data


def qwen_polish_zh(extracted: dict[str, Any]) -> dict[str, Any]:
    """Optional: polish category/summary via LAN Qwen text endpoint."""
    try:
        payload = {
            "model": config.QWEN_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "將收據 JSON 的 category 歸到："
                        + "、".join(CATEGORIES)
                        + "；summary_zh 寫一句繁中。只輸出 JSON："
                        '{"category":"…","summary_zh":"…"}'
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "vendor": extracted.get("vendor"),
                            "total": extracted.get("total"),
                            "line_items": extracted.get("line_items"),
                            "category": extracted.get("category"),
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            "temperature": 0.1,
            "max_tokens": 200,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        req = urllib.request.Request(
            config.QWEN_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
        msg = (raw.get("choices") or [{}])[0].get("message") or {}
        text = (msg.get("content") or msg.get("reasoning_content") or "").strip()
        patch = _parse_json_obj(text)
        if patch.get("category"):
            extracted["category"] = patch["category"]
        if patch.get("summary_zh"):
            extracted["summary_zh"] = patch["summary_zh"]
    except Exception:  # noqa: BLE001
        pass
    return extracted


def extract_and_optionally_polish(
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    polish: bool = True,
) -> dict[str, Any]:
    data = gemini_extract_receipt(image_bytes, mime_type=mime_type)
    if polish:
        data = qwen_polish_zh(data)
    # normalize numbers
    for k in ("subtotal", "tax", "total"):
        v = data.get(k)
        if v is not None:
            try:
                data[k] = float(v)
            except (TypeError, ValueError):
                data[k] = None
    cat = data.get("category") or "其他"
    if cat not in CATEGORIES:
        data["category"] = "其他"
    return data


def save_expense(
    extracted: dict[str, Any],
    image_bytes: bytes | None = None,
    mime_type: str = "image/jpeg",
) -> dict[str, Any]:
    _ensure_db()
    eid = uuid.uuid4().hex[:12]
    image_path = ""
    if image_bytes:
        ext = ".jpg"
        if "png" in (mime_type or ""):
            ext = ".png"
        elif "webp" in (mime_type or ""):
            ext = ".webp"
        path = RECEIPT_DIR / f"{eid}{ext}"
        path.write_bytes(image_bytes)
        image_path = str(path.relative_to(DATA_DIR.parent))

    rec = {
        "id": eid,
        "vendor": extracted.get("vendor") or extracted.get("vendor_zh") or "",
        "date": extracted.get("date") or "",
        "currency": extracted.get("currency") or "TWD",
        "subtotal": extracted.get("subtotal"),
        "tax": extracted.get("tax"),
        "total": extracted.get("total"),
        "category": extracted.get("category") or "其他",
        "notes": extracted.get("notes")
        or extracted.get("summary_zh")
        or "",
        "line_items_json": json.dumps(
            extracted.get("line_items") or [], ensure_ascii=False
        ),
        "image_path": image_path,
        "raw_json": json.dumps(extracted, ensure_ascii=False),
        "created_at": int(time.time()),
    }
    pg.execute(
        """
        INSERT INTO receipt_expenses
        (id, vendor, date, currency, subtotal, tax, total, category,
         notes, line_items_json, image_path, raw_json, created_at)
        VALUES
        (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            rec["id"],
            rec["vendor"],
            rec["date"],
            rec["currency"],
            rec["subtotal"],
            rec["tax"],
            rec["total"],
            rec["category"],
            rec["notes"],
            rec["line_items_json"],
            rec["image_path"],
            rec["raw_json"],
            rec["created_at"],
        ),
    )
    return rec


def list_expenses(limit: int = 50) -> list[dict[str, Any]]:
    _ensure_db()
    rows = pg.fetch_all(
        """
        SELECT * FROM receipt_expenses
        ORDER BY created_at DESC
        LIMIT %s
        """,
        (limit,),
    )
    out = []
    for r in rows:
        d = pg.json_safe(r)
        try:
            d["line_items"] = json.loads(d.get("line_items_json") or "[]")
        except (TypeError, json.JSONDecodeError):
            d["line_items"] = []
        out.append(d)
    return out


def delete_expense(expense_id: str) -> bool:
    _ensure_db()
    before = pg.fetch_one(
        "SELECT id FROM receipt_expenses WHERE id = %s", (expense_id,)
    )
    if not before:
        return False
    pg.execute("DELETE FROM receipt_expenses WHERE id = %s", (expense_id,))
    return True


def summary_by_category() -> list[dict[str, Any]]:
    _ensure_db()
    rows = pg.fetch_all(
        """
        SELECT category,
               COUNT(*)::int AS n,
               COALESCE(SUM(total), 0)::float AS sum_total
        FROM receipt_expenses
        GROUP BY category
        ORDER BY sum_total DESC
        """
    )
    return [pg.json_safe(r) for r in rows]
