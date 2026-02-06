"""Configuration management — loads settings from .env."""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the same directory as this file
load_dotenv(Path(__file__).resolve().parent / ".env")

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Required
# ---------------------------------------------------------------------------
NOTION_API_TOKEN: str = os.getenv("NOTION_API_TOKEN", "")
NOTION_DATABASE_ID: str = os.getenv("NOTION_DATABASE_ID", "")
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

# ---------------------------------------------------------------------------
# Defaults / tuning
# ---------------------------------------------------------------------------
DEFAULT_STATUS: str = "Inbox"
GEMINI_MODEL: str = "gemini-2.5-flash"
MAX_TEXT_LENGTH: int = 30_000  # chars forwarded to Gemini (fits free-tier context)
REQUEST_RETRY_COUNT: int = 3
REQUEST_RETRY_DELAY: float = 2.0  # base back-off in seconds
LOG_FILE: str = str(Path(__file__).resolve().parent / "logs" / "paper_processor.log")


def validate_config() -> list[str]:
    """Return a list of human-readable errors for any missing required vars.

    An empty list means the configuration is valid.
    """
    errors: list[str] = []
    if not NOTION_API_TOKEN:
        errors.append(
            "NOTION_API_TOKEN is not set.\n"
            "  → Get it at https://www.notion.so/my-integrations\n"
            "  → Add it to your .env file"
        )
    if not NOTION_DATABASE_ID:
        errors.append(
            "NOTION_DATABASE_ID is not set.\n"
            "  → Add it to your .env file"
        )
    if not GEMINI_API_KEY:
        errors.append(
            "GEMINI_API_KEY is not set.\n"
            "  → Get it at https://aistudio.google.com/\n"
            "  → Add it to your .env file"
        )
    return errors
