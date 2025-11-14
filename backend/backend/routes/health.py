"""Health check and documentation routes"""
from flask import Blueprint, jsonify
from utils.openrouter import get_api_config

# Create blueprint
health_bp = Blueprint('health', __name__)


@health_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    config = get_api_config()
    config_status = {
        'openrouter_api_key': 'configured' if config['api_key'] else 'missing',
        'openrouter_model': config['model']
    }
    
    return jsonify({
        'status': 'healthy',
        'config': config_status
    }), 200


@health_bp.route('/', methods=['GET'])
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
