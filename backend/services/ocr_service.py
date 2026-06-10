from backend.core.config import async_client, logger
from backend.core.models import BasicOCR
import re

def detect_hindi_text(text: str) -> bool:
    if not text:
        return False
    hindi_unicode_range = re.compile(r'[ऀ-ॿ]')
    return bool(hindi_unicode_range.search(text))

async def translate_hindi_to_english(text: str) -> str:
    if not text or not detect_hindi_text(text):
        return text

    try:
        response = await async_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": f"Translate this Hindi text to English. Return ONLY the English translation, nothing else:\n\n{text}"
                }
            ],
            temperature=0.0
        )
        translated = response.choices[0].message.content.strip()
        logger.info(f"Translated: '{text}' → '{translated}'")
        return translated
    except Exception as e:
        logger.warning(f"Translation failed for '{text}': {str(e)}")
        return text

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
        Extract text from this business card.
        Use your vision capabilities to accurately read even stylized, rotated, or inverted text.
        Fields: company, name, title, phone, email, address, slogan, location, website.
        If a field is missing, use an empty string.
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

    # Translate Hindi text to English
    fields_to_translate = ['company', 'name', 'address', 'slogan']
    for field in fields_to_translate:
        if field in data and data[field]:
            data[field] = await translate_hindi_to_english(data[field])

    return data
