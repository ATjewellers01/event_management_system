"""Card image storage on Cloudinary.

Business card photos arrive as base64 from the browser. We upload them once,
letting Cloudinary do the resize and re-encode, and store ONLY the optimised
derivative — the original is discarded so nothing large is retained.

Format is WebP, not AVIF. AVIF is smaller, but GPT-4o vision rejects it
outright (supported: png, jpeg, gif, webp), so an AVIF-only store would break
any future re-OCR of a saved card. Measured on a sample card:
    AVIF 43KB (unreadable by OCR) / WebP 49KB (readable) / JPEG 99KB
WebP gives ~50% off JPEG while staying OCR-compatible.
"""

import asyncio
import base64
import os
import uuid
from typing import Optional

import cloudinary
import cloudinary.uploader

from backend.core.config import logger

CLOUD_NAME = (os.getenv("CLOUDINARY_CLOUD_NAME") or "").strip()
API_KEY = (os.getenv("CLOUDINARY_API_KEY") or "").strip()
API_SECRET = (os.getenv("CLOUDINARY_API_SECRET") or "").strip()

CLOUDINARY_ENABLED = bool(CLOUD_NAME and API_KEY and API_SECRET)

# All assets for this project live under one folder.
FOLDER = "event-hub/cards"

# Cap the long edge. Business cards are legible well below this, and it keeps
# both the stored bytes and any future OCR upload small.
MAX_EDGE = 1600

if CLOUDINARY_ENABLED:
    cloudinary.config(
        cloud_name=CLOUD_NAME, api_key=API_KEY, api_secret=API_SECRET, secure=True
    )
    logger.info("Cloudinary configured (cloud=%s, folder=%s)", CLOUD_NAME, FOLDER)
else:
    logger.warning(
        "Cloudinary not configured — card images will not be stored. "
        "Set CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET."
    )


def _strip_data_url(b64: str) -> str:
    """Accept either a bare base64 string or a full data: URL."""
    if not b64:
        return ""
    if b64.startswith("data:"):
        _, _, payload = b64.partition(",")
        return payload
    return b64


def upload_card_image(base64_image: str, event_id: str, side: str) -> Optional[str]:
    """Upload one card side and return its optimised WebP URL, or None.

    Returns None rather than raising: a failed image upload must not lose the
    scanned card data, which is the valuable part.
    """
    payload = _strip_data_url(base64_image)
    if not payload:
        return None
    if not CLOUDINARY_ENABLED:
        logger.warning("Skipping image upload — Cloudinary is not configured.")
        return None

    try:
        raw = base64.b64decode(payload)
    except Exception as e:
        logger.error("Card image is not valid base64: %s", e)
        return None

    public_id = f"{(event_id or 'no-event').strip() or 'no-event'}_{side}_{uuid.uuid4().hex[:12]}"

    try:
        result = cloudinary.uploader.upload(
            raw,
            folder=FOLDER,
            public_id=public_id,
            resource_type="image",
            # Store the optimised derivative only, and drop the original so we
            # are not paying to keep a large file we never serve.
            eager=[{
                "width": MAX_EDGE, "crop": "limit",
                "fetch_format": "webp", "quality": "auto:good",
            }],
            eager_async=False,
            format="webp",
            transformation=[{
                "width": MAX_EDGE, "crop": "limit",
                "quality": "auto:good",
            }],
            overwrite=True,
            invalidate=True,
        )
        url = result.get("secure_url") or result.get("url")
        logger.info(
            "Card image stored: %s (%s bytes, %s)",
            public_id, result.get("bytes"), result.get("format"),
        )
        return url
    except Exception as e:
        logger.error("Cloudinary upload failed for %s: %s: %s", public_id, type(e).__name__, e)
        return None


async def upload_card_images_async(photo1_b64: str, photo2_b64: str,
                                   event_id: str) -> tuple:
    """Upload both sides concurrently. Returns (url1, url2), either may be None."""
    if not CLOUDINARY_ENABLED:
        return (None, None)

    tasks = [
        asyncio.to_thread(upload_card_image, photo1_b64, event_id, "front"),
        asyncio.to_thread(upload_card_image, photo2_b64, event_id, "back"),
    ]
    url1, url2 = await asyncio.gather(*tasks, return_exceptions=True)
    if isinstance(url1, Exception):
        logger.error("Front image upload raised: %s", url1)
        url1 = None
    if isinstance(url2, Exception):
        logger.error("Back image upload raised: %s", url2)
        url2 = None
    return (url1, url2)


def status() -> dict:
    return {
        "enabled": CLOUDINARY_ENABLED,
        "cloud_name": CLOUD_NAME if CLOUDINARY_ENABLED else None,
        "folder": FOLDER,
        "format": "webp",
        "max_edge": MAX_EDGE,
    }
