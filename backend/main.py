import os
import sys
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
import httpx

# Fix path to allow importing from 'backend'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.config import logger, FRONTEND_DIR, APPS_SCRIPT_URL, PUBLIC_BASE_URL
from backend.core.models import OCRRequest
from backend.services.ocr_service import extract_card_data
from backend.services.enrichment_service import run_waterfall_enrichment
from backend.utils.sheets import submit_to_sheets

app = FastAPI(title="Business Card OCR API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

@app.get("/api/config")
async def public_config():
    return {
        "appsScriptUrl": APPS_SCRIPT_URL,
        "publicBaseUrl": PUBLIC_BASE_URL,
    }

@app.post("/ocr")
async def perform_ocr(request: OCRRequest):
    try:
        # 1. OCR
        ocr_data = await extract_card_data(request.base64Image1, request.base64Image2)
        
        # 2. Enrichment
        final_data = await run_waterfall_enrichment(ocr_data)
        
        # 3. Stats & Score
        confidence_score = 0
        if final_data.get("is_validated"): confidence_score += 30
        if final_data.get("website"): confidence_score += 20
        try:
             trust_val = int(str(final_data.get("trust_score", "0")).split('/')[0].strip())
             confidence_score += (trust_val * 2) 
        except: pass
        if final_data.get("social_media"): confidence_score += 10
        
        # 4. Sheet Submission
        payload = {
            "action": "save_event_card" if request.eventMode else "save",
            "extractedData": final_data,
            "confidence_score": confidence_score,
            "photo1Base64": request.base64Image1, 
            "photo2Base64": request.base64Image2 or "",
            "eventInfo": request.eventInfo
        }
        
        # Log the final enriched data to terminal
        import json
        logger.info(f"FINAL DATA TO SAVE:\n{json.dumps(final_data, indent=4)}")
        
        submit_to_sheets(payload)
        
        return {"success": True, "data": final_data, "confidence_score": confidence_score}

    except Exception as e:
        logger.error(f"Global Endpoint Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/get-events")
async def get_events_list():
    try:
        resp = submit_to_sheets({"action": "get_event_list"})
        if resp and resp.status_code == 200:
            return resp.json()
        return {"success": False, "message": "Failed to fetch event list"}
    except Exception as e:
        return {"success": False, "message": str(e)}

@app.get("/get-event/{event_id}")
async def get_event_by_id(event_id: str):
    try:
        resp = submit_to_sheets({"action": "get_event", "eventId": event_id})
        if resp and resp.status_code == 200:
            return resp.json()
        return {"success": False, "message": "Failed to fetch event details"}
    except Exception as e:
        logger.error(f"Get Event Error: {e}")
        return {"success": False, "message": str(e)}

@app.post("/save-event")
async def save_event(request: dict):
    try:
        # Request is expected to contain 'eventData'
        payload = {
            "action": "save_event",
            "eventData": request.get("eventData")
        }
        
        # Submit to Sheets via existing utility
        resp = submit_to_sheets(payload)
        
        if resp and resp.status_code == 200:
            try:
                sheet_res = resp.json()
                return {"success": True, **sheet_res}
            except:
                return {"success": True, "message": "Event saved"}
        else:
            raise Exception("Failed to save to Google Sheets via Apps Script")

    except Exception as e:
        logger.error(f"Save Event Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/submit-lead")
async def submit_lead(request: dict):
    try:
        # Request contains 'leadData'
        payload = {
            "action": "save_lead",
            "leadData": request.get("leadData")
        }
        
        resp = submit_to_sheets(payload)
        
        if resp and resp.status_code == 200:
            return {"success": True, "message": "Lead submitted successfully"}
        else:
            raise Exception("Failed to save lead to Google Sheets")

    except Exception as e:
        logger.error(f"Submit Lead Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/get-event-data")
async def get_event_specific_data(request: dict):
    try:
        payload = {
            "action": "get_event_data",
            "eventId": request.get("eventId"),
            "eventName": request.get("eventName")
        }
        resp = submit_to_sheets(payload)
        if resp and resp.status_code == 200:
            return resp.json()
        return {"success": False, "message": "Failed to fetch event data"}
    except Exception as e:
        logger.error(f"Get Event Data Error: {e}")
        return {"success": False, "message": str(e)}

@app.get("/get-company-profile")
async def get_company_profile():
    try:
        resp = submit_to_sheets({"action": "get_company_profile"})
        if resp and resp.status_code == 200:
            return resp.json()
        return {"success": False, "message": "Failed to fetch profile"}
    except Exception as e:
        logger.error(f"Get Company Profile Error: {e}")
        return {"success": False, "message": str(e)}

@app.post("/save-company-profile")
async def save_company_profile(request: dict):
    try:
        payload = {
            "action": "save_company_profile",
            "profileData": request.get("profileData")
        }
        resp = submit_to_sheets(payload)
        if resp and resp.status_code == 200:
            return resp.json()
        return {"success": False, "message": "Failed to save profile"}
    except Exception as e:
        logger.error(f"Save Company Profile Error: {e}")
        return {"success": False, "message": str(e)}

@app.post("/submit-visitor-and-get-contact")
async def submit_visitor_and_get_contact(request: dict):
    try:
        payload = {
            "action": "save_visitor_and_get_contact",
            "visitorData": request
        }
        resp = submit_to_sheets(payload)
        if resp and resp.status_code == 200:
            return resp.json()
        return {"success": False, "message": "Failed to process visitor data"}
    except Exception as e:
        logger.error(f"Submit Visitor Error: {e}")
        return {"success": False, "message": str(e)}

@app.delete("/api/event/{event_id}")
async def delete_event(event_id: str):
    try:
        payload = {
            "action": "delete_event",
            "eventId": event_id
        }
        resp = submit_to_sheets(payload)
        if resp and resp.status_code == 200:
            return resp.json()
        return {"success": False, "message": "Failed to delete event"}
    except Exception as e:
        logger.error(f"Delete Event Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/visitor/{visitor_id}")
async def update_visitor(visitor_id: str, request: dict):
    try:
        payload = {
            "action": "update_visitor",
            "visitorId": visitor_id,
            "visitorData": request
        }
        resp = submit_to_sheets(payload)
        if resp and resp.status_code == 200:
            return resp.json()
        return {"success": False, "message": "Failed to update visitor"}
    except Exception as e:
        logger.error(f"Update Visitor Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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
    uvicorn.run(app, host="127.0.0.1", port=8000)