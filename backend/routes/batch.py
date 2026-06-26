"""Batch processing routes for multi-page PDFs"""
import logging

from flask import Blueprint, request, jsonify

from utils.auth import require_auth
from utils.image_processing import (
    convert_pdf_to_images,
    pil_image_to_bytes,
    image_to_base64
)
from utils.openrouter import extract_and_structure_with_openrouter

logger = logging.getLogger(__name__)

# Create blueprint
batch_bp = Blueprint('batch', __name__)


@batch_bp.route('/extract-batch', methods=['POST'])
@require_auth
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
        logger.info("Converting all PDF pages to images...")
        images = convert_pdf_to_images(file_content)
        
        if not images:
            return jsonify({'error': 'No pages found in PDF'}), 400
        
        results = []
        
        # Process each page
        for idx, page_image in enumerate(images):
            logger.info(f"Processing page {idx + 1}/{len(images)}...")
            
            # Convert PIL Image to bytes
            img_bytes = pil_image_to_bytes(page_image, format='PNG')
            
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
        logger.info(f"Error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
