"""OpenRouter vision call for invoice OCR.

The request itself goes through `utils.llm.chat_completion`, so a dead key,
rate limit or retired model raises a typed `LLMError` here too. The text-only
LLM call sites (chat synthesis, classification, anomaly explanation) live in
`ai/*` and use `Config.LLM_TEXT_MODEL`.
"""
import json
import logging
import re

from config import Config
from utils.llm import LLMError, chat_completion

logger = logging.getLogger(__name__)


EXTRACTION_PROMPT = """
You are an expert at extracting structured information from invoice/bill/receipt images.

Please analyze this image and extract the following information:
- invoice_number: string (the invoice/bill/receipt number)
- vendor_name: string (company/vendor/merchant name)
- date: string (invoice/transaction date in YYYY-MM-DD format if possible)
- total_amount: string (total amount with currency symbol)
- items: array of objects with item_name, quantity, and price (if line items are visible)
- customer_name: string (if available)
- address: string (vendor or billing address if available)
- payment_method: string (cash, card, UPI, etc. if mentioned)
- tax_amount: string (tax/GST amount if available)
- category: string (classify as: Groceries, Restaurant, Utilities, Transport, Healthcare, Shopping, Entertainment, or Other)

IMPORTANT:
1. Return ONLY a valid JSON object with these fields
2. If any field is not found or not clearly visible, use null for that field
3. Do NOT include any markdown formatting, code blocks, or additional text
4. Extract ALL visible text accurately
5. For items array, include as many line items as you can clearly see

Return pure JSON only.
"""


def parse_json_reply(content: str) -> dict:
    """Pull the JSON object out of a model reply.

    Models wrap it in ```json fences or add a sentence before it despite the
    prompt, so take the outermost {...}. Raises LLMError(BAD_RESPONSE) when
    there is no JSON object in the reply. The reply is invoice content, so it
    is logged at DEBUG only and kept out of the error detail (logged at ERROR).
    """
    text = re.sub(r"```(?:json)?", "", content or "").strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        logger.debug("Vision reply without a JSON object: %r", text[:200])
        raise LLMError(LLMError.BAD_RESPONSE, f"No JSON object in vision reply ({len(text)} chars)")
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError as e:
        logger.debug("Vision reply with invalid JSON: %r", text[:200])
        raise LLMError(LLMError.BAD_RESPONSE, f"Vision reply is not valid JSON ({e})") from e
    if not isinstance(data, dict):
        raise LLMError(LLMError.BAD_RESPONSE, "Vision reply JSON is not an object")
    return data


def extract_and_structure_with_openrouter(image_base64, media_type="image/jpeg"):
    """OCR and structure an invoice image in one vision-model call.

    Raises LLMError for any provider failure or unusable reply.
    """
    content = [
        {"type": "text", "text": EXTRACTION_PROMPT},
        {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{image_base64}"}},
    ]
    # Two tries must fit inside gunicorn's 120s worker timeout on Render.
    call = dict(
        model=Config.get_llm_vision_model(),
        fallback_models=Config.get_llm_vision_fallback_models(),
        temperature=0.1,
        max_tokens=2000,
        timeout=55,
    )
    reply = chat_completion(content, **call)
    try:
        return parse_json_reply(reply)
    except LLMError as e:
        # With `openrouter/free` a retry usually lands on a different model.
        logger.info("Retrying invoice OCR after an unusable reply")
        logger.debug("Unusable invoice OCR reply: %s", e.detail)
        return parse_json_reply(chat_completion(content, **call))
