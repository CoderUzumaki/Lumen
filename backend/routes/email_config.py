"""Email configuration endpoints.

All routes here are scoped to the authenticated user (`g.user_id`).
No `user_id` is read from query strings, form bodies, or JSON bodies.
"""
from datetime import datetime
import logging

from flask import Blueprint, g, request, jsonify

from models import EmailConfig, User
from models.database import db
from utils.auth import require_auth
from utils.email_service import EmailService

logger = logging.getLogger(__name__)

email_config_bp = Blueprint('email_config', __name__, url_prefix='/api/v1/email-config')


@email_config_bp.route('/status', methods=['GET'])
@require_auth
def get_status():
    """Get email polling status for the authenticated user."""
    user_id = g.user_id

    config = EmailConfig.query.filter_by(user_id=user_id).first()
    
    if not config:
        return jsonify({'configured': False})
    
    return jsonify({
        'configured': True,
        'email_address': config.email_address,
        'provider': config.provider,
        'polling_enabled': config.polling_enabled,
        'polling_interval_minutes': config.polling_interval_minutes,
        'folder_to_watch': config.folder_to_watch,
        'last_poll_time': config.last_poll_time.isoformat() if config.last_poll_time else None,
        'last_successful_poll': config.last_successful_poll.isoformat() if config.last_successful_poll else None,
        'emails_processed': config.emails_processed,
        'last_error': config.last_error
    })


@email_config_bp.route('', methods=['GET'])
@require_auth
def get_config():
    """Get email configuration for the authenticated user."""
    user_id = g.user_id

    config = EmailConfig.query.filter_by(user_id=user_id).first()
    
    if not config:
        return jsonify({'error': 'Configuration not found'}), 404
    
    return jsonify({
        'email_address': config.email_address,
        'provider': config.provider,
        'imap_server': config.imap_server,
        'imap_port': config.imap_port,
        'imap_username': config.imap_username,
        'use_ssl': config.use_ssl,
        'polling_enabled': config.polling_enabled,
        'polling_interval_minutes': config.polling_interval_minutes,
        'folder_to_watch': config.folder_to_watch,
        'mark_as_read': config.mark_as_read
    })


@email_config_bp.route('', methods=['POST'])
@require_auth
def create_config():
    """Create email configuration for the authenticated user."""
    data = request.json or {}
    user_id = g.user_id

    # Check if config already exists
    existing = EmailConfig.query.filter_by(user_id=user_id).first()
    if existing:
        return jsonify({'error': 'Configuration already exists. Use PUT to update.'}), 400

    # Lazy-create the local User row keyed on the Supabase user id. Supabase
    # owns the canonical user record; this is a thin local mirror so the
    # EmailConfig foreign key resolves.
    user = User.query.get(user_id)
    if not user:
        user = User(id=user_id, email=g.user_email or data.get('email_address'))
        db.session.add(user)
    
    config = EmailConfig(
        user_id=user_id,
        email_address=data['email_address'],
        provider=data.get('provider', 'gmail'),
        imap_server=data['imap_server'],
        imap_port=data.get('imap_port', 993),
        imap_username=data.get('imap_username'),
        imap_password=data.get('imap_password'),
        use_ssl=data.get('use_ssl', True),
        polling_enabled=data.get('polling_enabled', False),
        polling_interval_minutes=data.get('polling_interval_minutes', 5),
        folder_to_watch=data.get('folder_to_watch', 'INBOX'),
        mark_as_read=data.get('mark_as_read', True)
    )
    
    db.session.add(config)
    db.session.commit()
    
    logger.info(f"Created email configuration for {config.email_address}")
    
    return jsonify({
        'message': 'Configuration created successfully',
        'id': config.id
    }), 201


@email_config_bp.route('', methods=['PUT'])
@require_auth
def update_config():
    """Update email configuration for the authenticated user."""
    data = request.json or {}
    user_id = g.user_id

    config = EmailConfig.query.filter_by(user_id=user_id).first()
    if not config:
        return jsonify({'error': 'Configuration not found'}), 404
    
    # Update fields if provided
    if 'polling_enabled' in data:
        config.polling_enabled = data['polling_enabled']
    if 'polling_interval_minutes' in data:
        config.polling_interval_minutes = data['polling_interval_minutes']
    if 'folder_to_watch' in data:
        config.folder_to_watch = data['folder_to_watch']
    if 'mark_as_read' in data:
        config.mark_as_read = data['mark_as_read']
    if 'imap_password' in data:
        config.imap_password = data['imap_password']
    if 'imap_server' in data:
        config.imap_server = data['imap_server']
    if 'imap_port' in data:
        config.imap_port = data['imap_port']
    if 'use_ssl' in data:
        config.use_ssl = data['use_ssl']
    
    config.updated_at = datetime.utcnow()
    db.session.commit()
    
    logger.info(f"Updated email configuration for {config.email_address}")
    
    return jsonify({'message': 'Configuration updated successfully'})


@email_config_bp.route('', methods=['DELETE'])
@require_auth
def delete_config():
    """Delete email configuration for the authenticated user."""
    user_id = g.user_id

    config = EmailConfig.query.filter_by(user_id=user_id).first()
    if config:
        db.session.delete(config)
        db.session.commit()
        logger.info(f"Deleted email configuration for {config.email_address}")
    
    return jsonify({'message': 'Configuration deleted successfully'})


@email_config_bp.route('/test', methods=['POST'])
@require_auth
def test_connection():
    """Test IMAP connection using the authenticated user's stored config."""
    user_id = g.user_id

    config = EmailConfig.query.filter_by(user_id=user_id).first()
    if not config:
        return jsonify({'error': 'Configuration not found'}), 404
    
    try:
        service = EmailService(config)
        service.connect()
        service.disconnect()
        
        logger.info(f"Connection test successful for {config.email_address}")
        
        return jsonify({
            'success': True,
            'message': 'Connection successful! ✓'
        })
    except Exception as e:
        logger.error(f"Connection test failed for {config.email_address}: {e}")
        return jsonify({
            'success': False,
            'message': f'Connection failed: {str(e)}'
        }), 400


@email_config_bp.route('/poll-now', methods=['POST'])
@require_auth
def poll_now():
    """Manually trigger email polling for the authenticated user."""
    user_id = g.user_id

    config = EmailConfig.query.filter_by(user_id=user_id).first()
    if not config:
        return jsonify({'error': 'Configuration not found'}), 404
    
    try:
        logger.info(f"Manual polling triggered for {config.email_address}")
        from utils.email_poller import process_user_emails
        result = process_user_emails(config)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Manual polling failed: {e}")
        return jsonify({'error': str(e)}), 500


@email_config_bp.route('/pause', methods=['POST'])
@require_auth
def pause_polling():
    """Pause email polling for the authenticated user."""
    user_id = g.user_id

    config = EmailConfig.query.filter_by(user_id=user_id).first()
    if not config:
        return jsonify({'error': 'Configuration not found'}), 404
    
    config.polling_enabled = False
    config.updated_at = datetime.utcnow()
    db.session.commit()
    
    logger.info(f"Polling paused for {config.email_address}")
    
    return jsonify({'message': 'Polling paused'})


@email_config_bp.route('/resume', methods=['POST'])
@require_auth
def resume_polling():
    """Resume email polling for the authenticated user."""
    user_id = g.user_id

    config = EmailConfig.query.filter_by(user_id=user_id).first()
    if not config:
        return jsonify({'error': 'Configuration not found'}), 404
    
    config.polling_enabled = True
    config.updated_at = datetime.utcnow()
    db.session.commit()
    
    logger.info(f"Polling resumed for {config.email_address}")
    
    return jsonify({'message': 'Polling resumed'})


@email_config_bp.route('/gmail/auth', methods=['GET'])
@require_auth
def gmail_auth():
    """Get Gmail OAuth authorization URL"""
    # TODO: Implement OAuth flow
    return jsonify({
        'error': 'Gmail OAuth not yet implemented. Use IMAP with App Password instead.'
    }), 501


@email_config_bp.route('/gmail/callback', methods=['POST'])
@require_auth
def gmail_callback():
    """Handle Gmail OAuth callback"""
    # TODO: Implement OAuth callback
    return jsonify({
        'error': 'Gmail OAuth not yet implemented. Use IMAP with App Password instead.'
    }), 501


@email_config_bp.route('/gmail/disconnect', methods=['POST'])
@require_auth
def gmail_disconnect():
    """Disconnect Gmail OAuth"""
    # TODO: Implement OAuth disconnect
    return jsonify({
        'error': 'Gmail OAuth not yet implemented. Use IMAP with App Password instead.'
    }), 501
