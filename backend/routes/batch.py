"""Batch processing routes for multi-page PDFs"""
import logging

from flask import Blueprint, g, request, jsonify

from utils.auth import require_auth
from utils.errors import api_error
from utils.limiter import limiter
from utils.upload_validation import validate_upload
from utils.image_processing import (
    convert_pdf_to_images,
    pil_image_to_bytes,
    image_to_base64,
)
from utils.openrouter import extract_and_structure_with_openrouter
from utils.normalize import normalize_transaction
from utils.save_transaction import save_transaction

logger = logging.getLogger(__name__)

batch_bp = Blueprint("batch", __name__)


@batch_bp.route("/extract-batch", methods=["POST"])
@limiter.limit("5 per minute")
@require_auth
def extract_batch():
    """Process all pages from a PDF and persist each invoice to the database."""
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    file_ext = file.filename.lower().split(".")[-1]
    if file_ext != "pdf":
        return jsonify({"error": "Batch processing only supports PDF files"}), 400

    user_id = g.user_id

    try:
        file_content = file.read()
        upload_error = validate_upload(file.filename, file_content)
        if upload_error:
            return jsonify({"error": upload_error}), 400

        logger.info("Converting all PDF pages to images...")
        images = convert_pdf_to_images(file_content)
        if not images:
            return jsonify({"error": "No pages found in PDF"}), 400

        results = []
        saved_ids = []

        for idx, page_image in enumerate(images):
            logger.info("Processing page %s/%s...", idx + 1, len(images))
            img_bytes = pil_image_to_bytes(page_image, format="PNG")
            image_base64 = image_to_base64(img_bytes)

            try:
                page_data = extract_and_structure_with_openrouter(
                    image_base64, "image/png"
                )
                page_data["page_number"] = idx + 1
                page_data["source_file"] = file.filename

                normalized = normalize_transaction(page_data)
                transaction_id = save_transaction(user_id, normalized)
                saved_ids.append(str(transaction_id))

                results.append(
                    {
                        "page_number": idx + 1,
                        "success": True,
                        "transaction_id": str(transaction_id),
                        "vendor_name": normalized.get("vendor_name"),
                        "total_amount": normalized.get("total_amount"),
                    }
                )
            except Exception as e:
                logger.warning("Page %s failed: %s", idx + 1, e)
                results.append(
                    {
                        "page_number": idx + 1,
                        "success": False,
                        "error": "Page extraction or save failed",
                    }
                )

        return jsonify(
            {
                "success": True,
                "total_pages": len(images),
                "processed_pages": len(results),
                "saved_count": len(saved_ids),
                "transaction_ids": saved_ids,
                "data": results,
            }
        ), 200

    except Exception as e:
        return api_error("Batch extraction failed", code="batch_failed", log=e)
