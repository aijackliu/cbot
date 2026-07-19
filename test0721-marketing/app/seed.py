"""Seed demo marketing content into Redis + optional Postgres form_submissions."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import redis

from . import config
from .db import execute, fetch_one

SEED_KEY = "mkt:demo:seed_v1"

TESTIMONIALS = [
    {
        "name": "林怡君",
        "role": "行銷總監",
        "company": "綠意食堂連鎖",
        "quote": "以前每週開會才對得上廣告數字，現在儀表板一開就知道哪條素材該砍、哪條該加碼。",
        "score": 5,
    },
    {
        "name": "張偉誠",
        "role": "創辦人",
        "company": "山海選物",
        "quote": "Qwen 幫我們把官網文案從「產品規格」改成「顧客場景」，詢盤率明顯上來。",
        "score": 5,
    },
    {
        "name": "陳佳蓉",
        "role": "品牌經理",
        "company": "禾風茶業",
        "quote": "受眾包與 CRM 串起來之後，EDM 不再亂槍打鳥，退訂率掉了一截。",
        "score": 4,
    },
]

CASES = [
    {
        "title": "素食會員增長年",
        "metric": "廣告歸因營收 +38%",
        "desc": "以 Meta 素材測試 + 會員分群，把高 LTV 客群從內容一路養到復購。",
        "tag": "成長",
    },
    {
        "title": "門市詢盤自動化",
        "metric": "表單 → 銷售工單 15 分鐘內",
        "desc": "官網表單進線後自動摘要意向，轉交業務，減少漏接。",
        "tag": "轉換",
    },
    {
        "title": "競品情報週報",
        "metric": "每週 1 份可執行決策",
        "desc": "只報官方可驗證變更與競品訊號，會議不再被傳聞帶跑。",
        "tag": "情報",
    },
]

PRICING = [
    {
        "name": "Starter",
        "price": "NT$9,800",
        "period": "/月",
        "features": ["行銷儀表板", "基礎受眾包", "週報 4 次", "Email 支援"],
        "cta": "開始試用",
        "highlight": False,
    },
    {
        "name": "Growth",
        "price": "NT$28,000",
        "period": "/月",
        "features": [
            "全渠道廣告看板",
            "Qwen 文案助理",
            "表單與 CRM 串接",
            "競品訊號",
            "專屬成功顧問",
        ],
        "cta": "預約演示",
        "highlight": True,
    },
    {
        "name": "Enterprise",
        "price": "專案報價",
        "period": "",
        "features": ["私有部署", "SSO／權限", "客製知識庫", "SLA", "駐場 FDE 可選"],
        "cta": "聯絡我們",
        "highlight": False,
    },
]

FAKE_LEADS = [
    ("王小明", "hming@demo.local", "0912-000-111", "日日好食", "會員經營"),
    ("李雅婷", "yating@demo.local", "0922-000-222", "北區烘焙", "廣告素材"),
    ("周俊豪", "junhao@demo.local", "0933-000-333", "雲端餐飲 SaaS", "API 串接"),
    ("黃詩涵", "shihan@demo.local", "0955-000-444", "有機選品", "EDM 自動化"),
    ("吳柏宇", "boyu@demo.local", "0966-000-555", "連鎖茶飲", "私域導流"),
]


def seed_redis() -> dict:
    r = redis.Redis(
        host=config.REDIS_HOST,
        port=config.REDIS_PORT,
        decode_responses=True,
        socket_connect_timeout=3,
    )
    payload = {
        "testimonials": TESTIMONIALS,
        "cases": CASES,
        "pricing": PRICING,
        "seeded_at": datetime.now(timezone.utc).isoformat(),
    }
    r.set(SEED_KEY, json.dumps(payload, ensure_ascii=False))
    r.set("mkt:demo:heartbeat", datetime.now(timezone.utc).isoformat())
    return payload


def seed_leads_if_needed() -> int:
    """Insert a few demo form_submissions if table is sparse."""
    row = fetch_one("SELECT COUNT(*)::int AS n FROM form_submissions")
    n = row["n"] if row else 0
    if n >= 8:
        return 0
    added = 0
    for name, email, phone, company, interest in FAKE_LEADS:
        exists = fetch_one(
            "SELECT id FROM form_submissions WHERE email = %s LIMIT 1",
            (email,),
        )
        if exists:
            continue
        execute(
            """
            INSERT INTO form_submissions
              (id, form_type, name, email, phone, company, stores, interest,
               message, source, payload, status, created_at)
            VALUES
              (%s, 'lead', %s, %s, %s, %s, 1, %s,
               %s, 'marketing_site_demo', '{}'::jsonb, 'new', NOW())
            """,
            (
                str(uuid.uuid4()),
                name,
                email,
                phone,
                company,
                interest,
                f"來自行銷展示站的假資料詢盤：{interest}",
            ),
        )
        added += 1
    return added


def run_seed() -> dict:
    redis_payload = seed_redis()
    leads = 0
    try:
        leads = seed_leads_if_needed()
    except Exception as e:  # noqa: BLE001
        leads = -1
        redis_payload["lead_seed_error"] = str(e)
    redis_payload["leads_inserted"] = leads
    return redis_payload
