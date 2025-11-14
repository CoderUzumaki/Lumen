from flask import Blueprint, request, jsonify
from models import Transaction, TransactionItem
from models.database import db
from sqlalchemy import and_, or_
from datetime import datetime
import uuid

database_query_bp = Blueprint('database_query', __name__)


@database_query_bp.route('/transactions/<user_id>', methods=['GET'])
def get_transactions(user_id):
    """
    Get transactions with filters and pagination
    
    Query parameters:
    - date_from: Filter transactions from this date (YYYY-MM-DD)
    - date_to: Filter transactions up to this date (YYYY-MM-DD)
    - category: Filter by category
    - vendor: Filter by vendor name (partial match)
    - min_amount: Minimum transaction amount
    - max_amount: Maximum transaction amount
    - page: Page number (default: 1)
    - per_page: Items per page (default: 10, max: 100)
    - sort_by: Field to sort by (date, total_amount, vendor_name)
    - sort_order: asc or desc (default: desc)
    
    Example: GET /transactions/123?date_from=2024-01-01&category=Restaurant&page=1&per_page=20
    """
    try:
        # Get pagination parameters
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('page_size', 10)), 100)  # Max 100 per page
        
        # Get filter parameters
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        category = request.args.get('category')
        vendor = request.args.get('vendor')
        min_amount = request.args.get('min_amount', type=float)
        max_amount = request.args.get('max_amount', type=float)
        
        # Get sorting parameters
        sort_by = request.args.get('sort_by', 'created_at')
        sort_order = request.args.get('sort_order', 'desc')
        
        # Build query
        query = Transaction.query.filter_by(user_id=str(user_id))
        
        # Apply filters
        if date_from:
            query = query.filter(Transaction.date >= date_from)
        
        if date_to:
            query = query.filter(Transaction.date <= date_to)
        
        if category:
            query = query.filter(Transaction.category == category)
        
        if vendor:
            query = query.filter(Transaction.vendor_name.like(f'%{vendor}%'))
        
        if min_amount is not None:
            query = query.filter(Transaction.total_amount >= min_amount)
        
        if max_amount is not None:
            query = query.filter(Transaction.total_amount <= max_amount)
        
        # Apply sorting
        sort_field = getattr(Transaction, sort_by, Transaction.created_at)
        if sort_order.lower() == 'asc':
            query = query.order_by(sort_field.asc())
        else:
            query = query.order_by(sort_field.desc())
        
        # Execute paginated query
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        # Format response
        transactions = []
        for txn in pagination.items:
            transactions.append({
                'id': txn.id,
                'vendor_name': txn.vendor_name,
                'invoice_number': txn.invoice_number,
                'date': txn.date,
                'total_amount': txn.total_amount,
                'tax_amount': txn.tax_amount,
                'payment_method': txn.payment_method,
                'address': txn.address,
                'category': txn.category,
                'created_at': txn.created_at.isoformat() if txn.created_at else None,
                'items': [
                    {
                        'item_name': item.item_name,
                        'quantity': item.quantity,
                        'unit_price': item.unit_price,
                        'total_price': item.total_price
                    }
                    for item in txn.items
                ]
            })
        
        return jsonify({
            'success': True,
            'data': transactions,
            'pagination': {
                'page': pagination.page,
                'per_page': pagination.per_page,
                'total_pages': pagination.pages,
                'total_items': pagination.total,
                'has_next': pagination.has_next,
                'has_prev': pagination.has_prev
            },
            'filters_applied': {
                'date_from': date_from,
                'date_to': date_to,
                'category': category,
                'vendor': vendor,
                'min_amount': min_amount,
                'max_amount': max_amount
            }
        }), 200
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@database_query_bp.route('/transactions', methods=['POST'])
def create_transaction():
    """
    Create a new transaction from JSON data
    
    Request body:
    {
        "user_id": "123",
        "vendor_name": "East Repair Inc.",
        "invoice_number": "US-001",
        "date": "2019-11-02",
        "total_amount": 154.06,
        "tax_amount": 9.06,
        "payment_method": "check",
        "address": "2 Court Square, New York, NY 12210",
        "category": "Other",
        "items": [
            {
                "item_name": "Front and rear brake cables",
                "quantity": 1,
                "unit_price": 100.0,
                "total_price": 100.0
            }
        ]
    }
    """
    try:
        data = request.json
        
        # Validate required fields
        if not data.get('user_id'):
            return jsonify({'success': False, 'error': 'user_id is required'}), 400
        
        if not data.get('vendor_name'):
            return jsonify({'success': False, 'error': 'vendor_name is required'}), 400
        
        # Create transaction
        transaction_id = str(uuid.uuid4())
        transaction = Transaction(
            id=transaction_id,
            user_id=str(data['user_id']),
            vendor_name=data.get('vendor_name'),
            invoice_number=data.get('invoice_number'),
            date=data.get('date'),
            total_amount=data.get('total_amount'),
            tax_amount=data.get('tax_amount'),
            payment_method=data.get('payment_method'),
            address=data.get('address'),
            category=data.get('category'),
            created_at=datetime.utcnow()
        )
        
        db.session.add(transaction)
        
        # Add transaction items if provided
        items = data.get('items', [])
        for item_data in items:
            item = TransactionItem(
                id=str(uuid.uuid4()),
                transaction_id=transaction_id,
                item_name=item_data.get('item_name'),
                quantity=item_data.get('quantity', 1),
                unit_price=item_data.get('unit_price'),
                total_price=item_data.get('total_price')
            )
            db.session.add(item)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Transaction created successfully',
            'transaction_id': transaction_id,
            'data': {
                'id': transaction.id,
                'vendor_name': transaction.vendor_name,
                'invoice_number': transaction.invoice_number,
                'date': transaction.date,
                'total_amount': transaction.total_amount,
                'category': transaction.category,
                'items_count': len(items)
            }
        }), 201
    
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@database_query_bp.route('/transactions/<transaction_id>', methods=['PUT'])
def update_transaction(transaction_id):
    """
    Update an existing transaction
    
    Request body (all fields optional):
    {
        "vendor_name": "Updated Vendor",
        "invoice_number": "US-002",
        "date": "2024-11-14",
        "total_amount": 200.00,
        "tax_amount": 15.00,
        "payment_method": "credit_card",
        "address": "New Address",
        "category": "Restaurant",
        "items": [
            {
                "item_name": "Updated item",
                "quantity": 2,
                "unit_price": 75.0,
                "total_price": 150.0
            }
        ]
    }
    
    Example: curl -X PUT http://localhost:5000/transactions/8aa77edc-b44e-4699-972d-6400ffb34b89 -H "Content-Type: application/json" -d '{"category":"Restaurant"}'
    """
    try:
        data = request.json
        
        # Find existing transaction
        transaction = Transaction.query.filter_by(id=transaction_id).first()
        
        if not transaction:
            return jsonify({
                'success': False,
                'error': f'Transaction with id {transaction_id} not found'
            }), 404
        
        # Update transaction fields if provided
        if 'vendor_name' in data:
            transaction.vendor_name = data['vendor_name']
        if 'invoice_number' in data:
            transaction.invoice_number = data['invoice_number']
        if 'date' in data:
            transaction.date = data['date']
        if 'total_amount' in data:
            transaction.total_amount = data['total_amount']
        if 'tax_amount' in data:
            transaction.tax_amount = data['tax_amount']
        if 'payment_method' in data:
            transaction.payment_method = data['payment_method']
        if 'address' in data:
            transaction.address = data['address']
        if 'category' in data:
            transaction.category = data['category']
        
        # Update items if provided
        if 'items' in data:
            # Delete existing items
            TransactionItem.query.filter_by(transaction_id=transaction_id).delete()
            
            # Add new items
            for item_data in data['items']:
                item = TransactionItem(
                    id=str(uuid.uuid4()),
                    transaction_id=transaction_id,
                    item_name=item_data.get('item_name'),
                    quantity=item_data.get('quantity', 1),
                    unit_price=item_data.get('unit_price'),
                    total_price=item_data.get('total_price')
                )
                db.session.add(item)
        
        db.session.commit()
        
        # Fetch updated transaction with items
        updated_transaction = Transaction.query.filter_by(id=transaction_id).first()
        
        return jsonify({
            'success': True,
            'message': 'Transaction updated successfully',
            'data': {
                'id': updated_transaction.id,
                'vendor_name': updated_transaction.vendor_name,
                'invoice_number': updated_transaction.invoice_number,
                'date': updated_transaction.date,
                'total_amount': updated_transaction.total_amount,
                'tax_amount': updated_transaction.tax_amount,
                'payment_method': updated_transaction.payment_method,
                'address': updated_transaction.address,
                'category': updated_transaction.category,
                'items': [
                    {
                        'item_name': item.item_name,
                        'quantity': item.quantity,
                        'unit_price': item.unit_price,
                        'total_price': item.total_price
                    }
                    for item in updated_transaction.items
                ]
            }
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
