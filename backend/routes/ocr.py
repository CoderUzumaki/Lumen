"""OCR and invoice extraction routes"""
import logging

from flask import Blueprint, g, request, jsonify

from utils.auth import require_auth
from utils.errors import api_error, llm_api_error
from utils.limiter import limiter
from utils.llm import LLMError
from utils.upload_validation import validate_upload
from utils.image_processing import (
    PDFReadError,
    image_to_base64,
    pil_image_to_bytes,
    render_pdf_first_page,
)
from utils.openrouter import extract_and_structure_with_openrouter
from utils.normalize import normalize_transaction
from utils.save_transaction import save_transaction_detailed

logger = logging.getLogger(__name__)
# Create blueprint
ocr_bp = Blueprint('ocr', __name__)

MEDIA_TYPES = {
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg',
    'png': 'image/png',
    'gif': 'image/gif',
    'bmp': 'image/bmp',
    'webp': 'image/webp',
}

# What the user sees when the vision model fails (status codes: utils.errors.llm_api_error).
OCR_LLM_MESSAGES = {
    "rate_limited": "Invoice scanning is handling too many requests right now. Please try again in a minute.",
    "bad_response": "We couldn't read this invoice. Please try again, or upload a clearer image.",
    "unavailable": "Invoice scanning is unavailable right now. Please try again shortly.",
}


@ocr_bp.route('/extract', methods=['POST'])
@limiter.limit("15 per minute")
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

    file_content = file.read()
    upload_error = validate_upload(file.filename, file_content)
    if upload_error:
        return jsonify({"error": upload_error}), 400

    file_ext = file.filename.lower().rsplit('.', 1)[-1]

    # Step 1: OCR (PDFs: first page only)
    try:
        if file_ext == 'pdf':
            try:
                first_page, total_pages = render_pdf_first_page(file_content)
            except PDFReadError as e:
                logger.info("Unreadable PDF upload %r: %s", file.filename, e)
                return api_error(
                    "Couldn't open this PDF. It may be corrupted or password-protected.",
                    status=422,
                    code="pdf_unreadable",
                )
            if first_page is None:
                return api_error("This PDF has no pages.", status=422, code="pdf_empty")

            image_base64 = image_to_base64(pil_image_to_bytes(first_page, format='PNG'))
            logger.info("Processing PDF page 1/%d with OpenRouter...", total_pages)
            structured_data = extract_and_structure_with_openrouter(image_base64, 'image/png')
            structured_data['pages_processed'] = 1
            structured_data['total_pages'] = total_pages
        elif file_ext in MEDIA_TYPES:
            logger.info("Processing %s image with OpenRouter...", file_ext)
            structured_data = extract_and_structure_with_openrouter(
                image_to_base64(file_content), MEDIA_TYPES[file_ext]
            )
        else:
            return jsonify({'error': 'Unsupported file format. Please upload PDF or image file (JPG, PNG, GIF, BMP, WEBP).'}), 400
    except LLMError as e:
        return llm_api_error(e, OCR_LLM_MESSAGES, context=f"OCR failed for user={user_id}")
    except Exception as e:
        return api_error("Invoice extraction failed", code="extract_failed", log=e)

    structured_data['source_file'] = file.filename
    structured_data['file_type'] = file_ext

    # Step 2: Normalize the OCR data (never raises; unparseable fields become None)
    normalized = normalize_transaction(structured_data)
    if normalized["total_amount"] is None and not normalized["vendor_name"]:
        logger.info("OCR found no invoice data in %r: %s", file.filename, structured_data)
        return api_error(
            "We couldn't find invoice details in this file. Please upload a clear photo or PDF of an invoice or receipt.",
            status=422,
            code="no_invoice_data",
        )

    # Step 3: Save. If this fails the user must know: reporting success would
    # lose the invoice silently.
    try:
        transaction_id, created = save_transaction_detailed(user_id, normalized, email=g.user_email)
    except Exception as e:
        return api_error(
            "We read the invoice but couldn't save it. Please try again.",
            code="save_failed",
            log=e,
        )

    if created:
        logger.info("Transaction %s saved for user %s", transaction_id, user_id)
        message = 'Transaction extracted and stored successfully'
    else:
        message = 'This invoice was already uploaded'

    return jsonify({
        'success': True,
        'duplicate': not created,
        'message': message,
        'transaction_id': str(transaction_id),
        'data': normalized,
        'ocr_data': structured_data,
    }), 200
