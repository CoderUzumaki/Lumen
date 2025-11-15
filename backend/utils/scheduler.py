"""Background task scheduler for email polling"""
import threading
import time
import logging
from datetime import datetime
from flask import Flask

logger = logging.getLogger(__name__)


class EmailPollingScheduler:
    """Background scheduler for periodic email polling"""
    
    def __init__(self, app: Flask = None, interval_seconds: int = 60):
        self.app = app
        self.interval_seconds = interval_seconds
        self.running = False
        self.thread = None
    
    def start(self):
        """Start the polling scheduler"""
        if self.running:
            logger.warning("Scheduler already running")
            return
        
        if not self.app:
            logger.error("Flask app not configured for scheduler")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        logger.info(f"✅ Email polling scheduler started (interval: {self.interval_seconds}s)")
    
    def stop(self):
        """Stop the polling scheduler"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("Email polling scheduler stopped")
    
    def _run(self):
        """Main polling loop"""
        # Wait a bit before first poll to let app start up
        time.sleep(10)
        
        while self.running:
            try:
                with self.app.app_context():
                    logger.info("🔄 Starting email polling cycle...")
                    from utils.email_poller import poll_all_users
                    
                    results = poll_all_users()
                    
                    # Log summary
                    total_processed = sum(r.get('processed', 0) for r in results)
                    total_errors = sum(r.get('errors', 0) for r in results)
                    
                    logger.info(
                        f"✅ Polling cycle complete: {len(results)} users, "
                        f"{total_processed} invoices processed, {total_errors} errors"
                    )
                    
            except Exception as e:
                logger.error(f"❌ Polling cycle failed: {e}", exc_info=True)
            
            # Wait for next cycle
            time.sleep(self.interval_seconds)


# Global scheduler instance
scheduler = EmailPollingScheduler(interval_seconds=60)  # Poll every 60 seconds
