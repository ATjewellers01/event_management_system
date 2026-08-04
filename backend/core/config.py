import os
import logging
from dotenv import load_dotenv
from openai import AsyncOpenAI

# Load backend/.env by absolute path. A bare load_dotenv() only finds it when the
# process happens to be started from inside backend/, which silently breaks
# scripts and tooling run from the repo root.
_ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(_ENV_PATH, override=True)

# API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
APPS_SCRIPT_URL = os.getenv("APPS_SCRIPT_URL")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID")

# Public-facing deployment URL — used to build links the browser/QR points to.
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")

if not OPENAI_API_KEY:
    raise ValueError("No OPENAI_API_KEY found in .env file.")
if not APPS_SCRIPT_URL:
    raise ValueError("No APPS_SCRIPT_URL found in .env file.")

# --- Turso (libSQL) ---
# Optional. When both URL and token are present the app can read/write Turso;
# otherwise it silently stays on Google Sheets. Deliberately NOT a hard failure
# so a missing token can never take the live site down.
_raw_turso_url = (os.getenv("TURSO_DB_URL") or "").strip()
TURSO_AUTH_TOKEN = (os.getenv("TURSO_AUTH_TOKEN") or "").strip()

# The Turso dashboard shows some URLs as turso://, but the libsql client only
# accepts libsql:// or https://. Normalise so either form in .env works.
if _raw_turso_url.startswith("turso://"):
    TURSO_DB_URL = "libsql://" + _raw_turso_url[len("turso://"):]
else:
    TURSO_DB_URL = _raw_turso_url

TURSO_ENABLED = bool(TURSO_DB_URL and TURSO_AUTH_TOKEN)

# Read path: 'sheets' (default) or 'turso'. Lets us flip the source of truth
# without code changes, and roll straight back if Turso misbehaves.
DATA_SOURCE = (os.getenv("DATA_SOURCE") or "sheets").strip().lower()

# Cache TTL in seconds for sheet-backed reads. 0 disables caching entirely.
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS") or "60")

# Path Helpers
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")

# OpenAI Client
async_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# Logging Setup
def setup_logging():
    # Paths for log file
    log_file = os.path.join(BASE_DIR, "app.log")
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file, encoding='utf-8')
        ]
    )
    return logging.getLogger("BusinessCardReader")

logger = setup_logging()
logger.info("Logging initialized. Logs saved to: backend/app.log")

# Make the active data configuration obvious in the logs — silently reading from
# the wrong backend is the kind of bug that wastes hours.
logger.info(
    "Data config: source=%s | turso_enabled=%s | cache_ttl=%ss",
    DATA_SOURCE, TURSO_ENABLED, CACHE_TTL_SECONDS
)
if DATA_SOURCE == "turso" and not TURSO_ENABLED:
    logger.warning(
        "DATA_SOURCE=turso but Turso creds are incomplete "
        "(need TURSO_DB_URL and TURSO_AUTH_TOKEN) — falling back to Google Sheets."
    )
