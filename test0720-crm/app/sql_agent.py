"""
Agentic NL → SQL (read-only) for catch_crm.

Pattern from Hands-On agentic_sql_search:
  load skill → inspect schema → execute SELECT → answer in zh-Hant.

Uses LAN Qwen + Postgres. Whitelist tables; SELECT-only; row/time limits.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any

import psycopg2
import psycopg2.extras

from . import config
from .db import json_safe

# Demo whitelist — only tables used by CRM UI
ALLOWED_TABLES: dict[str, str] = {
    "accounts": "B2B 客戶帳戶",
    "opportunities": "銷售機會／管道",
    "activities": "活動／跟進紀錄",
    "web_customers": "電商客戶",
    "web_orders": "電商訂單",
    "competitors": "競品主檔",
    "competitor_signals": "競品訊號",
    "war_room_snapshots": "戰情快照",
    "form_submissions": "表單詢盤（若存在）",
    "ad_daily": "廣告日報（若存在）",
    "marketing_plans": "行銷計畫（若存在）",
}

ROW_LIMIT = 50
STATEMENT_TIMEOUT_MS = 8000

SQL_SKILL = """
# Postgres read-only SQL skill (catch_crm)

Rules:
- Output a SINGLE SELECT (or WITH ... SELECT). No INSERT/UPDATE/DELETE/DDL.
- No multiple statements. No semicolons mid-string abuse.
- Always LIMIT results (max 50 unless counting aggregates only).
- Prefer explicit column lists over SELECT * for wide tables.
- Money/amount columns are often NTD; label clearly in the answer.
- JOIN only on whitelist tables.
- If question cannot be answered from schema, say so — do not invent tables.
"""


def _chat_qwen(system: str, user: str, max_tokens: int = 1200) -> str:
    payload = {
        "model": config.QWEN_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.15,
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
    msg = (raw.get("choices") or [{}])[0].get("message") or {}
    content = (msg.get("content") or "").strip()
    reason = (msg.get("reasoning_content") or "").strip()
    for blob in (content, reason, f"{content}\n{reason}"):
        if blob.strip():
            return blob
    return ""


def _parse_json_obj(text: str) -> dict:
    text = (text or "").strip()
    text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.I)
    if "```" in text:
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if m:
            text = m.group(1).strip()
    # also accept fenced sql only later
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return json.loads(text[start : end + 1])
    raise ValueError("no JSON object")


def get_schema() -> dict[str, Any]:
    """Live columns for whitelist tables that exist."""
    sql = """
    SELECT table_name, column_name, data_type
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = ANY(%s)
    ORDER BY table_name, ordinal_position
    """
    names = list(ALLOWED_TABLES.keys())
    with psycopg2.connect(
        host=config.PG_HOST,
        port=config.PG_PORT,
        user=config.PG_USER,
        password=config.PG_PASSWORD,
        dbname=config.PG_DB,
        connect_timeout=5,
    ) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (names,))
            rows = [dict(r) for r in cur.fetchall()]

    tables: dict[str, list[dict]] = {}
    for r in rows:
        t = r["table_name"]
        tables.setdefault(t, []).append(
            {"column": r["column_name"], "type": r["data_type"]}
        )

    return {
        "allowed": {
            k: ALLOWED_TABLES[k] for k in tables.keys() if k in ALLOWED_TABLES
        },
        "tables": tables,
        "skill": SQL_SKILL.strip(),
    }


def validate_select(sql: str) -> str:
    s = (sql or "").strip().rstrip(";").strip()
    if not s:
        raise ValueError("空 SQL")
    # strip line comments
    lines = []
    for line in s.splitlines():
        if "--" in line:
            line = line[: line.index("--")]
        lines.append(line)
    s = "\n".join(lines).strip()
    low = s.lower()
    if ";" in s:
        raise ValueError("不允許多語句")
    # allow WITH ... SELECT
    if not (low.startswith("select") or low.startswith("with")):
        raise ValueError("僅允許 SELECT / WITH…SELECT")
    forbidden = [
        "insert ",
        "update ",
        "delete ",
        "drop ",
        "alter ",
        "create ",
        "truncate ",
        "grant ",
        "revoke ",
        "copy ",
        "execute ",
        "call ",
        " into ",
        "pg_sleep",
        "dblink",
    ]
    for bad in forbidden:
        if bad in low:
            raise ValueError(f"禁止關鍵字：{bad.strip()}")
    # table whitelist: every relation-like identifier after from/join
    # simple check: any known non-whitelist public table word is hard;
    # require that if we see FROM x, x is whitelist or alias
    tokens = re.findall(r"\b([a-z_][a-z0-9_]*)\b", low)
    # reject if mentions table-like names outside whitelist
    # (skip sql keywords)
    keywords = {
        "select",
        "from",
        "where",
        "and",
        "or",
        "group",
        "by",
        "order",
        "limit",
        "offset",
        "as",
        "on",
        "join",
        "left",
        "right",
        "inner",
        "outer",
        "full",
        "cross",
        "with",
        "case",
        "when",
        "then",
        "else",
        "end",
        "null",
        "not",
        "in",
        "is",
        "like",
        "ilike",
        "between",
        "distinct",
        "count",
        "sum",
        "avg",
        "min",
        "max",
        "coalesce",
        "cast",
        "having",
        "union",
        "all",
        "true",
        "false",
        "asc",
        "desc",
        "nulls",
        "first",
        "last",
        "over",
        "partition",
        "row",
        "rows",
        "extract",
        "date",
        "timestamp",
        "interval",
        "integer",
        "text",
        "numeric",
        "boolean",
        "exists",
        "any",
        "some",
        "lateral",
        "using",
        "natural",
        "except",
        "intersect",
        "filter",
        "within",
        "array",
        "json",
        "jsonb",
    }
    # only flag tokens that appear after from/join that look like tables
    # simpler: any ALLOWED not required; if token is a known PG system table or
    # common table name not in whitelist
    for i, tok in enumerate(tokens):
        if tok in keywords:
            continue
        if tok in ALLOWED_TABLES:
            continue
        # if previous keyword is from/join, and token not allowed → reject
        if i > 0 and tokens[i - 1] in ("from", "join"):
            # could be subquery alias — if next is ( skip
            if tok not in ALLOWED_TABLES and len(tok) > 2:
                # allow common aliases like a, o, t, c, s, w
                if len(tok) <= 2:
                    continue
                if tok not in ALLOWED_TABLES:
                    raise ValueError(f"資料表不在白名單：{tok}")
    return s


def execute_select(sql: str) -> dict[str, Any]:
    safe = validate_select(sql)
    # inject LIMIT if missing and not pure aggregate-only (heuristic)
    low = safe.lower()
    if "limit" not in low:
        safe = f"{safe}\nLIMIT {ROW_LIMIT}"
    with psycopg2.connect(
        host=config.PG_HOST,
        port=config.PG_PORT,
        user=config.PG_USER,
        password=config.PG_PASSWORD,
        dbname=config.PG_DB,
        connect_timeout=5,
        options=f"-c statement_timeout={STATEMENT_TIMEOUT_MS}",
    ) as conn:
        conn.set_session(readonly=True, autocommit=True)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(safe)
            rows = cur.fetchmany(ROW_LIMIT)
            cols = [d[0] for d in cur.description] if cur.description else []
            data = [json_safe(dict(r)) for r in rows]
    return {"sql": safe, "columns": cols, "rows": data, "row_count": len(data)}


def ask(question: str) -> dict[str, Any]:
    """Full pipeline: schema → generate SQL → execute → explain."""
    schema = get_schema()
    schema_txt = json.dumps(
        {
            "allowed": schema["allowed"],
            "tables": schema["tables"],
        },
        ensure_ascii=False,
        indent=2,
    )[:12000]

    system = (
        "You are a Postgres analyst for CATCH CRM. "
        "Follow the SQL skill. Output ONLY one JSON object:\n"
        '{"sql":"SELECT ...","rationale_zh":"為何這樣查"}\n'
        "No markdown outside JSON. No chain-of-thought. "
        "Traditional Chinese for rationale_zh."
    )
    user = (
        f"{SQL_SKILL}\n\n"
        f"SCHEMA:\n{schema_txt}\n\n"
        f"QUESTION (zh/en ok):\n{question}\n"
    )
    raw = _chat_qwen(system, user, max_tokens=800)
    try:
        plan = _parse_json_obj(raw)
        sql = (plan.get("sql") or "").strip()
        rationale = (plan.get("rationale_zh") or "").strip()
    except (json.JSONDecodeError, ValueError):
        # try extract SQL from fences
        m = re.search(r"```(?:sql)?\s*([\s\S]*?)```", raw, re.I)
        sql = (m.group(1) if m else raw).strip()
        rationale = "（模型未回傳 JSON，已嘗試抽取 SQL）"

    steps: list[dict] = [
        {"step": "load_skill", "ok": True, "detail": "sql skill applied"},
        {
            "step": "get_schema",
            "ok": True,
            "detail": f"{len(schema['tables'])} tables",
            "tables": list(schema["tables"].keys()),
        },
    ]

    try:
        result = execute_select(sql)
        steps.append(
            {
                "step": "execute_sql",
                "ok": True,
                "sql": result["sql"],
                "row_count": result["row_count"],
            }
        )
    except Exception as e:  # noqa: BLE001
        steps.append({"step": "execute_sql", "ok": False, "error": str(e), "sql": sql})
        return {
            "ok": False,
            "question": question,
            "sql": sql,
            "rationale_zh": rationale,
            "error": str(e),
            "steps": steps,
            "columns": [],
            "rows": [],
            "answer_zh": f"查詢失敗：{e}",
        }

    # answer from rows
    sample = json.dumps(result["rows"][:15], ensure_ascii=False, default=str)[:4000]
    ans_system = (
        "你是 CATCH CRM 分析助理。根據 SQL 結果用繁體中文簡潔回答用戶問題。"
        "可引用數字；不要編造結果中沒有的資料。2–6 句即可。"
    )
    ans_user = (
        f"問題：{question}\n"
        f"SQL：{result['sql']}\n"
        f"列數：{result['row_count']}\n"
        f"資料：{sample}\n"
    )
    try:
        answer = _chat_qwen(ans_system, ans_user, max_tokens=600).strip()
    except Exception as e:  # noqa: BLE001
        answer = f"（結果已查出 {result['row_count']} 列；摘要生成失敗：{e}）"

    steps.append({"step": "answer", "ok": True})
    return {
        "ok": True,
        "question": question,
        "sql": result["sql"],
        "rationale_zh": rationale,
        "columns": result["columns"],
        "rows": result["rows"],
        "row_count": result["row_count"],
        "answer_zh": answer,
        "steps": steps,
    }
