"""
Gateway configuration.
"""
import os

# ──────────────────────────────────────────────
# JWT Auth
# ──────────────────────────────────────────────
JWT_SECRET = os.getenv("JWT_SECRET_KEY", "dev-secret-change-in-production")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7

# ──────────────────────────────────────────────
# PostgreSQL (gateway_db)
# ──────────────────────────────────────────────
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", 5432))
POSTGRES_USER = os.getenv("POSTGRES_USER", "emotion")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "emotion_dev")
GATEWAY_DB = os.getenv("GATEWAY_DB", "gateway_db")
GATEWAY_DB_URL = f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{GATEWAY_DB}"

# ──────────────────────────────────────────────
# Redis (for reading live streams)
# ──────────────────────────────────────────────
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}"

STREAM_LIVE_PREFIX = "stream:live:"

# ──────────────────────────────────────────────
# Internal service URLs
# ──────────────────────────────────────────────
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://orchestrator:8001")

# ──────────────────────────────────────────────
# CORS
# ──────────────────────────────────────────────
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")

# ──────────────────────────────────────────────
# Rate limiting
# ──────────────────────────────────────────────
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", 100))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", 60))

# ──────────────────────────────────────────────
# WebSocket
# ──────────────────────────────────────────────
WS_MAX_FRAME_SIZE = int(os.getenv("WS_MAX_FRAME_SIZE", 1_000_000))  # 1MB
WS_HEARTBEAT_INTERVAL = int(os.getenv("WS_HEARTBEAT_INTERVAL", 30))

# ──────────────────────────────────────────────
# Bcrypt
# ──────────────────────────────────────────────
BCRYPT_ROUNDS = int(os.getenv("BCRYPT_ROUNDS", 12))

# ──────────────────────────────────────────────
# Upload rate limiting
# ──────────────────────────────────────────────
UPLOAD_RATE_LIMIT = int(os.getenv("UPLOAD_RATE_LIMIT", 10))
UPLOAD_RATE_WINDOW_SECONDS = int(os.getenv("UPLOAD_RATE_WINDOW_SECONDS", 3600))