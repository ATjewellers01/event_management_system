import os
import logging
from dotenv import load_dotenv
from openai import AsyncOpenAI

# Load environment variables
load_dotenv(override=True)

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
