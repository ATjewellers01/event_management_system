"""Event Hub API.

Data lives in Turso; card images live in Cloudinary. Google Sheets, Apps Script
and Google Drive are no longer part of any request path — that stack was the
source of the 3-40s page loads and the intermittent "stream not found" /
"unable to open the file" failures.

No response cache: Turso answers in tens of milliseconds, so a TTL cache would
save almost nothing while adding staleness and invalidation complexity.
"""

import os
import sys
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
import httpx

# Fix path to allow importing from 'backend'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.config import logger, FRONTEND_DIR, PUBLIC_BASE_URL
from backend.core.models import OCRRequest
from backend.services.ocr_service import extract_card_data
from backend.services.enrichment_service import run_waterfall_enrichment
from backend.utils import repository as repo
from backend.utils import images
from backend.utils.turso import check_connection_async, init_schema

app = FastAPI(title="Event Hub API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup():
    """Fail loudly at boot if the database is unreachable.

    Turso is now the only data store, so a broken connection means a broken app.
    Better to see it in the logs at startup than as mystery 500s later.
    """
    status = await check_connection_async()
    if status.get("ok"):
        logger.info("Turso connected. Tables: %s", ", ".join(status.get("tables", [])))
    else:
        logger.error("TURSO UNAVAILABLE AT STARTUP — %s", status.get("reason"))
    logger.info("Image storage: %s", images.status())


@app.get("/api/config")
async def public_config():
    # appsScriptUrl is intentionally gone: nothing in the frontend should call
    # Apps Script any more.
    return {"publicBaseUrl": PUBLIC_BASE_URL}


@app.get("/api/health")
async def health():
    db = await check_connection_async()
    return {
        "database": db,
        "images": images.status(),
    }


def _row_id(raw: str):
    """Parse the row id from a path param.

    The frontend historically sent '<index>_<timestamp>'; it now sends the real
    primary key. Accept both so an older cached page cannot 500.
    """
    token = str(raw).split("_")[0]
    try:
        return int(token)
    except (TypeError, ValueError):
        return None


@app.post("/ocr")
async def perform_ocr(request: OCRRequest):
    try:
        # 1. OCR
        ocr_data = await extract_card_data(request.base64Image1, request.base64Image2)

        # 2. Enrichment
        final_data = await run_waterfall_enrichment(ocr_data)

        # 3. Stats & Score
        confidence_score = 0
        if final_data.get("is_validated"):
            confidence_score += 30
        if final_data.get("website"):
            confidence_score += 20
        try:
            trust_val = int(str(final_data.get("trust_score", "0")).split('/')[0].strip())
            confidence_score += (trust_val * 2)
        except Exception:
            pass
        if final_data.get("social_media"):
            confidence_score += 10

        event_info = request.eventInfo or {}

        # 4. Store the images (optimised WebP) and the row.
        photo1_url, photo2_url = await images.upload_card_images_async(
            request.base64Image1, request.base64Image2 or "", event_info.get("id") or ""
        )

        result = await repo.run(
            repo.save_event_card, final_data, photo1_url or "", photo2_url or "", event_info
        )
        saved = bool(result.get("success"))
        if not saved:
            logger.error("Card OCR succeeded but the DB write FAILED: %s", result.get("message"))

        return {
            "success": True,
            "saved": saved,
            "message": "Card saved." if saved else f"Card scanned but saving failed: {result.get('message')}",
            "imagesStored": bool(photo1_url or photo2_url),
            "data": final_data,
            "confidence_score": confidence_score,
        }

    except Exception as e:
        logger.error(f"OCR Endpoint Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/get-events")
async def get_events_list():
    return await repo.run(repo.get_event_list)


@app.get("/get-event/{event_id}")
async def get_event_by_id(event_id: str):
    return await repo.run(repo.get_event_by_id, event_id)


@app.post("/save-event")
async def save_event(request: dict):
    result = await repo.run(repo.save_event, request.get("eventData") or {})
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("message", "Failed to save event"))
    return result


@app.post("/submit-lead")
async def submit_lead(request: dict):
    """Legacy alias — the QR form now posts to /submit-visitor-and-get-contact."""
    result = await repo.run(repo.save_visitor, request.get("leadData") or {})
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("message", "Failed to save lead"))
    return {"success": True, "message": "Lead submitted successfully"}


@app.post("/get-event-data")
async def get_event_specific_data(request: dict):
    return await repo.run(
        repo.get_event_specific_data,
        request.get("eventId") or "",
        request.get("eventName") or "",
    )


@app.post("/read-sheet")
async def read_sheet(request: dict):
    """Whole-table read for the Leads Database page.

    Still named 'sheet' because the frontend calls it that; it reads Turso.
    """
    return await repo.run(repo.read_table, request.get("sheetName") or "")


@app.get("/get-company-profile")
async def get_company_profile():
    return await repo.run(repo.get_company_profile)


@app.post("/save-company-profile")
async def save_company_profile(request: dict):
    return await repo.run(repo.save_company_profile, request.get("profileData") or {})


@app.post("/submit-visitor-and-get-contact")
async def submit_visitor_and_get_contact(request: dict):
    return await repo.run(repo.save_visitor, request)


@app.post("/api/event/delete/{event_id}")
async def delete_event(event_id: str):
    result = await repo.run(repo.delete_event, event_id)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("message", "Failed to delete event"))
    return result


@app.post("/api/visitor/update/{visitor_id}")
async def update_visitor(visitor_id: str, request: dict):
    row_id = _row_id(visitor_id)
    if row_id is None:
        raise HTTPException(status_code=400, detail=f"Invalid visitor id '{visitor_id}'")
    return await repo.run(repo.update_visitor, row_id, request)


@app.post("/api/card/update/{card_id}")
async def update_card(card_id: str, request: dict):
    row_id = _row_id(card_id)
    if row_id is None:
        raise HTTPException(status_code=400, detail=f"Invalid card id '{card_id}'")
    return await repo.run(repo.update_card, row_id, request)


@app.get("/proxy-image")
async def proxy_image(url: str):
    if not url:
        raise HTTPException(status_code=400, detail="No URL provided")
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, follow_redirects=True)
            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail="Failed to fetch image")
            
            return Response(content=resp.content, media_type=resp.headers.get("content-type", "image/png"))
    except Exception as e:
        logger.error(f"Proxy error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- FRONTEND ASSETS ---
from fastapi.staticfiles import StaticFiles
# Mount main frontend assets
app.mount("/assets", StaticFiles(directory=FRONTEND_DIR), name="assets")

# Mount Scanner Build (React)
# Use dynamic path for cloud compatibility
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCANNER_DIST = os.path.join(PROJECT_ROOT, "BotivateScanner", "dist")

if os.path.exists(SCANNER_DIST):
    app.mount("/scanner", StaticFiles(directory=SCANNER_DIST, html=True), name="scanner")
else:
    logger.warning(f"Scanner Dist directory not found at {SCANNER_DIST}")

@app.get("/")
async def read_index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

@app.get("/leads.html")
@app.get("/leads")
async def read_leads():
    return FileResponse(os.path.join(FRONTEND_DIR, "leads.html"))

@app.get("/visitor-form/{event_id}")
async def serve_visitor_form(event_id: str):
    return FileResponse(os.path.join(FRONTEND_DIR, "visitor-form", "index.html"))

# Map individual files for root level access if needed by the index.html
@app.get("/style.css")
async def read_style():
    return FileResponse(os.path.join(FRONTEND_DIR, "style.css"))

@app.get("/worker.js")
async def read_worker():
    return FileResponse(os.path.join(FRONTEND_DIR, "worker.js"))

@app.get("/vcard-direct")
async def vcard_direct(name: str, org: str, phone: str, email: str, title: str = "", addr: str = "", web: str = "", first: str = "", last: str = ""):
    vcard_raw = f"""BEGIN:VCARD
VERSION:3.0
FN:{name}
N:{last};{first};;;
ORG:{org}
TITLE:{title}
TEL;TYPE=WORK,VOICE:+91{phone}
EMAIL;TYPE=PREF,INTERNET:{email}
ADR;TYPE=WORK:;;{addr};;;;
URL:{web}
END:VCARD"""
    safe_name = name.replace(" ", "_").replace("(", "").replace(")", "")
    return Response(
        content=vcard_raw,
        media_type="text/vcard",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}_{int(os.path.getmtime(__file__))}.vcf"',
            "Content-Type": "text/vcard; charset=utf-8"
        }
    )

if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*80)
    print("🚀 TARGET SERVER STARTING - V2.0.0 (NEW_UPDATE) 🚀")
    print("SERVICING SCANNER FROM: " + SCANNER_DIST)
    print("="*80 + "\n")
