"""OpenRouter API integration for OCR and data extraction.

This module talks to OpenRouter's vision model for invoice OCR. The text-only
LLM call sites (chat synthesis, classification, anomaly explanation) live in
`ai/*` and use `Config.LLM_TEXT_MODEL`.
"""
import json
import logging

import requests

from config import Config

logger = logging.getLogger(__name__)


# Backwards-compatible module-level aliases. New code should read from `Config`.
OPENROUTER_API_KEY = Config.OPENROUTER_API_KEY
OPENROUTER_MODEL = Config.LLM_VISION_MODEL
OPENROUTER_URL = Config.OPENROUTER_CHAT_URL


def get_api_config():
    """Get OpenRouter API configuration"""
    return {
        'api_key': Config.OPENROUTER_API_KEY,
        'model': Config.LLM_VISION_MODEL,
        'url': Config.OPENROUTER_CHAT_URL
    }


def extract_and_structure_with_openrouter(image_base64, media_type="image/jpeg"):
    """Use OpenRouter multimodal LLM for OCR and structuring in one step"""
    
    prompt = """
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
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:5000",
        "X-Title": "LUMEN Financial Intelligence"
    }
    
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{media_type};base64,{image_base64}"
                        }
                    }
                ]
            }
        ],
        "temperature": 0.1,
        "max_tokens": 2000
    }
    
    try:
        from utils.logging_config import mask_secret
        logger.debug("Calling OpenRouter (model=%s, key=%s)", OPENROUTER_MODEL, mask_secret(OPENROUTER_API_KEY))

        response = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=60)

        if response.status_code == 401:
            logger.error("OpenRouter returned 401 Unauthorized (key=%s)", mask_secret(OPENROUTER_API_KEY))
            raise Exception(f"OpenRouter API authentication failed. Please check your API key. Status: {response.status_code}")
        
        response.raise_for_status()
        result = response.json()
        
        content = result['choices'][0]['message']['content']
        
        # Clean up any markdown formatting
        content = content.strip()
        if content.startswith('```json'):
            content = content[7:]
        if content.startswith('```'):
            content = content[3:]
        if content.endswith('```'):
            content = content[:-3]
        content = content.strip()
        
        # Parse JSON
        structured_data = json.loads(content)
        return structured_data
    
    except requests.exceptions.Timeout:
        raise Exception("OpenRouter API request timed out. Please try again.")
    except requests.exceptions.RequestException as e:
        raise Exception(f"OpenRouter API request failed: {str(e)}")
    except json.JSONDecodeError as e:
        raise Exception(f"Failed to parse OpenRouter response as JSON: {str(e)}\nResponse: {content}")
    except KeyError as e:
        raise Exception(f"Unexpected OpenRouter API response format: {str(e)}")
