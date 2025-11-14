"""OCR and invoice extraction routes"""
from flask import Blueprint, request, jsonify
from utils.image_processing import (
    image_to_base64, 
    convert_pdf_to_images, 
    pil_image_to_bytes
)
from utils.openrouter import extract_and_structure_with_openrouter
from flask import Blueprint, request, jsonify
from utils.normalize import normalize_transaction
from utils.save_transaction import save_transaction
# Create blueprint
ocr_bp = Blueprint('ocr', __name__)


@ocr_bp.route('/extract', methods=['POST'])
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
            img_bytes = pil_image_to_bytes(first_page, format='PNG')
            
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







@ocr_bp.route("/transaction/create", methods=["POST"])
def create_transaction():
    payload = request.json
    if not payload or "user_id" not in payload or "ocr_data" not in payload:
        return jsonify({"error": "user_id and ocr_data are required"}), 400

    user_id = payload["user_id"]
    ocr_data = payload["ocr_data"]     
    try:
        normalized = normalize_transaction(ocr_data)
    except Exception as e:
        return jsonify({"error": f"Normalization failed: {str(e)}"}), 500

    # (3) Save to database (transaction + items)
    try:
        transaction_id = save_transaction(user_id, normalized)
    except Exception as e:
        return jsonify({"error": f"Database save failed: {str(e)}"}), 500

    # (4) Return success response
    return jsonify({
        "success": True,
        "message": "Transaction stored successfully",
        "transaction_id": str(transaction_id),
        "normalized_data": normalized
    }), 200