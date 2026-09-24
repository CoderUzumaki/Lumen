"""Image processing utilities for invoice extraction"""
import io
import base64

import pypdfium2 as pdfium


class PDFReadError(ValueError):
    """The upload isn't a PDF we can open (corrupt, encrypted, not a PDF)."""


def image_to_base64(image_content):
    """Convert image bytes to base64 string"""
    return base64.b64encode(image_content).decode('utf-8')


def _open_pdf(pdf_content):
    try:
        return pdfium.PdfDocument(pdf_content)
    except pdfium.PdfiumError as e:
        raise PDFReadError(f"Could not open PDF: {e}") from e


def convert_pdf_to_images(pdf_content, dpi=200, max_pages=None):
    """Render PDF pages to PIL images.

    Uses pdfium via the pypdfium2 wheel, so there is no system dependency
    (pdf2image needed Poppler's `pdftoppm` on PATH, which neither Windows dev
    machines nor Render's Python runtime have). Raises PDFReadError when the
    file can't be opened.
    """
    pdf = _open_pdf(pdf_content)
    try:
        count = len(pdf) if max_pages is None else min(len(pdf), max_pages)
        images = []
        for i in range(count):
            page = pdf[i]
            try:
                images.append(page.render(scale=dpi / 72).to_pil())
            finally:
                page.close()
        return images
    finally:
        pdf.close()


def render_pdf_first_page(pdf_content, dpi=200):
    """Return (first page as a PIL image or None if the PDF has no pages, page count)."""
    pdf = _open_pdf(pdf_content)
    try:
        total = len(pdf)
        if total == 0:
            return None, 0
        page = pdf[0]
        try:
            return page.render(scale=dpi / 72).to_pil(), total
        finally:
            page.close()
    finally:
        pdf.close()


def pil_image_to_bytes(pil_image, format='PNG'):
    """Convert PIL Image to bytes"""
    img_byte_arr = io.BytesIO()
    pil_image.save(img_byte_arr, format=format)
    return img_byte_arr.getvalue()
