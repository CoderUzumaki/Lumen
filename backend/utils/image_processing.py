"""Image processing utilities for invoice extraction"""
import io
import base64
from pdf2image import convert_from_bytes
from PIL import Image


def image_to_base64(image_content):
    """Convert image bytes to base64 string"""
    return base64.b64encode(image_content).decode('utf-8')


def convert_pdf_to_images(pdf_content):
    """Convert PDF to images"""
    try:
        images = convert_from_bytes(pdf_content, dpi=200)
        return images
    except Exception as e:
        raise Exception(f"Failed to convert PDF to images: {str(e)}")


def pil_image_to_bytes(pil_image, format='PNG'):
    """Convert PIL Image to bytes"""
    img_byte_arr = io.BytesIO()
    pil_image.save(img_byte_arr, format=format)
    return img_byte_arr.getvalue()
