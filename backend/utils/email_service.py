"""Email polling and processing service"""
import imaplib
import email
from email.message import Message
import os
import tempfile
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import logging

from utils.crypto import decrypt_secret

logger = logging.getLogger(__name__)


class EmailService:
    """Service for connecting to and reading emails via IMAP"""

    def __init__(self, config):
        self.config = config
        self.imap = None

    def connect(self):
        """Connect to IMAP server"""
        try:
            if self.config.use_ssl:
                self.imap = imaplib.IMAP4_SSL(self.config.imap_server, self.config.imap_port)
            else:
                self.imap = imaplib.IMAP4(self.config.imap_server, self.config.imap_port)

            username = self.config.imap_username or self.config.email_address
            password = decrypt_secret(self.config.imap_password)
            self.imap.login(username, password)
            logger.info(f"Successfully connected to {self.config.imap_server}")
            return True
        except Exception as e:
            logger.error(f"IMAP connection failed: {e}")
            raise
    
    def disconnect(self):
        """Disconnect from IMAP server"""
        if self.imap:
            try:
                self.imap.logout()
                logger.info("Disconnected from IMAP server")
            except Exception as e:
                logger.error(f"Error disconnecting: {e}")
    
    def fetch_new_emails(self, since_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Fetch unread emails with attachments"""
        try:
            self.imap.select(self.config.folder_to_watch)
            
            # Search criteria - look for unseen emails
            search_criteria = '(UNSEEN)'
            if since_date:
                date_str = since_date.strftime("%d-%b-%Y")
                search_criteria = f'(UNSEEN SINCE {date_str})'
            
            status, message_ids = self.imap.search(None, search_criteria)
            
            if status != 'OK':
                logger.warning(f"Search failed with status: {status}")
                return []
            
            email_ids = message_ids[0].split()
            logger.info(f"Found {len(email_ids)} unread emails")
            
            emails = []
            
            for email_id in email_ids:
                try:
                    email_data = self._fetch_email(email_id)
                    if email_data and email_data['attachments']:
                        emails.append(email_data)
                except Exception as e:
                    logger.error(f"Error processing email {email_id}: {e}")
            
            logger.info(f"Found {len(emails)} emails with invoice attachments")
            return emails
            
        except Exception as e:
            logger.error(f"Error fetching emails: {e}")
            return []
    
    def _fetch_email(self, email_id: bytes) -> Optional[Dict[str, Any]]:
        """Fetch single email with attachments"""
        try:
            status, msg_data = self.imap.fetch(email_id, '(RFC822)')
            
            if status != 'OK':
                return None
            
            email_message = email.message_from_bytes(msg_data[0][1])
            
            email_data = {
                'id': email_id.decode(),
                'subject': email_message.get('Subject', ''),
                'from': email_message.get('From', ''),
                'date': email_message.get('Date', ''),
                'attachments': []
            }
            
            # Extract attachments
            for part in email_message.walk():
                if part.get_content_maintype() == 'multipart':
                    continue
                if part.get('Content-Disposition') is None:
                    continue
                
                filename = part.get_filename()
                if filename:
                    logger.debug(f"Found attachment: {filename}")
                    if self._is_invoice_attachment(filename):
                        logger.info(f"Processing invoice attachment: {filename}")
                        email_data['attachments'].append({
                            'filename': filename,
                            'content': part.get_payload(decode=True)
                        })
                    else:
                        logger.debug(f"Skipped attachment (not invoice): {filename}")
            
            return email_data if email_data['attachments'] else None
            
        except Exception as e:
            logger.error(f"Error fetching email: {e}")
            return None
    
    def _is_invoice_attachment(self, filename: str) -> bool:
        """Check if attachment is likely an invoice"""
        # Accept all common image and PDF formats
        valid_extensions = ['.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.tif', '.bmp', '.webp', '.gif']
        
        filename_lower = filename.lower()
        has_valid_ext = any(filename_lower.endswith(ext) for ext in valid_extensions)
        
        logger.debug(f"Checking {filename}: valid_ext={has_valid_ext}")
        return has_valid_ext
    
    def mark_as_read(self, email_id: str):
        """Mark email as read"""
        try:
            self.imap.store(email_id.encode(), '+FLAGS', '\\Seen')
            logger.debug(f"Marked email {email_id} as read")
        except Exception as e:
            logger.error(f"Error marking email as read: {e}")
