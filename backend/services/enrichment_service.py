import re
import json
from backend.core.config import async_client, logger
from backend.core.models import OCRResponse
from backend.services.search_service import google_search
from backend.services.scraping_service import scrape_jina
from backend.services.ocr_service import englishify_fields

async def run_waterfall_enrichment(ocr_data: dict):
    logger.info("Starting Waterfall Enrichment (Step 2)...")
    
    company_q = ocr_data.get('company', '')
    location_q = ocr_data.get('location', '')
    email_q = ocr_data.get('email', '')
    website_q = ocr_data.get('website', '')

    # --- Phase 1: Identity Resolution ---
    official_url = ""
    
    # A: Direct
    if website_q and website_q.startswith("http"):
        official_url = website_q
    
    # B: Email Domain
    if not official_url and email_q and "@" in email_q:
        domain = email_q.split("@")[-1].strip()
        generic = ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'rediffmail.com', 'aol.com', 'icloud.com', 'protonmail.com', 'mail.com', 'ymail.com', 'live.com']
        if domain and domain.lower() not in generic:
            official_url = f"https://www.{domain}"
            
    # C: Google CSE
    if not official_url and company_q:
        items = await google_search(f"{company_q} {location_q} official website", 5)
        for item in items:
            link = item.get("link", "")
            if not any(x in link.lower() for x in ['zauba', 'tofler', 'justdial', 'indiamart', 'tradeindia', 'facebook.com', 'instagram.com', 'linkedin.com', 'twitter.com', 'youtube.com']):
                official_url = link
                break
        if not official_url and items:
            official_url = items[0].get("link", "")

    # --- Phase 2: Scraping ---
    official_markdown = await scrape_jina(official_url) if official_url else ""
    
    zauba_url = ""
    zauba_markdown = ""
    if company_q:
        zauba_items = await google_search(f"{company_q} {location_q} site:zaubacorp.com OR site:tofler.in", 2)
        if zauba_items:
            zauba_url = zauba_items[0].get("link", "")
            if zauba_url:
                zauba_markdown = await scrape_jina(zauba_url)

    # --- Phase 3: Social Links Parsing ---
    social_pattern = re.compile(
        r'https?://(?:www\.)?'
        r'(?:instagram\.com/[\w.\-]+|facebook\.com/(?:pages/)?[\w.\-/]+|fb\.com/[\w.\-]+|linkedin\.com/(?:company|in|school|showcase)/[\w.\-]+|twitter\.com/[\w.\-]+|x\.com/[\w.\-]+|youtube\.com/(?:@|channel/|c/|user/)[\w.\-]+|youtube\.com/[\w.\-]+|pinterest\.com/[\w.\-]+|wa\.me/[\w.\-+]+|api\.whatsapp\.com/send\?phone=[\w.\-+]+|t\.me/[\w.\-]+|threads\.net/@[\w.\-]+)',
        re.IGNORECASE
    )
    
    found_socials = set()
    if official_markdown:
        matches = social_pattern.findall(official_markdown)
        for m in matches:
            cleaned = m.split("?")[0].rstrip("/")
            if not any(x in cleaned.lower() for x in ['/p/', '/reel/', '/status/', '/posts/', '/video/']):
                found_socials.add(cleaned)
    
    # Backup Search for Socials
    if not found_socials and company_q:
        social_items = await google_search(f"{company_q} {location_q} Instagram Facebook LinkedIn", 6)
        for item in social_items:
            link = item.get('link', '')
            if any(x in link.lower() for x in ['instagram.com', 'facebook.com', 'linkedin.com', 'twitter.com', 'youtube.com']):
                cleaned = link.split("?")[0].rstrip("/")
                if not any(x in cleaned.lower() for x in ['/p/', '/reel/', '/status/', '/posts/', '/video/']):
                    found_socials.add(cleaned)

    social_links_str = "\n".join(sorted(found_socials))
    
    # --- Phase 4: GPT-4o Synthesis ---
    combined_search_context = f"""
    1. WEB: {official_url}
    2. SOCIALS: {social_links_str}
    3. LEGAL URL: {zauba_url}
    4. WEB CONTENT: {official_markdown[:15000]}
    5. LEGAL CONTENT: {zauba_markdown[:5000]}
    """
    
    extraction_prompt = f"""
    INVESTIGATION REPORT (from the web):
    {combined_search_context}

    ORIGINAL BUSINESS CARD DATA (already OCR'd and converted to English):
    {json.dumps(ocr_data, ensure_ascii=False)}

    Produce the final structured record.

    LANGUAGE: every value must be English / Latin script. If any input value is in
    Devanagari or another Indic script, transliterate names and translate descriptive
    text. Never output non-Latin script.

    TRUST THE CARD for these fields — copy them through unchanged from the card data
    above, only correcting obvious OCR typos. Do NOT replace them with values found
    on the web:
      company, name, title, phone, email, address, location

    FIELD DEFINITIONS — put each value in the correct field, never shift them:
      company             : firm/business name only, never a person's name.
      name                : the card holder's personal name only, never the firm name.
      title               : that person's designation (Proprietor, Director, Partner...).
      phone               : phone numbers only, comma-separated if several.
      email               : email addresses only (must contain '@').
      website             : the company's official website URL only.
      address             : full street address.
      location            : city and/or state only — a short place name, not the address.
      industry            : sector, e.g. "Jewellery", "Jewellery Retail", "Manufacturing".
                            A short category — never a company name, never a list of services.
      services            : the products/services offered, comma-separated.
      company_size        : employee count or range, digits/ranges only.
      founded_year        : 4-digit year only, e.g. "1998". Empty if unknown.
      registration_status : GST / CIN / registration state, e.g. "Active", "GST Registered".
      social_media        : newline-separated profile URLs only, no other text.
      validation_source   : the single best URL that verifies this company exists.
      is_validated        : true only if a credible source confirms the company.
      about_the_company   : 1-2 sentence description in English.
      trust_score         : integer 0-10 as a string.
      key_people          : leadership found on the web (name / role / contact each).
      slogan              : the card's tagline if present.

    If a value is unknown, return an empty string — never invent one, and never put a
    placeholder or another field's value in its place.
    """

    completion = await async_client.beta.chat.completions.parse(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a precise JSON extractor and verification agent for Indian "
                    "business cards. You always output English/Latin script, you keep each "
                    "value strictly in its own field, and you never fabricate data."
                )
            },
            {"role": "user", "content": extraction_prompt}
        ],
        response_format=OCRResponse,
        temperature=0.0
    )

    final_data = completion.choices[0].message.parsed.model_dump()

    # Final guard: enforce Latin script on every text field that reaches the sheet,
    # so nothing in Devanagari can slip into a column regardless of model behaviour.
    final_data = await englishify_fields(final_data, [
        'company', 'name', 'title', 'address', 'location', 'industry',
        'services', 'registration_status', 'about_the_company', 'slogan'
    ])

    for person in final_data.get('key_people') or []:
        if isinstance(person, dict):
            await englishify_fields(person, ['name', 'role'])

    logger.info("Waterfall Enrichment Complete.")
    return final_data
