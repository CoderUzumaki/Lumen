"""Background worker for email polling (Render worker service).

Run: python worker.py
Or deploy as a Render background worker pointing to this entrypoint.
"""
import logging
import os
import time

from dotenv import load_dotenv

load_dotenv()

from config import Config
from utils.logging_config import configure_logging

configure_logging()
logger = logging.getLogger(__name__)

Config.validate()

from app import app  # noqa: E402
from utils.scheduler import scheduler  # noqa: E402

scheduler.app = app
scheduler.interval_seconds = int(os.getenv("EMAIL_POLL_INTERVAL_SECONDS", "300"))
scheduler.start()

logger.info(
    "Email polling worker running (interval=%ss)",
    scheduler.interval_seconds,
)

if __name__ == "__main__":
    while True:
        time.sleep(3600)
