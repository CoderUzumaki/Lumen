from flask import Flask, request, jsonify
import io
import os
import json
import requests
import base64
from pdf2image import convert_from_bytes
from PIL import Image
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# OpenRouter API configuration
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
OPENROUTER_MODEL = os.getenv('OPENROUTER_MODEL', 'nvidia/nemotron-nano-12b-v2-vl:free')
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Debug: Print API key status (first few chars only for security)
if OPENROUTER_API_KEY:
    print(f"✅ OpenRouter API Key loaded: {OPENROUTER_API_KEY[:15]}...")
else:
    print("❌ OpenRouter API Key NOT loaded!")
print(f"✅ Using model: {OPENROUTER_MODEL}")

def image_to_base64(image_content):
    """Convert image bytes to base64 string"""
    return base64.b64encode(image_content).decode('utf-8')

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
        print(f"🔑 Using API Key: {OPENROUTER_API_KEY[:15]}... (from config)")
        print(f"📡 Calling OpenRouter with model: {OPENROUTER_MODEL}")
        
        response = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=60)
        
        if response.status_code == 401:
            print(f"❌ 401 Unauthorized - API Key might be invalid")
            print(f"   API Key being used: {OPENROUTER_API_KEY[:20]}...")
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

def convert_pdf_to_images(pdf_content):
    """Convert PDF to images"""
    try:
        images = convert_from_bytes(pdf_content, dpi=200)
        return images
    except Exception as e:
        raise Exception(f"Failed to convert PDF to images: {str(e)}")

@app.route('/extract', methods=['POST'])
def extract_invoice_data():
    """Main endpoint to extract invoice data from uploaded file"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    try:
        file_content = file.read()
        file_ext = file.filename.lower().split('.')[-1]
        
        # Determine media type
        media_type_map = {
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'gif': 'image/gif',
            'bmp': 'image/bmp',
            'webp': 'image/webp'
        }
        
        if file_ext == 'pdf':
            # Convert PDF to images and process first page (or all pages)
            print("Converting PDF to images...")
            images = convert_pdf_to_images(file_content)
            
            if not images:
                return jsonify({'error': 'No pages found in PDF'}), 400
            
            # Process first page only for speed (can be extended to all pages)
            # For multi-page support, you can loop through all images
            first_page = images[0]
            
            # Convert PIL Image to bytes
            img_byte_arr = io.BytesIO()
            first_page.save(img_byte_arr, format='PNG')
            img_bytes = img_byte_arr.getvalue()
            
            # Convert to base64
            image_base64 = image_to_base64(img_bytes)
            media_type = 'image/png'
            
            print("Processing PDF page with OpenRouter...")
            structured_data = extract_and_structure_with_openrouter(image_base64, media_type)
            
            # Add metadata
            structured_data['pages_processed'] = 1
            structured_data['total_pages'] = len(images)
        
        elif file_ext in media_type_map:
            # Process image directly
            print(f"Processing {file_ext} image with OpenRouter...")
            image_base64 = image_to_base64(file_content)
            media_type = media_type_map[file_ext]
            
            structured_data = extract_and_structure_with_openrouter(image_base64, media_type)
        
        else:
            return jsonify({'error': 'Unsupported file format. Please upload PDF or image file (JPG, PNG, GIF, BMP, WEBP).'}), 400
        
        # Add source file info
        structured_data['source_file'] = file.filename
        structured_data['file_type'] = file_ext
        
        return jsonify({
            'success': True,
            'data': structured_data
        }), 200
    
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/extract-batch', methods=['POST'])
def extract_batch():
    """Process multiple pages from a PDF"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    file_ext = file.filename.lower().split('.')[-1]
    
    if file_ext != 'pdf':
        return jsonify({'error': 'Batch processing only supports PDF files'}), 400
    
    try:
        file_content = file.read()
        
        # Convert all pages
        print("Converting all PDF pages to images...")
        images = convert_pdf_to_images(file_content)
        
        if not images:
            return jsonify({'error': 'No pages found in PDF'}), 400
        
        results = []
        
        # Process each page
        for idx, page_image in enumerate(images):
            print(f"Processing page {idx + 1}/{len(images)}...")
            
            # Convert PIL Image to bytes
            img_byte_arr = io.BytesIO()
            page_image.save(img_byte_arr, format='PNG')
            img_bytes = img_byte_arr.getvalue()
            
            # Convert to base64
            image_base64 = image_to_base64(img_bytes)
            
            # Extract data
            try:
                page_data = extract_and_structure_with_openrouter(image_base64, 'image/png')
                page_data['page_number'] = idx + 1
                results.append(page_data)
            except Exception as e:
                results.append({
                    'page_number': idx + 1,
                    'error': str(e),
                    'success': False
                })
        
        return jsonify({
            'success': True,
            'total_pages': len(images),
            'processed_pages': len(results),
            'data': results
        }), 200
    
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    config_status = {
        'openrouter_api_key': 'configured' if OPENROUTER_API_KEY else 'missing',
        'openrouter_model': OPENROUTER_MODEL
    }
    
    return jsonify({
        'status': 'healthy',
        'config': config_status
    }), 200

@app.route('/', methods=['GET'])
def home():
    """Home endpoint with API documentation"""
    return jsonify({
        'name': 'LUMEN Financial Intelligence API',
        'version': '1.0.0',
        'endpoints': {
            'POST /extract': 'Extract data from single image or first page of PDF',
            'POST /extract-batch': 'Extract data from all pages of a PDF',
            'GET /health': 'Health check and configuration status',
            'GET /': 'API documentation'
        },
        'supported_formats': ['PDF', 'JPG', 'JPEG', 'PNG', 'GIF', 'BMP', 'WEBP']
    }), 200

if __name__ == '__main__':
    # Check for required environment variables
    if not OPENROUTER_API_KEY:
        print("❌ ERROR: OPENROUTER_API_KEY environment variable not set!")
        print("Please set it using: export OPENROUTER_API_KEY='your-key-here'")
    else:
        print(f"✅ OpenRouter API Key configured")
        print(f"✅ Using model: {OPENROUTER_MODEL}")
    
    print("\n🚀 Starting LUMEN Financial Intelligence API...")
    print("📝 Endpoints available:")
    print("   POST /extract - Single page extraction")
    print("   POST /extract-batch - Multi-page PDF extraction")
    print("   GET /health - Health check")
    
    app.run(debug=True, host='0.0.0.0', port=5000)