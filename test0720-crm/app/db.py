from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any, Iterator

import psycopg2
import psycopg2.extras

from . import config


@contextmanager
def get_conn() -> Iterator[Any]:
    conn = psycopg2.connect(
        host=config.PG_HOST,
        port=config.PG_PORT,
        user=config.PG_USER,
        password=config.PG_PASSWORD,
        dbname=config.PG_DB,
        connect_timeout=5,
    )
    try:
        yield conn
    finally:
        conn.close()


def fetch_all(sql: str, params: tuple | None = None) -> list[dict]:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params or ())
            rows = cur.fetchall()
            return [dict(r) for r in rows]


def fetch_one(sql: str, params: tuple | None = None) -> dict | None:
    rows = fetch_all(sql, params)
    return rows[0] if rows else None


def execute(sql: str, params: tuple | None = None) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
        conn.commit()


def json_safe(obj: Any) -> Any:
    """Make DB values JSON-serializable."""
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {k: json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_safe(v) for v in obj]
    # uuid, date, datetime, Decimal, etc.
    try:
        json.dumps(obj)
        return obj
    except TypeError:
        return str(obj)
