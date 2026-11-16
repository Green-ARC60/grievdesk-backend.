import os
from datetime import timedelta


def _normalize_db_uri(raw_uri: str | None) -> str:
    if not raw_uri:
        return "sqlite:///grievdesk.db"
    uri = raw_uri.strip()
    if uri.startswith("postgres://"):
        uri = uri.replace("postgres://", "postgresql+psycopg2://", 1)
    elif uri.startswith("postgresql://") and not uri.startswith("postgresql+"):
        uri = uri.replace("postgresql://", "postgresql+psycopg2://", 1)
    return uri


class Config:
    SQLALCHEMY_DATABASE_URI = _normalize_db_uri(os.environ.get("DATABASE_URL"))
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 12 * 1024 * 1024  # hard ceiling for any request body

    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-secret-change-me")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=7)

    DEVELOPER_EMAIL = os.environ.get("DEVELOPER_EMAIL", "ayushcharchi7@gmail.com")
    DEVELOPER_APPROVAL_SECRET = os.environ.get("DEVELOPER_APPROVAL_SECRET", "grievdesk-dev-master-approval-key-2026")
    FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")
    BACKEND_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:5000")

    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    # Model names get deprecated regularly — keep it in .env, not hardcoded.
    GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-lite-latest")
    # Tried in order when the main model is overloaded (503), retired (404) or out of free quota (429).
    GEMINI_FALLBACK_MODELS = [m.strip() for m in os.environ.get("GEMINI_FALLBACK_MODELS", "gemini-3.5-flash-lite,gemini-3.1-flash-lite").split(",") if m.strip()]
    GEMINI_RETRIES_PER_MODEL = int(os.environ.get("GEMINI_RETRIES_PER_MODEL", "2"))
    GEMINI_TIMEOUT_SECONDS = int(os.environ.get("GEMINI_TIMEOUT_SECONDS", "15"))

    # ---- Voice input ----
    MAX_AUDIO_BYTES = 10 * 1024 * 1024        # voice notes are short, so keep the cap small
    AUDIO_DIR = os.environ.get("AUDIO_DIR")   # default: <project>/instance/audio, resolved at runtime

    # ---- Amenity booking rules (policy choices — change in .env, no code edit) ----
    SOCIETY_TIMEZONE = os.environ.get("SOCIETY_TIMEZONE", "Asia/Kolkata")  # "now" for booking rules
    MAX_BOOKING_HOURS = int(os.environ.get("MAX_BOOKING_HOURS", "4"))       # stops one booking blocking a facility all day
    MAX_BOOKING_DAYS_AHEAD = int(os.environ.get("MAX_BOOKING_DAYS_AHEAD", "30"))

    # ---- Housekeeping jobs (Step 7) ----
    ESCALATION_DAYS = int(os.environ.get("ESCALATION_DAYS", "5"))                 # untouched "new" complaint -> escalated
    DUPLICATE_WINDOW_HOURS = int(os.environ.get("DUPLICATE_WINDOW_HOURS", "48"))  # how far back "the same problem" looks
    CHAT_RETENTION_DAYS = int(os.environ.get("CHAT_RETENTION_DAYS", "7"))         # chat transcripts older than this are deleted
    ENABLE_SCHEDULER = os.environ.get("ENABLE_SCHEDULER", "false").strip().lower() in ("1", "true", "yes")

    # ---- Translate-on-read (Step 8) ----
    TRANSLATE_BATCH_ITEMS = int(os.environ.get("TRANSLATE_BATCH_ITEMS", "25"))     # texts sent to Gemini per call
    TRANSLATE_BATCH_CHARS = int(os.environ.get("TRANSLATE_BATCH_CHARS", "8000"))   # ...and a size cap per call
