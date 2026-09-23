from flask import Blueprint, g, request, jsonify
from models import Transaction, TransactionItem
from models.database import db
from sqlalchemy import and_, or_
from datetime import datetime
import uuid

from utils.auth import require_auth

database_query_bp = Blueprint('database_query', __name__)


# The legacy URL shape included a `<user_id>` path segment. We keep accepting it
# so older frontends don't 404 between AUTH-03 and AUTH-05, but the value is
# IGNORED — the authenticated user always comes from g.user_id. AUTH-05 deletes
# the path segment from the frontend; once that ships, this route can drop the
# parameter.
@database_query_bp.route('/transactions', methods=['GET'])
@database_query_bp.route('/transactions/<user_id>', methods=['GET'])
@require_auth
def get_transactions(user_id=None):
    """List the authenticated user's transactions with filters and pagination.

    Any `user_id` path segment is ignored; identity comes from the JWT.

    Query parameters: see code for filter list (date_from, date_to, category,
    vendor, min_amount, max_amount, page, page_size, sort_by, sort_order).
    """
    try:
        user_id = g.user_id
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
@require_auth
def create_transaction():
    """Create a new transaction owned by the authenticated user.

    The request body must NOT include user_id; any value is ignored.
    """
    try:
        data = request.json or {}

        if not data.get('vendor_name'):
            return jsonify({'success': False, 'error': 'vendor_name is required'}), 400

        # Create transaction
        transaction_id = str(uuid.uuid4())
        transaction = Transaction(
            id=transaction_id,
            user_id=str(g.user_id),
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


@database_query_bp.route('/transactions/<transaction_id>', methods=['DELETE'])
@require_auth
def delete_transaction(transaction_id):
    """Delete a transaction owned by the authenticated user."""
    try:
        transaction = Transaction.query.filter_by(
            id=transaction_id, user_id=str(g.user_id)
        ).first()
        if not transaction:
            return jsonify({'success': False, 'error': 'Transaction not found'}), 404

        TransactionItem.query.filter_by(transaction_id=transaction_id).delete()
        db.session.delete(transaction)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Transaction deleted'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Delete failed'}), 500


@database_query_bp.route('/transactions/<transaction_id>', methods=['PUT'])
@require_auth
def update_transaction(transaction_id):
    """Update an existing transaction. Only succeeds if it belongs to the
    authenticated user; otherwise 404 (we hide existence to avoid leaking ids).
    """
    try:
        data = request.json or {}

        # Scope the lookup by the authenticated user. A transaction the caller
        # does not own is treated as if it does not exist.
        transaction = Transaction.query.filter_by(
            id=transaction_id, user_id=str(g.user_id)
        ).first()

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
