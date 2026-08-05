import os
import logging
from dotenv import load_dotenv
from openai import AsyncOpenAI

# Load backend/.env by absolute path. A bare load_dotenv() only finds it when the
# process happens to be started from inside backend/, which silently breaks
# scripts and tooling run from the repo root.
_ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
# override=False so a real environment variable wins over the file. That is the
# conventional precedence and it lets a value be overridden for a single run
# (e.g. PUBLIC_BASE_URL=<tunnel> when testing the QR flow from a phone) without
# editing .env.
load_dotenv(_ENV_PATH, override=False)

# API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID")

# Public-facing deployment URL — used to build links the browser/QR points to.
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")

if not OPENAI_API_KEY:
    raise ValueError("No OPENAI_API_KEY found in .env file.")

# --- Turso (libSQL) ---
# The application's only data store. Missing credentials are a hard failure at
# import: there is no fallback any more, so starting up "successfully" with no
# database would just produce mystery 500s on every request.
_raw_turso_url = (os.getenv("TURSO_DB_URL") or "").strip()
TURSO_AUTH_TOKEN = (os.getenv("TURSO_AUTH_TOKEN") or "").strip()

# The Turso dashboard shows some URLs as turso://, but the libsql client only
# accepts libsql:// or https://. Normalise so either form in .env works.
if _raw_turso_url.startswith("turso://"):
    TURSO_DB_URL = "libsql://" + _raw_turso_url[len("turso://"):]
else:
    TURSO_DB_URL = _raw_turso_url

TURSO_ENABLED = bool(TURSO_DB_URL and TURSO_AUTH_TOKEN)

if not TURSO_ENABLED:
    missing = [n for n, v in (("TURSO_DB_URL", TURSO_DB_URL),
                              ("TURSO_AUTH_TOKEN", TURSO_AUTH_TOKEN)) if not v]
    raise ValueError(
        f"Turso is the only data store but {' and '.join(missing)} "
        f"{'is' if len(missing) == 1 else 'are'} missing from backend/.env"
    )

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

logger.info("Data store: Turso (%s)", TURSO_DB_URL.split("//")[-1].split(".")[0])
