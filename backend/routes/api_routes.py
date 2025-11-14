from flask import Blueprint, jsonify, request

bp = Blueprint('api', __name__, url_prefix='/api')

@bp.route('/hello', methods=['GET'])
def hello():
    """
    Simple hello endpoint to test connectivity
    """
    return jsonify({
        "message": "Hello from Flask backend!",
        "status": "success"
    }), 200

@bp.route('/data', methods=['GET'])
def get_data():
    """
    Example endpoint to return data
    """
    sample_data = {
        "items": [
            {"id": 1, "name": "Item 1", "value": 100},
            {"id": 2, "name": "Item 2", "value": 200},
            {"id": 3, "name": "Item 3", "value": 300}
        ]
    }
    return jsonify(sample_data), 200

@bp.route('/data', methods=['POST'])
def post_data():
    """
    Example endpoint to receive data
    """
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    return jsonify({
        "message": "Data received successfully",
        "received": data
    }), 201
