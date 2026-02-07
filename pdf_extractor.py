"""PDF text extraction using PyMuPDF (fitz)."""

import logging
import os
import re
import tempfile
import time
from dataclasses import dataclass, field
from typing import Optional

import fitz  # PyMuPDF
import requests

from config import REQUEST_RETRY_COUNT, REQUEST_RETRY_DELAY

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class ExtractedPaper:
    """All text and metadata pulled from a single PDF."""

    title: Optional[str] = None
    authors: Optional[str] = None
    abstract: Optional[str] = None
    body_text: str = ""
    num_pages: int = 0
    source_path: str = ""
    metadata: dict = field(default_factory=dict)

    @property
    def full_text(self) -> str:
        """Concatenate metadata hints + abstract + body into one string."""
        parts: list[str] = []
        if self.title:
            parts.append(f"Title: {self.title}")
        if self.authors:
            parts.append(f"Authors: {self.authors}")
        if self.abstract:
            parts.append(f"Abstract:\n{self.abstract}")
        if self.body_text:
            parts.append(self.body_text)
        return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------


def download_pdf(url: str) -> str:
    """Download a PDF to a temp file and return its path.

    Automatically converts arXiv /abs/ URLs to /pdf/ export URLs.

    Raises:
        RuntimeError: After all retries are exhausted.
    """
    # Normalise arXiv abstract links → PDF export links
    if "arxiv.org/abs/" in url:
        url = url.replace("/abs/", "/pdf/")
        if not url.endswith(".pdf"):
            url += ".pdf"
        logger.info("Converted arXiv URL → %s", url)

    # Try to convert ScienceDirect abstract URLs to PDF URLs
    # Note: This may still fail due to paywall/authentication
    if "sciencedirect.com" in url and "/abs/" in url:
        url = url.replace("/abs/", "/")
        if not url.endswith("/pdfft"):
            url = url.rstrip("/") + "/pdfft"
        logger.info("Converted ScienceDirect URL → %s", url)
        logger.warning("ScienceDirect PDFs often require subscription access")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/pdf,*/*",
    }
    last_error: Optional[Exception] = None

    for attempt in range(1, REQUEST_RETRY_COUNT + 1):
        try:
            logger.info("Downloading %s (attempt %d)", url, attempt)
            resp = requests.get(url, headers=headers, timeout=30, stream=True)
            resp.raise_for_status()

            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            for chunk in resp.iter_content(chunk_size=8192):
                tmp.write(chunk)
            tmp.close()

            logger.info("Saved to %s", tmp.name)
            return tmp.name

        except requests.RequestException as exc:
            last_error = exc
            logger.warning("Download attempt %d failed: %s", attempt, exc)
            if attempt < REQUEST_RETRY_COUNT:
                time.sleep(REQUEST_RETRY_DELAY)

    # Provide helpful error message based on the error type
    error_msg = f"Download failed after {REQUEST_RETRY_COUNT} attempts: {last_error}"

    # Check for common publisher issues
    if "403" in str(last_error) or "Forbidden" in str(last_error):
        if "sciencedirect.com" in url:
            error_msg += (
                "\n\n  ScienceDirect blocks automated downloads."
                "\n  → Try using the DOI instead: python paper_processor.py --doi 10.xxxx/xxxxx"
                "\n  → Or download the PDF manually and use: python paper_processor.py --pdf file.pdf"
            )
        else:
            error_msg += (
                "\n\n  This URL appears to be blocked (403 Forbidden)."
                "\n  → The paper may be paywalled or behind bot protection"
                "\n  → Try using --doi if you have the paper's DOI"
                "\n  → Or download manually and use --pdf"
            )
    elif "404" in str(last_error):
        error_msg += (
            "\n\n  URL not found (404). Check that the URL is correct."
            "\n  → Make sure it's a direct PDF link, not an abstract page"
        )

    raise RuntimeError(error_msg)


def resolve_doi_to_pdf(doi: str) -> str:
    """Resolve a DOI to a PDF URL using multiple strategies.

    Accepts DOI in any format:
        - 10.1234/example
        - doi:10.1234/example
        - https://doi.org/10.1234/example

    Returns a direct PDF URL if found.

    Raises:
        RuntimeError: If no PDF URL could be found for the DOI.
    """
    # Normalize DOI to just the identifier
    doi_clean = doi.strip()
    if doi_clean.startswith("https://doi.org/"):
        doi_clean = doi_clean.replace("https://doi.org/", "")
    elif doi_clean.startswith("http://doi.org/"):
        doi_clean = doi_clean.replace("http://doi.org/", "")
    elif doi_clean.startswith("doi:"):
        doi_clean = doi_clean.replace("doi:", "")

    logger.info("Resolving DOI: %s", doi_clean)

    # Strategy 1: Try Unpaywall API (free, legal, finds open access PDFs)
    try:
        unpaywall_url = f"https://api.unpaywall.org/v2/{doi_clean}?email=paper-processor@example.com"
        resp = requests.get(unpaywall_url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            # Check for best open access location
            best_oa = data.get("best_oa_location")
            if best_oa and best_oa.get("url_for_pdf"):
                pdf_url = best_oa["url_for_pdf"]
                logger.info("Found PDF via Unpaywall: %s", pdf_url)
                return pdf_url
    except Exception as exc:
        logger.debug("Unpaywall lookup failed: %s", exc)

    # Strategy 2: Try common publisher patterns
    # Many publishers use predictable URL patterns
    patterns = [
        # arXiv
        (r"10\.48550/arXiv\.(\d+\.\d+)", lambda m: f"https://arxiv.org/pdf/{m.group(1)}.pdf"),
        # bioRxiv/medRxiv
        (r"10\.1101/(\d{4}\.\d{2}\.\d{2}\.\d+)", lambda m: f"https://www.biorxiv.org/content/{doi_clean}v1.full.pdf"),
    ]

    for pattern, url_builder in patterns:
        match = re.match(pattern, doi_clean)
        if match:
            pdf_url = url_builder(match)
            logger.info("Constructed PDF URL from DOI pattern: %s", pdf_url)
            return pdf_url

    # Strategy 3: Follow DOI redirect and look for PDF link
    # This is a last resort and may not always work
    try:
        doi_url = f"https://doi.org/{doi_clean}"
        resp = requests.get(doi_url, timeout=10, allow_redirects=True)
        if resp.status_code == 200:
            # Check if the response itself is a PDF
            content_type = resp.headers.get("Content-Type", "")
            if "pdf" in content_type.lower():
                logger.info("DOI resolved directly to PDF")
                # Download to temp file
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
                tmp.write(resp.content)
                tmp.close()
                return tmp.name

            # Try to find PDF link in the HTML
            text = resp.text.lower()
            # Look for common PDF link patterns
            pdf_patterns = [
                r'href=["\']([^"\']*\.pdf[^"\']*)["\']',
                r'href=["\']([^"\']*download[^"\']*pdf[^"\']*)["\']',
            ]
            for pattern in pdf_patterns:
                matches = re.findall(pattern, resp.text)
                if matches:
                    pdf_link = matches[0]
                    # Make absolute URL if needed
                    if pdf_link.startswith("http"):
                        logger.info("Found PDF link on landing page: %s", pdf_link)
                        return pdf_link
    except Exception as exc:
        logger.debug("DOI redirect lookup failed: %s", exc)

    raise RuntimeError(
        f"Could not resolve DOI {doi_clean} to a PDF URL.\n"
        f"  → This may be a paywalled paper without open access.\n"
        f"  → Try downloading the PDF manually and using --pdf instead.\n"
        f"  → Or check the paper at: https://doi.org/{doi_clean}"
    )


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------


def _clean_text(text: str) -> str:
    """Remove PDF artifacts: ligatures, excessive blank lines, trailing spaces."""
    for src, dst in [("ﬁ", "fi"), ("ﬂ", "fl"), ("ﬀ", "ff"), ("ﬃ", "ffi"), ("ﬄ", "ffl")]:
        text = text.replace(src, dst)
    text = re.sub(r"\n{3,}", "\n\n", text)  # collapse blank lines
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    return text.strip()


def _detect_abstract(text: str) -> Optional[str]:
    """Heuristically locate the abstract section."""
    pattern = (
        r"(?i)(?:^|\n)\s*(?:Abstract|ABSTRACT|Summary)\s*:?\s*\n?"
        r"(.*?)"
        r"(?=\n\s*(?:Keywords|KEYWORDS|1\.\s|Introduction|INTRODUCTION)|\Z)"
    )
    match = re.search(pattern, text, re.DOTALL)
    if match:
        candidate = _clean_text(match.group(1))
        if len(candidate) > 50:
            return candidate
    return None


def _detect_title(text: str, pdf_meta_title: Optional[str]) -> Optional[str]:
    """Pick title from PDF metadata, falling back to the first meaningful line."""
    if pdf_meta_title and len(pdf_meta_title.strip()) > 3:
        return pdf_meta_title.strip()
    for line in text.split("\n"):
        stripped = line.strip()
        if len(stripped) > 5:
            return stripped
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_text_from_pdf(pdf_path: str) -> ExtractedPaper:
    """Read a local PDF and return structured text + metadata.

    Raises:
        FileNotFoundError: Path does not exist.
        RuntimeError: PDF is encrypted, unreadable, or appears to be scanned.
    """
    pdf_path = os.path.abspath(pdf_path)
    if not os.path.isfile(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    logger.info("Opening %s", pdf_path)
    try:
        doc = fitz.open(pdf_path)
    except Exception as exc:
        raise RuntimeError(f"Cannot open PDF: {exc}") from exc

    if doc.is_encrypted:
        if not doc.authenticate(""):
            doc.close()
            raise RuntimeError(
                f"PDF is password-protected: {pdf_path}\n"
                "  → Unlock it before processing."
            )

    num_pages = len(doc)
    meta = doc.metadata or {}

    # Pull text from every page
    page_texts: list[str] = []
    for page in doc:
        t = page.get_text("text")
        if t.strip():
            page_texts.append(t)

    doc.close()

    raw = "\n\n".join(page_texts)

    # Guard against scanned / image-only PDFs
    if len(raw.strip()) < 100 and num_pages > 0:
        raise RuntimeError(
            f"Only {len(raw.strip())} characters extracted from {num_pages} pages — "
            "this PDF is likely scanned and needs OCR.\n"
            "  → Try uploading to Google Docs or an online OCR tool first."
        )

    cleaned = _clean_text(raw)

    return ExtractedPaper(
        title=_detect_title(cleaned, meta.get("title")),
        authors=meta.get("author"),
        abstract=_detect_abstract(cleaned),
        body_text=cleaned,
        num_pages=num_pages,
        source_path=pdf_path,
        metadata=meta,
    )
