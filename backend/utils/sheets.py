import asyncio

import requests
from backend.core.config import APPS_SCRIPT_URL, logger

# Apps Script responses are served via a redirect to script.googleusercontent.com
# and that second hop is routinely slow. 15s was too tight — a legitimate call
# that takes 20s was being reported as a failure.
SHEETS_TIMEOUT_SECONDS = 45


def submit_to_sheets(payload: dict):
    """Blocking POST to the Apps Script web app.

    Kept synchronous because non-async callers (e.g. migration scripts) use it.
    Async request handlers should call `submit_to_sheets_async` instead.
    """
    action = payload.get("action", "?")
    logger.info("Submitting to Google Sheets (action=%s)...", action)
    try:
        resp = requests.post(APPS_SCRIPT_URL, json=payload, timeout=SHEETS_TIMEOUT_SECONDS)
        logger.info("Sheets response: %s (action=%s)", resp.status_code, action)
        return resp
    except Exception as e:
        logger.error("Sheets submission error (action=%s): %s", action, e)
        return None


async def submit_to_sheets_async(payload: dict):
    """Run the blocking POST in a worker thread.

    `requests` is synchronous, so calling it directly from an async handler
    blocks the whole event loop for the duration — with Apps Script that is
    seconds to tens of seconds, during which the app serves nothing else.
    """
    return await asyncio.to_thread(submit_to_sheets, payload)


def sheets_json(resp):
    """Extract a JSON body from an Apps Script response, or None."""
    if resp is None or resp.status_code != 200:
        return None
    try:
        return resp.json()
    except ValueError:
        logger.error("Sheets returned non-JSON body (status %s)", resp.status_code)
        return None
