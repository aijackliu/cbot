import os

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
PORT = int(os.getenv("PORT", "18721"))
