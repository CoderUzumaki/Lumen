"""OpenRouter API integration for OCR and data extraction"""
import os
import json
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# OpenRouter API configuration
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
OPENROUTER_MODEL = os.getenv('OPENROUTER_MODEL', 'nvidia/nemotron-nano-12b-v2-vl:free')
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def get_api_config():
    """Get OpenRouter API configuration"""
    return {
        'api_key': OPENROUTER_API_KEY,
        'model': OPENROUTER_MODEL,
        'url': OPENROUTER_URL
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
        print(f"🔑 Using API Key: {OPENROUTER_API_KEY[:15] if OPENROUTER_API_KEY else 'None'}... (from config)")
        print(f"📡 Calling OpenRouter with model: {OPENROUTER_MODEL}")
        
        response = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=60)
        
        if response.status_code == 401:
            print(f"❌ 401 Unauthorized - API Key might be invalid")
            print(f"   API Key being used: {OPENROUTER_API_KEY[:20] if OPENROUTER_API_KEY else 'None'}...")
            raise Exception(f"OpenRouter API authentication failed. Please check your API key. Status: {response.status_code}, Response: {response.text}")
        
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
