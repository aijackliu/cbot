"""
Agricultural multi-tool assistant (lightweight).

Pattern from Hands-On llm_agri_bot:
  weather · crop calendar · web snippets → Qwen advice.

Uses LAN Qwen; weather via wttr.in (no key) or OpenWeather if OPENWEATHER_API_KEY set.
Web: Google News RSS (agri keywords). Crop calendar: static TW-oriented KB.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any

from . import config

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")

# TW / common crops — 示意知識，非正式農技處方
CROP_CALENDAR: list[dict[str, str]] = [
    {
        "crop": "水稻",
        "aliases": "稻 稻米 rice 一期作 二期作",
        "plant": "一期作約 2–3 月插秧；二期作約 6–7 月（依縣市略有差異）。",
        "harvest": "一期約 6–7 月；二期約 10–11 月收割。",
        "tips": "注意灌溉排水、穗稻熱病與稻飛蝨；勿在強颱前強行收割。",
    },
    {
        "crop": "番茄",
        "aliases": "tomato 蕃茄",
        "plant": "春作 1–3 月、秋作 8–10 月育苗定植（平地）。",
        "harvest": "定植後約 70–90 日開始採收，持續分批。",
        "tips": "黃葉常見缺水、青枯病或養分；保持通風、避免葉面長濕。",
    },
    {
        "crop": "玉米",
        "aliases": "maize corn 甜玉米",
        "plant": "平地幾乎全年可種；春作 2–3 月、秋作 8–9 月較穩。",
        "harvest": "乳熟期採甜玉米；飼料玉米待籽粒硬熟。",
        "tips": "注意螟蟲、銹病；忌連作重病田。",
    },
    {
        "crop": "葉菜",
        "aliases": "小白菜 青江菜 菠菜 萵苣 leafy",
        "plant": "冷涼季較佳；高溫期需遮陰與水分管理。",
        "harvest": "播種後 20–40 日可採（視品種）。",
        "tips": "軟腐病、蚜蟲常見；雨後注意排水。",
    },
    {
        "crop": "茶",
        "aliases": "茶葉 tea 烏龍",
        "plant": "扦插／更新多在春季；依海拔與品種調整。",
        "harvest": "春茶、夏茶、秋茶、冬片分批採。",
        "tips": "小綠葉蟬、餅病；勿過量農藥，遵守安全採收期。",
    },
    {
        "crop": "香蕉",
        "aliases": "banana 蕉",
        "plant": "吸芽種植幾乎全年；避開淹水。",
        "harvest": "抽穗後約 3–4 月採收（視品種氣候）。",
        "tips": "黃葉病（TR4）高風險區需檢疫；防風支柱。",
    },
    {
        "crop": "芒果",
        "aliases": "mango 愛文 金煌",
        "plant": "嫁接苗冬末春初定植。",
        "harvest": "愛文約 5–7 月；依產區調整。",
        "tips": "炭疽病、果實蠅；套袋與清園重要。",
    },
    {
        "crop": "鳳梨",
        "aliases": "pineapple 旺來 金鑽",
        "plant": "吸芽／冠芽種植；春、秋較穩。",
        "harvest": "催花後約 5–6 月採（視管理）。",
        "tips": "心腐病、乾旱與積水皆傷根。",
    },
    {
        "crop": "葡萄",
        "aliases": "grape 巨峰",
        "plant": "落葉期修剪與更新；平地溫室與坡地管理不同。",
        "harvest": "夏季為主，設施可調節。",
        "tips": "白粉病、露菌病；通風與藥劑輪用。",
    },
    {
        "crop": "胡椒/辣椒",
        "aliases": "pepper 辣椒 青椒 chilli",
        "plant": "春、秋定植；忌連作。",
        "harvest": "青熟或紅熟分批採。",
        "tips": "蚜蟲、炭疽；注意疫病。",
    },
    {
        "crop": "甘藷",
        "aliases": "地瓜 sweet potato 番薯",
        "plant": "春植 3–5 月、秋植 8–9 月扦插。",
        "harvest": "種植後約 4–6 月掘收。",
        "tips": "象鼻蟲、水濕傷塊根。",
    },
    {
        "crop": "大豆",
        "aliases": "soybean 黃豆 edamame",
        "plant": "春作、秋作；排水良好砂質壤土。",
        "harvest": "豆莢鼓粒後依用途採。",
        "tips": "根瘤菌接種有助氮；注意豆莢螟。",
    },
]


def _http_get(url: str, timeout: float = 12.0) -> bytes:
    req = urllib.request.Request(
        url, headers={"User-Agent": "cbot-agri-bot/1.0"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def tool_crop_calendar(query: str) -> dict[str, Any]:
    q = (query or "").lower()
    hits = []
    for c in CROP_CALENDAR:
        blob = f"{c['crop']} {c['aliases']}".lower()
        score = sum(1 for t in re.split(r"\s+", q) if len(t) >= 2 and t in blob)
        if c["crop"] in query or any(
            a and a in query for a in c["aliases"].split()
        ):
            score += 3
        if score > 0:
            hits.append((score, c))
    hits.sort(key=lambda x: x[0], reverse=True)
    crops = [h[1] for h in hits[:4]]
    if not crops:
        crops = CROP_CALENDAR[:3]
    return {
        "tool": "crop_calendar",
        "ok": True,
        "crops": [
            {
                "crop": c["crop"],
                "plant": c["plant"],
                "harvest": c["harvest"],
                "tips": c["tips"],
            }
            for c in crops
        ],
    }


def tool_weather(location: str) -> dict[str, Any]:
    loc = (location or "台北").strip() or "台北"
    # Prefer OpenWeather if key present
    if OPENWEATHER_API_KEY:
        try:
            q = urllib.parse.quote(loc)
            url = (
                "https://api.openweathermap.org/data/2.5/weather"
                f"?q={q}&appid={OPENWEATHER_API_KEY}&units=metric&lang=zh_tw"
            )
            data = json.loads(_http_get(url).decode("utf-8"))
            return {
                "tool": "weather",
                "ok": True,
                "provider": "openweathermap",
                "location": data.get("name") or loc,
                "temp_c": (data.get("main") or {}).get("temp"),
                "humidity": (data.get("main") or {}).get("humidity"),
                "desc": ((data.get("weather") or [{}])[0]).get("description"),
                "wind_ms": (data.get("wind") or {}).get("speed"),
            }
        except Exception as e:  # noqa: BLE001
            owm_err = str(e)
    else:
        owm_err = None

    # Free fallback: wttr.in JSON
    try:
        q = urllib.parse.quote(loc)
        url = f"https://wttr.in/{q}?format=j1"
        data = json.loads(_http_get(url, timeout=15).decode("utf-8"))
        cur = (data.get("current_condition") or [{}])[0]
        area = ((data.get("nearest_area") or [{}])[0].get("areaName") or [{}])[0]
        return {
            "tool": "weather",
            "ok": True,
            "provider": "wttr.in",
            "location": area.get("value") or loc,
            "temp_c": cur.get("temp_C"),
            "humidity": cur.get("humidity"),
            "desc": ((cur.get("lang_zh") or cur.get("weatherDesc") or [{}])[0]).get(
                "value"
            ),
            "wind_ms": cur.get("windspeedKmph"),
            "note": "風速單位可能為 km/h（wttr）",
            "openweather_error": owm_err,
        }
    except Exception as e:  # noqa: BLE001
        return {
            "tool": "weather",
            "ok": False,
            "location": loc,
            "error": str(e),
            "openweather_error": owm_err,
        }


def tool_agri_search(query: str, limit: int = 6) -> dict[str, Any]:
    """Google News RSS for agricultural guidance (no paid SERP)."""
    q = urllib.parse.quote(f"{query} 農業 OR 作物 OR 病蟲害")
    url = (
        "https://news.google.com/rss/search?"
        f"q={q}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    )
    try:
        raw = _http_get(url)
        root = ET.fromstring(raw)
        items = []
        for item in root.findall(".//item")[:limit]:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            if title:
                items.append({"title": title, "url": link})
        return {"tool": "agri_search", "ok": True, "items": items}
    except Exception as e:  # noqa: BLE001
        return {"tool": "agri_search", "ok": False, "items": [], "error": str(e)}


def _guess_location(question: str) -> str:
    # simple TW place names
    places = [
        "台北",
        "臺北",
        "新北",
        "桃園",
        "台中",
        "臺中",
        "台南",
        "臺南",
        "高雄",
        "宜蘭",
        "花蓮",
        "台東",
        "臺東",
        "屏東",
        "南投",
        "雲林",
        "嘉義",
        "彰化",
        "苗栗",
        "新竹",
        "基隆",
        "澎湖",
        "金門",
        "馬祖",
    ]
    for p in places:
        if p in question:
            return p.replace("臺", "台")
    # English city-ish
    m = re.search(
        r"\b(in|at)\s+([A-Za-z][A-Za-z\s]{1,30})\b", question, re.I
    )
    if m:
        return m.group(2).strip()
    return "台北"


def _extract_text(message: dict) -> str:
    content = (message.get("content") or "").strip()
    reason = (message.get("reasoning_content") or "").strip()
    return content or reason or ""


def _chat_qwen(system: str, user: str, max_tokens: int = 1000) -> str:
    payload = {
        "model": config.QWEN_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.3,
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
    choice = (raw.get("choices") or [{}])[0]
    return _extract_text(choice.get("message") or {})


def _parse_json(text: str) -> dict:
    text = (text or "").strip()
    text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.I)
    if "```" in text:
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if m:
            text = m.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        return json.loads(text[start : end + 1])
    raise ValueError("no json")


def plan_tools(question: str) -> dict[str, Any]:
    """Decide which tools to call."""
    system = (
        "你是農業助理的工具規劃器。只輸出 JSON：\n"
        '{"tools":["weather","crop_calendar","agri_search"],'
        '"location":"城市名或空","notes_zh":"一句"}\n'
        "依問題勾選需要的 tools（可多選）。有天氣/降雨/溫度→weather；"
        "何時種/收成→crop_calendar；病蟲害/防治/黃葉→agri_search+crop_calendar。"
        "不要思考過程。"
    )
    try:
        raw = _chat_qwen(system, question, max_tokens=200)
        data = _parse_json(raw)
        tools = data.get("tools") or []
        if not isinstance(tools, list):
            tools = []
        allowed = {"weather", "crop_calendar", "agri_search"}
        tools = [t for t in tools if t in allowed]
        if not tools:
            tools = ["crop_calendar", "agri_search"]
        loc = (data.get("location") or "").strip() or _guess_location(question)
        return {"tools": tools, "location": loc, "notes_zh": data.get("notes_zh") or ""}
    except Exception:  # noqa: BLE001
        q = question.lower()
        tools = []
        if any(k in question for k in ("天氣", "雨", "溫度", "weather", "下雨")):
            tools.append("weather")
        if any(k in question for k in ("種", "收", "曆", "何時", "plant", "harvest")):
            tools.append("crop_calendar")
        if any(k in question for k in ("病", "蟲", "黃葉", "pest", "蚜", "黴", "防治")):
            tools.extend(["agri_search", "crop_calendar"])
        if not tools:
            tools = ["crop_calendar", "agri_search"]
        return {
            "tools": list(dict.fromkeys(tools)),
            "location": _guess_location(question),
            "notes_zh": "規則後備選工具",
        }


def ask(question: str) -> dict[str, Any]:
    question = (question or "").strip()
    if not question:
        raise ValueError("empty question")

    plan = plan_tools(question)
    tool_results: list[dict] = []
    for t in plan["tools"]:
        if t == "weather":
            tool_results.append(tool_weather(plan.get("location") or "台北"))
        elif t == "crop_calendar":
            tool_results.append(tool_crop_calendar(question))
        elif t == "agri_search":
            tool_results.append(tool_agri_search(question))

    system = (
        "你是 CATCH 農業客戶助理（繁體中文）。根據工具結果給出務實、可執行建議。"
        "這是一般資訊，不是法定農藥處方；用藥須遵循標示與當地法規。"
        "結構：1) 簡答 2) 依據（天氣/曆/資料）3) 注意事項。勿編造未提供的數據。"
    )
    user = (
        f"問題：{question}\n"
        f"規劃：{json.dumps(plan, ensure_ascii=False)}\n"
        f"工具結果：{json.dumps(tool_results, ensure_ascii=False)[:9000]}\n"
    )
    answer = _chat_qwen(system, user, max_tokens=900).strip()

    return {
        "question": question,
        "plan": plan,
        "tools": tool_results,
        "answer_zh": answer,
        "disclaimer_zh": "一般栽培資訊，非現場診斷或用藥處方；重大損失請洽農改場／技師。",
    }


def list_crops() -> list[str]:
    return [c["crop"] for c in CROP_CALENDAR]


def sample_questions() -> list[str]:
    return [
        "台北今天適合噴藥或下田嗎？天氣如何？",
        "番茄葉子發黃可能是什麼原因？",
        "一期水稻大概何時插秧與收割？",
        "雲林種玉米要注意什麼病蟲害？",
        "芒果炭疽病如何預防（一般建議）？",
    ]
