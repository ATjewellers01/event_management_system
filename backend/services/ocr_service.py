from backend.core.config import async_client, logger
from backend.core.models import BasicOCR
from google.cloud import translate_v2
import os

def translate_hindi_to_english(text: str) -> str:
    if not text:
        return text

    try:
        translate_client = translate_v2.Client()
        result = translate_client.translate_text(text, target_language='en')
        return result['translatedText']
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
            data[field] = translate_hindi_to_english(data[field])

    return data
