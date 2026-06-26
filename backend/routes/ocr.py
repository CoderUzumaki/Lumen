"""OCR and invoice extraction routes"""
import logging

from flask import Blueprint, g, request, jsonify

from utils.auth import require_auth
from utils.image_processing import (
    image_to_base64,
    convert_pdf_to_images,
    pil_image_to_bytes,
)
from utils.openrouter import extract_and_structure_with_openrouter
from utils.normalize import normalize_transaction
from utils.save_transaction import save_transaction

logger = logging.getLogger(__name__)
# Create blueprint
ocr_bp = Blueprint('ocr', __name__)


@ocr_bp.route('/extract', methods=['POST'])
@require_auth
def extract_invoice_data():
    """
    Combined endpoint: OCR image/PDF and store transaction directly to database.
    The transaction is saved under the authenticated user (g.user_id from JWT).
    """
    user_id = g.user_id

    # Validate file
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
        
        # Step 1: Perform OCR
        if file_ext == 'pdf':
            # Convert PDF to images and process first page
            logger.info("Converting PDF to images...")
            images = convert_pdf_to_images(file_content)
            
            if not images:
                return jsonify({'error': 'No pages found in PDF'}), 400
            
            first_page = images[0]
            img_bytes = pil_image_to_bytes(first_page, format='PNG')
            image_base64 = image_to_base64(img_bytes)
            media_type = 'image/png'
            
            logger.info("Processing PDF page with OpenRouter...")
            structured_data = extract_and_structure_with_openrouter(image_base64, media_type)
            
            # Add metadata
            structured_data['pages_processed'] = 1
            structured_data['total_pages'] = len(images)
        
        elif file_ext in media_type_map:
            # Process image directly
            logger.info(f"Processing {file_ext} image with OpenRouter...")
            image_base64 = image_to_base64(file_content)
            media_type = media_type_map[file_ext]
            
            structured_data = extract_and_structure_with_openrouter(image_base64, media_type)
        
        else:
            return jsonify({'error': 'Unsupported file format. Please upload PDF or image file (JPG, PNG, GIF, BMP, WEBP).'}), 400
        
        # Add source file info
        structured_data['source_file'] = file.filename
        structured_data['file_type'] = file_ext
        
        # Step 2: Normalize the OCR data
        logger.info("Normalizing transaction data...")
        try:
            normalized = normalize_transaction(structured_data)
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'Normalization failed: {str(e)}',
                'ocr_data': structured_data
            }), 500
        
        # Step 3: Save to database (optional - graceful degradation)
        transaction_id = None
        db_warning = None
        logger.info(f"Saving transaction to database for user {user_id}...")
        try:
            transaction_id = save_transaction(user_id, normalized)
            logger.info(f"✅ Transaction {transaction_id} saved to database")
        except Exception as e:
            db_warning = f"Database save failed: {str(e)}"
            logger.warning(f"⚠️  {db_warning}")
            logger.info("   Continuing without database storage (OCR successful)")
        
        # Step 4: Return success response
        response_data = {
            'success': True,
            'message': 'Transaction extracted successfully',
            'data': normalized,
            'ocr_data': structured_data
        }
        
        if transaction_id:
            response_data['transaction_id'] = str(transaction_id)
            response_data['message'] = 'Transaction extracted and stored successfully'
        else:
            response_data['warning'] = 'Database unavailable - transaction not persisted'
            response_data['db_error'] = db_warning
        
        return jsonify(response_data), 200
    
    except Exception as e:
        logger.info(f"Error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500