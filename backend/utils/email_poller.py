"""Background email polling service"""
import logging
import tempfile
import os
from datetime import datetime, timedelta
from models import EmailConfig, Receipt, Transaction
from models.database import db
from utils.email_service import EmailService
from utils.image_processing import image_to_base64, convert_pdf_to_images, pil_image_to_bytes
from utils.openrouter import extract_and_structure_with_openrouter
from utils.normalize import normalize_transaction
from utils.save_transaction import save_transaction

logger = logging.getLogger(__name__)


def process_user_emails(config: EmailConfig) -> dict:
    """Process emails for a single user"""
    service = None
    processed_count = 0
    error_count = 0
    
    try:
        logger.info(f"Starting email polling for {config.email_address}")
        service = EmailService(config)
        service.connect()
        
        # Fetch emails since last poll (or last 7 days if never polled)
        since_date = config.last_poll_time or datetime.utcnow() - timedelta(days=7)
        emails = service.fetch_new_emails(since_date)
        
        logger.info(f"📧 Found {len(emails)} emails with invoice attachments for {config.email_address}")
        
        if len(emails) == 0:
            logger.warning(f"⚠️  No emails with attachments found. Check if there are unread emails with image/PDF attachments in {config.folder_to_watch}")
        
        for email_data in emails:
            logger.info(f"Processing email: {email_data['subject']} from {email_data['from']}")
            
            for attachment in email_data['attachments']:
                try:
                    logger.info(f"Processing attachment: {attachment['filename']}")
                    
                    # Process attachment
                    result = process_invoice_attachment(
                        attachment['content'],
                        attachment['filename'],
                        config.user_id,
                        email_data
                    )
                    
                    if result['success']:
                        processed_count += 1
                        logger.info(f"Successfully processed invoice: {attachment['filename']}")
                    else:
                        error_count += 1
                        logger.error(f"Failed to process invoice: {result.get('error', 'Unknown error')}")
                        
                except Exception as e:
                    logger.error(f"Error processing attachment {attachment['filename']}: {e}")
                    error_count += 1
            
            # Mark as read if configured
            if config.mark_as_read:
                try:
                    service.mark_as_read(email_data['id'])
                except Exception as e:
                    logger.error(f"Failed to mark email as read: {e}")
        
        # Update config status
        config.last_poll_time = datetime.utcnow()
        config.last_successful_poll = datetime.utcnow()
        config.emails_processed += processed_count
        config.last_error = None
        db.session.commit()
        
        logger.info(f"Polling complete: {processed_count} processed, {error_count} errors")
        
        return {
            'success': True,
            'processed': processed_count,
            'errors': error_count,
            'total_emails': len(emails),
            'emails_checked': len(emails),
            'invoices_created': processed_count
        }
        
    except Exception as e:
        logger.error(f"Email polling failed for {config.email_address}: {e}")
        db.session.rollback()  # Rollback failed transaction
        try:
            config.last_poll_time = datetime.utcnow()
            config.last_error = str(e)
            db.session.commit()
        except:
            db.session.rollback()
        return {
            'success': False,
            'error': str(e),
            'processed': processed_count,
            'errors': error_count,
            'emails_checked': 0,
            'invoices_created': processed_count
        }
    
    finally:
        if service:
            service.disconnect()


def process_invoice_attachment(content: bytes, filename: str, user_id: str, email_data: dict) -> dict:
    """Process a single invoice attachment"""
    try:
        file_ext = os.path.splitext(filename)[1].lower().replace('.', '')
        
        logger.info(f"Processing {file_ext} file: {filename}")
        
        # Determine media type
        media_type_map = {
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'gif': 'image/gif',
            'bmp': 'image/bmp',
            'webp': 'image/webp',
            'pdf': 'application/pdf'
        }
        
        # Process based on file type
        if file_ext == 'pdf':
            # Convert PDF to images and process first page
            logger.info("Converting PDF to images...")
            images = convert_pdf_to_images(content)
            
            if not images:
                return {'success': False, 'error': 'No pages found in PDF', 'filename': filename}
            
            first_page = images[0]
            img_bytes = pil_image_to_bytes(first_page, format='PNG')
            image_base64 = image_to_base64(img_bytes)
            media_type = 'image/png'
            
            logger.info("Extracting data from PDF with AI...")
            structured_data = extract_and_structure_with_openrouter(image_base64, media_type)
            
        elif file_ext in media_type_map:
            # Process image directly
            logger.info(f"Extracting data from {file_ext} image with AI...")
            image_base64 = image_to_base64(content)
            media_type = media_type_map[file_ext]
            
            structured_data = extract_and_structure_with_openrouter(image_base64, media_type)
        else:
            return {
                'success': False,
                'error': f'Unsupported file format: {file_ext}',
                'filename': filename
            }
        
        # Add source metadata
        structured_data['source_file'] = filename
        structured_data['file_type'] = file_ext
        structured_data['source'] = 'email'
        
        # Normalize the data
        logger.info("Normalizing transaction data...")
        normalized = normalize_transaction(structured_data)
        
        # Save to database
        logger.info("Saving to database...")
        transaction_id = save_transaction(user_id, normalized)
        
        if transaction_id:
            logger.info(f"✅ Saved transaction {transaction_id} for invoice: {filename}")
            return {
                'success': True,
                'transaction_id': transaction_id,
                'filename': filename
            }
        else:
            return {
                'success': False,
                'error': 'Failed to save transaction to database',
                'filename': filename
            }
        
    except Exception as e:
        logger.error(f"Error processing invoice {filename}: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'filename': filename
        }


def poll_all_users():
    """Poll emails for all users with enabled configs"""
    logger.info("Starting polling cycle for all users...")
    
    configs = EmailConfig.query.filter_by(polling_enabled=True).all()
    
    logger.info(f"Found {len(configs)} users with polling enabled")
    
    results = []
    for config in configs:
        try:
            result = process_user_emails(config)
            results.append({
                'user_id': config.user_id,
                'email': config.email_address,
                **result
            })
        except Exception as e:
            logger.error(f"Failed to poll for user {config.user_id}: {e}")
            results.append({
                'user_id': config.user_id,
                'email': config.email_address,
                'success': False,
                'error': str(e)
            })
    
    logger.info(f"Polling cycle complete: {len(results)} users processed")
    return results
