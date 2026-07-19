"""LAN defaults — override with env."""

from __future__ import annotations

import os

QWEN_URL = os.getenv(
    "QWEN_URL", "http://100.88.220.82:8080/v1/chat/completions"
)
QWEN_MODEL = os.getenv("QWEN_MODEL", "Qwen3.6-35B-A3B-MXFP4_MOE.gguf")
TOP_N = int(os.getenv("DIGEST_TOP_N", "5"))
LOOKBACK_HOURS = int(os.getenv("DIGEST_HOURS", "24"))
FETCH_WORKERS = int(os.getenv("DIGEST_WORKERS", "16"))
FETCH_TIMEOUT = float(os.getenv("DIGEST_TIMEOUT", "12"))
MAX_CANDIDATES_FOR_LLM = int(os.getenv("DIGEST_MAX_CANDIDATES", "40"))
