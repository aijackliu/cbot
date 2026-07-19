import os
from pathlib import Path

# Load local .env if present (do not commit secrets)
_ENV = Path(__file__).resolve().parent.parent / ".env"
if _ENV.is_file():
    for line in _ENV.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v

# Remote demo stack (Tailscale / LAN)
QWEN_URL = os.getenv(
    "QWEN_URL", "http://100.88.220.82:8080/v1/chat/completions"
)
QWEN_MODEL = os.getenv("QWEN_MODEL", "Qwen3.6-35B-A3B-MXFP4_MOE.gguf")
REMOTE_FASTAPI = os.getenv("REMOTE_FASTAPI", "http://100.88.220.82:9000")
REDIS_HOST = os.getenv("REDIS_HOST", "100.88.220.82")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
PG_HOST = os.getenv("PG_HOST", "100.88.220.82")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASSWORD = os.getenv("PG_PASSWORD", "postgres")
PG_DB = os.getenv("PG_DB", "catch_crm")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DB}",
)

# Google AI Studio / Gemini — receipt OCR + CS mic (no GPU)
GOOGLE_AI_API_KEY = os.getenv("GOOGLE_AI_API_KEY", "")
GEMINI_VISION_MODEL = os.getenv("GEMINI_VISION_MODEL", "gemini-2.0-flash")
GEMINI_AUDIO_MODEL = os.getenv("GEMINI_AUDIO_MODEL", "gemini-2.0-flash")
GEMINI_EMBED_MODEL = os.getenv("GEMINI_EMBED_MODEL", "text-embedding-004")
