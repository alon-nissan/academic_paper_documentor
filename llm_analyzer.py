"""Gemini-powered paper analysis — extracts structured metadata from text."""

import json
import logging
import re
import time
from typing import Optional

import google.generativeai as genai

from config import GEMINI_API_KEY, GEMINI_MODEL, MAX_TEXT_LENGTH, REQUEST_RETRY_COUNT, REQUEST_RETRY_DELAY

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

_PROMPT_TEMPLATE = """\
You are analyzing an academic paper. Extract the following information and \
return it as valid JSON only — no markdown fences, no explanations.

{{
  "title": "<full title>",
  "authors": "<comma-separated author names>",
  "year": <4-digit integer or null>,
  "keywords": ["kw1", "kw2", ...],
  "main_topics": ["topic1", "topic2", ...],
  "key_findings": "<2-3 sentences summarising main findings>",
  "methodology": "<1-2 sentences describing the method>",
  "relevance_score": "High | Medium | Low",
  "research_area": "Primary Research | Related Field | Methodology | Background",
  "language": "<detected language>"
}}

Rules:
- keywords : 5-10 concise terms that capture the core subjects
- main_topics : 3-5 broader thematic areas
- relevance_score : High = cutting-edge / directly relevant; Low = tangential
- research_area : how this paper fits into a research portfolio
- Use null for any field that cannot be determined
- year must be an integer, not a string

---

Paper text (may be truncated for long papers):

{paper_text}"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _truncate(text: str) -> str:
    """Keep the first 80 % and last 20 % of the allowed length so both the
    introduction *and* the conclusions are available to the model."""
    if len(text) <= MAX_TEXT_LENGTH:
        return text
    head = int(MAX_TEXT_LENGTH * 0.8)
    tail = MAX_TEXT_LENGTH - head
    logger.info(
        "Truncating %d chars → %d (head %d + tail %d)",
        len(text), MAX_TEXT_LENGTH, head, tail,
    )
    return text[:head] + "\n\n[…text truncated…]\n\n" + text[-tail:]


def _parse_response(raw: str) -> dict:
    """Strip any markdown fences and parse the JSON body."""
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned)
    cleaned = re.sub(r"\n?```\s*$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Gemini returned invalid JSON — try re-running the command.\n"
            f"  → {exc}"
        ) from exc


def _normalise(data: dict) -> dict:
    """Ensure all expected keys exist and lists are actually lists."""
    data.setdefault("title", None)
    data.setdefault("authors", None)
    data.setdefault("year", None)
    data.setdefault("keywords", [])
    data.setdefault("main_topics", [])
    data.setdefault("key_findings", "")
    data.setdefault("methodology", "")
    data.setdefault("relevance_score", "Medium")
    data.setdefault("research_area", "Background")
    data.setdefault("language", "English")

    # Gemini sometimes returns comma-separated strings instead of lists
    for key in ("keywords", "main_topics"):
        if isinstance(data[key], str):
            data[key] = [item.strip() for item in data[key].split(",") if item.strip()]

    return data


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def analyze_paper(paper_text: str) -> dict:
    """Send paper text to Gemini and return structured metadata.

    Raises:
        RuntimeError: If all retries are exhausted or JSON parsing fails.
    """
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(GEMINI_MODEL)

    prompt = _PROMPT_TEMPLATE.format(paper_text=_truncate(paper_text))
    last_error: Optional[Exception] = None

    for attempt in range(1, REQUEST_RETRY_COUNT + 1):
        try:
            logger.info("Gemini call attempt %d (model=%s)", attempt, GEMINI_MODEL)
            response = model.generate_content(prompt)

            if not response.text:
                raise RuntimeError("Gemini returned an empty response")

            result = _normalise(_parse_response(response.text))
            logger.info("Analysis OK — title=%r", result.get("title"))
            return result

        except RuntimeError:
            raise  # parse errors / empty responses → fail fast
        except Exception as exc:
            last_error = exc
            logger.warning("Attempt %d failed: %s", attempt, exc)
            if attempt < REQUEST_RETRY_COUNT:
                delay = REQUEST_RETRY_DELAY * (2 ** (attempt - 1))
                logger.info("Retrying in %.1f s…", delay)
                time.sleep(delay)

    raise RuntimeError(
        f"Gemini API failed after {REQUEST_RETRY_COUNT} attempts: {last_error}"
    )
