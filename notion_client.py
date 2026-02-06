"""Notion API client — creates paper pages and checks for duplicates."""

import logging
from datetime import date
from typing import Optional

import requests

from config import NOTION_API_TOKEN, NOTION_DATABASE_ID, DEFAULT_STATUS

logger = logging.getLogger(__name__)

_API_VERSION = "2022-06-28"
_BASE_URL = "https://api.notion.com/v1"


def _headers() -> dict[str, str]:
    """Build auth headers at call time so the token is always current."""
    return {
        "Authorization": f"Bearer {NOTION_API_TOKEN}",
        "Content-Type": "application/json",
        "Notion-Version": _API_VERSION,
    }


# ---------------------------------------------------------------------------
# Property builders — one small helper per Notion property type
# ---------------------------------------------------------------------------


def _prop_title(value: Optional[str]) -> dict:
    return {"title": [{"text": {"content": value or ""}}]}


def _prop_rich_text(value: Optional[str]) -> dict:
    return {"rich_text": [{"text": {"content": value or ""}}]}


def _prop_number(value) -> dict:
    return {"number": value}


def _prop_select(value: Optional[str]) -> dict:
    return {"select": {"name": value} if value else None}


def _prop_multi_select(values) -> dict:
    if isinstance(values, str):
        values = [values]
    return {"multi_select": [{"name": str(v)} for v in (values or [])]}


def _prop_date(iso_date: Optional[str]) -> dict:
    return {"date": {"start": iso_date} if iso_date else None}


def _prop_url(value: Optional[str]) -> dict:
    return {"url": value}


# ---------------------------------------------------------------------------
# Duplicate check
# ---------------------------------------------------------------------------


def _normalize_title(title: str) -> str:
    """Normalize a title for comparison by removing extra whitespace and newlines."""
    import re
    # Replace newlines and multiple spaces with single space
    normalized = re.sub(r'\s+', ' ', title)
    return normalized.strip().lower()


def check_duplicate(title: str, url: Optional[str] = None) -> Optional[str]:
    """Query Notion for a page whose Title matches *title* (case-insensitive).

    Returns the existing page URL if found, else None.
    Failures are non-fatal — logged as a warning and the pipeline continues.
    """
    if not title:
        return None

    logger.info("Checking duplicate for title: %r", title)
    normalized_title = _normalize_title(title)

    try:
        resp = requests.post(
            f"{_BASE_URL}/databases/{NOTION_DATABASE_ID}/query",
            headers=_headers(),
            json={
                "filter": {
                    "property": "Title",
                    "title": {"contains": title[:100]},
                },
                "page_size": 10,  # Increased to catch more potential matches
            },
            timeout=15,
        )
        resp.raise_for_status()

        for page in resp.json().get("results", []):
            title_blocks = (
                page.get("properties", {}).get("Title", {}).get("title", [])
            )
            page_title = title_blocks[0]["text"]["content"] if title_blocks else ""
            normalized_page_title = _normalize_title(page_title)

            if normalized_page_title == normalized_title:
                logger.info("Duplicate found: %s (matched: %r)", page.get("url"), page_title)
                return page.get("url")

    except Exception as exc:  # noqa: BLE001 — must never crash the pipeline
        logger.warning("Duplicate check failed (continuing): %s", exc)

    return None


# ---------------------------------------------------------------------------
# Page creation
# ---------------------------------------------------------------------------


def create_paper_page(
    paper_data: dict,
    source: str,
    pdf_url: Optional[str] = None,
) -> str:
    """Push a paper into the Notion database.

    Args:
        paper_data: Structured dict from ``llm_analyzer.analyze_paper``.
        source:     Label for the Source field (e.g. "PI Recommendation").
        pdf_url:    URL or local path to attach as PDF Link.

    Returns:
        URL of the newly created Notion page.

    Raises:
        RuntimeError: On Notion API errors or network failures.
    """
    title = paper_data.get("title") or "Untitled Paper"

    properties: dict = {
        "Title":           _prop_title(title),
        "Authors":         _prop_rich_text(paper_data.get("authors")),
        "Year":            _prop_number(paper_data.get("year")),
        "Keywords":        _prop_multi_select(paper_data.get("keywords", [])),
        "Main Topics":     _prop_multi_select(paper_data.get("main_topics", [])),
        "Key Findings":    _prop_rich_text(paper_data.get("key_findings")),
        "Methodology":     _prop_rich_text(paper_data.get("methodology")),
        "Relevance Score": _prop_select(paper_data.get("relevance_score")),
        "Research Area":   _prop_select(paper_data.get("research_area")),
        "Status":          _prop_select(DEFAULT_STATUS),
        "Source":          _prop_select(source),
        "Date Added":      _prop_date(date.today().isoformat()),
    }

    if pdf_url:
        properties["PDF Link"] = _prop_url(pdf_url)

    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": properties,
    }

    logger.info("Creating Notion page: %s", title)
    try:
        resp = requests.post(
            f"{_BASE_URL}/pages",
            headers=_headers(),
            json=payload,
            timeout=15,
        )
        if resp.status_code != 200:
            message = resp.json().get("message", resp.text)
            raise RuntimeError(
                f"Notion API {resp.status_code}: {message}\n"
                "  → Verify integration permissions and database ID."
            )

        page_url: str = resp.json().get("url", "")
        logger.info("Created page: %s", page_url)
        return page_url

    except requests.RequestException as exc:
        raise RuntimeError(f"Notion API connection failed: {exc}") from exc
