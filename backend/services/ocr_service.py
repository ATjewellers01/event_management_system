from backend.core.config import async_client, logger
from backend.core.models import BasicOCR
from backend.services import llm_client
import re

# Devanagari (Hindi/Marathi), Gujarati, Bengali, Tamil, Telugu, Kannada,
# Malayalam, Gurmukhi (Punjabi), Odia — business cards at Indian jewellery
# trade shows show up in all of these, not just Hindi.
NON_LATIN_SCRIPT = re.compile(
    r'[ऀ-ॿ'   # Devanagari
    r'઀-૿'    # Gujarati
    r'ঀ-৿'    # Bengali
    r'஀-௿'    # Tamil
    r'ఀ-౿'    # Telugu
    r'ಀ-೿'    # Kannada
    r'ഀ-ൿ'    # Malayalam
    r'਀-੿'    # Gurmukhi
    r'଀-୿'    # Odia
    r']'
)

def has_non_latin_text(text: str) -> bool:
    if not text:
        return False
    return bool(NON_LATIN_SCRIPT.search(str(text)))

async def transliterate_to_english(text: str) -> str:
    """Convert an Indic-script field value to Latin script.

    Proper nouns (company/person names) are transliterated so they stay
    recognisable — 'श्री जिनकुशल ज्वेलर्स' should become 'Shree Jinkushal
    Jewellers', not a literal meaning-translation. Descriptive text is
    translated normally.
    """
    if not has_non_latin_text(text):
        return text

    try:
        # Routed through llm_client: Groq's free tier handles this fine and it is
        # ~11% of the per-scan LLM cost. Falls back to OpenAI automatically.
        converted = await llm_client.text([
            {
                "role": "system",
                "content": (
                    "You convert Indian-language business card text to English. "
                    "For names of companies, people, and places: TRANSLITERATE to "
                    "Latin script so pronunciation is preserved (e.g. 'ज्वेलर्स' -> "
                    "'Jewellers', 'सुचित बोहरा' -> 'Suchit Bohra'). "
                    "For descriptive phrases: translate the meaning. "
                    "Keep digits, emails, URLs and phone numbers exactly as-is. "
                    "Return ONLY the converted text with no quotes, labels, or commentary."
                )
            },
            {"role": "user", "content": str(text)}
        ])
        logger.info(f"Transliterated: '{text}' -> '{converted}'")
        return converted or text
    except Exception as e:
        logger.warning(f"Transliteration failed for '{text}': {str(e)}")
        return text

async def englishify_fields(data: dict, fields: list) -> dict:
    """Force the given fields to Latin script, in place."""
    for field in fields:
        value = data.get(field)
        if isinstance(value, str) and has_non_latin_text(value):
            data[field] = await transliterate_to_english(value)
    return data

async def extract_card_data(base64_img1: str, base64_img2: str = None):
    logger.info("Starting OpenAI Vision OCR (Step 1)...")

    image_content = []

    # Process Image 1
    img1 = base64_img1 if base64_img1.startswith("data:image") else f"data:image/jpeg;base64,{base64_img1}"
    image_content.append({"type": "image_url", "image_url": {"url": img1}})

    # Process Image 2
    if base64_img2:
        img2 = base64_img2 if base64_img2.startswith("data:image") else f"data:image/jpeg;base64,{base64_img2}"
        image_content.append({"type": "image_url", "image_url": {"url": img2}})

    # User Instructions
    image_content.append({
        "type": "text",
        "text": """
        Extract the details from this business card (both sides if two images are given).
        Read stylized, rotated, or inverted text carefully.

        OUTPUT LANGUAGE: Every value must be in English / Latin script. If the card
        is in Hindi, Gujarati, Bengali, Tamil, Marathi or any other Indic script,
        transliterate names (company, person, city) into Latin script and translate
        descriptive text. Never return Devanagari or any non-Latin script.

        Put each value in the CORRECT field — do not mix them up:
        - company : the business/firm name only (e.g. "Arham Jewellers"). Never a person's name.
        - name    : the individual person's name only (e.g. "Palash Tatiya"). Never the firm name.
        - title   : that person's job title/designation (e.g. "Proprietor", "Director", "Partner").
                    A designation is NOT a name and NOT an industry.
        - phone   : phone/mobile numbers only. Multiple numbers -> comma-separated. Digits,
                    +, spaces and commas only. Never put an email or address here.
        - email   : email addresses only (must contain '@'). Never a website.
        - website : website/domain only (e.g. "www.example.com"). Never an email.
        - address : the full street address (building, street, area, landmark, pincode).
        - location: ONLY the city and/or state (e.g. "Raipur, Chhattisgarh"). This is a
                    short place name, NOT the full address, NOT a company name.
        - slogan  : tagline/motto if present (e.g. "Purity You Can Trust").

        If a field is genuinely not on the card, return an empty string "" for it.
        Never guess, never copy another field's value as a placeholder.
        """
    })

    ocr_response = await async_client.beta.chat.completions.parse(
        model="gpt-4o",
        messages=[{"role": "user", "content": image_content}],
        response_format=BasicOCR,
        temperature=0.0
    )

    data = ocr_response.choices[0].message.parsed.model_dump()
    logger.info(f"OCR Step 1 Complete: {data.get('company')}")

    # Safety net: the vision model is told to output English, but if any
    # Indic-script text slips through, force it to Latin script here.
    data = await englishify_fields(
        data,
        ['company', 'name', 'title', 'address', 'location', 'slogan']
    )

    return data
