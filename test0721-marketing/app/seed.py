"""Seed demo marketing content into Redis + optional Postgres form_submissions."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import redis

from . import config
from .db import execute, fetch_one

SEED_KEY = "mkt:demo:seed_v1"
KB_EXTRA_KEY = "mkt:demo:kb_extra_v1"

TEAM = [
    {
        "id": "tm-ceo",
        "name": "何心怡",
        "role": "執行長 / 共同創辦人",
        "dept": "經營",
        "focus": "品牌策略、融資與合作夥伴",
        "email": "xinyi@catch.demo",
        "avatar": "心",
        "skills": ["策略", "品牌", "B2B"],
    },
    {
        "id": "tm-cmo",
        "name": "周子齊",
        "role": "行銷長",
        "dept": "成長",
        "focus": "全渠道成長、預算與 ROAS",
        "email": "ziqi@catch.demo",
        "avatar": "齊",
        "skills": ["Meta 廣告", "會員", "歸因"],
    },
    {
        "id": "tm-crm",
        "name": "高婉庭",
        "role": "CRM 產品負責人",
        "dept": "產品",
        "focus": "catch_crm、詢盤漏斗、私域",
        "email": "wanting@catch.demo",
        "avatar": "婉",
        "skills": ["CRM", "自動化", "企微"],
    },
    {
        "id": "tm-ai",
        "name": "林書澤",
        "role": "AI / 知識庫工程師",
        "dept": "技術",
        "focus": "RAG、Ollama embedding、Qwen 文案",
        "email": "shuze@catch.demo",
        "avatar": "澤",
        "skills": ["RAG", "FastAPI", "向量檢索"],
    },
    {
        "id": "tm-cs",
        "name": "葉采妮",
        "role": "客戶成功",
        "dept": "服務",
        "focus": "上線輔導、案例沉澱、NPS",
        "email": "caini@catch.demo",
        "avatar": "采",
        "skills": ["CS", "培訓", "案例"],
    },
    {
        "id": "tm-design",
        "name": "許沐辰",
        "role": "品牌設計師",
        "dept": "創意",
        "focus": "落地頁、素材、視覺系統",
        "email": "muchen@catch.demo",
        "avatar": "沐",
        "skills": ["UI", "素材", "Landing"],
    },
]

KB_EXTRA = [
    {
        "id": "kb-playbook-growth",
        "category": "營運手冊",
        "title": "CATCH Growth 90 天上線手冊",
        "summary": "從帳戶開通、受眾包匯入到第一波廣告測試的標準作業。",
        "body": (
            "第 1–2 週：串接廣告帳戶與 CRM 詢盤；建立 3 個核心受眾包。"
            "第 3–6 週：跑素材 A/B，每週砍底部 20% 素材。"
            "第 7–12 週：會員復購活動 + EDM 自動化，目標 ROAS ≥ 4。"
        ),
        "owner": "周子齊",
        "tags": ["SOP", "成長", "90天"],
    },
    {
        "id": "kb-rag-howto",
        "category": "AI 知識",
        "title": "內部 RAG 使用規範",
        "summary": "僅可依知識庫檢索內容回答客戶；無命中時要明說不確定。",
        "body": (
            "embedding 使用 Ollama qwen3-embedding:0.6b；生成使用 qwen3:latest（think=false）。"
            "語料來自 marketing_plans、audience_packs、kb_products、competitors 與本知識庫。"
            "禁止把第三方傳聞寫成官方結論。"
        ),
        "owner": "林書澤",
        "tags": ["RAG", "Ollama", "合規"],
    },
    {
        "id": "kb-brand-voice",
        "category": "品牌",
        "title": "品牌語氣指南",
        "summary": "專業但親和，少黑話，多場景。",
        "body": (
            "避免：吊打、革命性、保證暴利。"
            "鼓勵：具體場景、前後對比、可複製步驟、能力邊界。"
            "主視覺：暖沙底 + 成長綠；CTA 用動詞。"
        ),
        "owner": "許沐辰",
        "tags": ["品牌", "文案", "語氣"],
    },
]

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
        "team": TEAM,
        "seeded_at": datetime.now(timezone.utc).isoformat(),
    }
    r.set(SEED_KEY, json.dumps(payload, ensure_ascii=False))
    r.set(KB_EXTRA_KEY, json.dumps(KB_EXTRA, ensure_ascii=False))
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
