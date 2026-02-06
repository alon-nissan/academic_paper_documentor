"""paper_processor — main CLI entry point for processing academic papers."""

import argparse
import logging
import os
import sys
import time
from typing import Optional

import config
from config import validate_config, LOG_FILE
from pdf_extractor import ExtractedPaper, extract_text_from_pdf, download_pdf, resolve_doi_to_pdf
from llm_analyzer import analyze_paper
from notion_client import create_paper_page, check_duplicate


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


def setup_logging() -> None:
    """Wire up file + console logging."""
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # Detailed file log
    fh = logging.FileHandler(LOG_FILE)
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))

    # Concise console log
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))

    root.addHandler(fh)
    root.addHandler(ch)


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Config test
# ---------------------------------------------------------------------------


def test_configuration() -> bool:
    """Smoke-test every external dependency.  Returns True when all pass."""
    print("\n=== Configuration Test ===\n")

    # 1. Environment variables
    errors = validate_config()
    if errors:
        print("FAIL — missing config:")
        for e in errors:
            print(f"  • {e}")
        return False
    print("PASS — environment variables set")

    # 2. Notion connectivity
    try:
        import requests

        resp = requests.get(
            f"https://api.notion.com/v1/databases/{config.NOTION_DATABASE_ID}",
            headers={
                "Authorization": f"Bearer {config.NOTION_API_TOKEN}",
                "Notion-Version": "2022-06-28",
            },
            timeout=10,
        )
        resp.raise_for_status()
        print("PASS — Notion database accessible")
    except Exception as exc:
        print(f"FAIL — Notion: {exc}")
        return False

    # 3. Gemini connectivity
    try:
        import google.generativeai as genai

        genai.configure(api_key=config.GEMINI_API_KEY)
        model = genai.GenerativeModel(config.GEMINI_MODEL)
        reply = model.generate_content("Reply with just: OK")
        print(f"PASS — Gemini responding ({reply.text.strip()[:20]})")
    except Exception as exc:
        print(f"FAIL — Gemini: {exc}")
        return False

    print("\n=== All checks passed — ready to process papers ===\n")
    return True


# ---------------------------------------------------------------------------
# Core processing
# ---------------------------------------------------------------------------


def process_single_paper(input_path: str, source: str, *, is_url: bool = False) -> bool:
    """Full pipeline for one paper: download? → extract → dedupe → analyse → create.

    Returns True on success (including harmless skips like duplicates).
    """
    pdf_path: Optional[str] = None
    downloaded = False

    try:
        # --- obtain PDF ---
        if is_url:
            print("  Downloading PDF…")
            pdf_path = download_pdf(input_path)
            downloaded = True
        else:
            pdf_path = os.path.abspath(input_path)
            if not os.path.isfile(pdf_path):
                print(f"  ERROR — file not found: {pdf_path}")
                return False

        # --- extract ---
        print("  Extracting text…")
        paper: ExtractedPaper = extract_text_from_pdf(pdf_path)
        print(f"  → {len(paper.full_text):,} chars, {paper.num_pages} pages")

        # --- duplicate guard ---
        if paper.title:
            dup_url = check_duplicate(paper.title)
            if dup_url:
                print(f"  SKIP — duplicate already in Notion: {dup_url}")
                return True

        # --- LLM analysis ---
        print("  Analysing with Gemini…")
        analysis = analyze_paper(paper.full_text)

        # Fall back to PDF-level metadata when Gemini misses fields
        if not analysis.get("title") and paper.title:
            analysis["title"] = paper.title
        if not analysis.get("authors") and paper.authors:
            analysis["authors"] = paper.authors

        print(f"    Title   : {analysis.get('title', '—')}")
        print(f"    Authors : {analysis.get('authors', '—')}")
        print(f"    Year    : {analysis.get('year', '—')}")
        print(f"    Keywords: {', '.join(analysis.get('keywords', []))}")

        # --- push to Notion ---
        print("  Creating Notion page…")
        pdf_link = input_path if is_url else pdf_path
        page_url = create_paper_page(analysis, source, pdf_url=pdf_link)
        print(f"  DONE — {page_url}")
        return True

    except (FileNotFoundError, RuntimeError) as exc:
        print(f"  ERROR — {exc}")
        logger.error("Failed: %s", exc, exc_info=True)
        return False
    finally:
        if downloaded and pdf_path and os.path.exists(pdf_path):
            os.unlink(pdf_path)


# ---------------------------------------------------------------------------
# Batch helper (also used by batch_process.py)
# ---------------------------------------------------------------------------


def process_folder(folder_path: str, source: str, recursive: bool = False) -> dict[str, int]:
    """Process every PDF in *folder_path* sequentially.

    Args:
        folder_path: Directory to search for PDFs.
        source: Source label for papers.
        recursive: If True, search subdirectories recursively.

    Returns {"success": N, "failed": N}.
    """
    from pathlib import Path

    folder = Path(folder_path)
    if not folder.is_dir():
        print(f"ERROR — not a directory: {folder_path}")
        return {"success": 0, "failed": 0}

    # Use rglob for recursive search, glob for non-recursive
    pdfs = sorted(folder.rglob("*.pdf") if recursive else folder.glob("*.pdf"))
    if not pdfs:
        search_type = "recursively" if recursive else ""
        print(f"No PDFs found in {folder_path} {search_type}".strip())
        return {"success": 0, "failed": 0}

    counts = {"success": 0, "failed": 0}
    search_desc = "(including subdirectories)" if recursive else ""
    print(f"\nBatch: {len(pdfs)} PDF(s) in {folder_path} {search_desc}\n".strip())

    for i, pdf in enumerate(pdfs, 1):
        print(f"\n[{i}/{len(pdfs)}] {pdf.name}")
        if process_single_paper(str(pdf), source):
            counts["success"] += 1
        else:
            counts["failed"] += 1
        if i < len(pdfs):
            time.sleep(2)  # respect Gemini rate limits

    print(f"\nBatch done — {counts['success']} ok, {counts['failed']} failed")
    return counts


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="paper_processor",
        description="Process academic papers and add them to a Notion database.",
        epilog=(
            "Examples:\n"
            "  python paper_processor.py --pdf paper.pdf --source \"PI Recommendation\"\n"
            "  python paper_processor.py --url https://arxiv.org/abs/2301.12345\n"
            "  python paper_processor.py --doi 10.1234/example --source \"Self-found\"\n"
            "  python paper_processor.py --folder ~/Papers --source \"Conference\"\n"
            "  python paper_processor.py --folder ~/Papers -r --source \"Conference\"\n"
            "  python paper_processor.py --test"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument("--pdf",    metavar="PATH", help="Single PDF file to process.")
    group.add_argument("--url",    metavar="URL",  help="Paper URL (arXiv, direct PDF link).")
    group.add_argument("--doi",    metavar="DOI",  help="Paper DOI (e.g., 10.1234/example or https://doi.org/10.1234/example).")
    group.add_argument("--folder", metavar="PATH", help="Directory of PDFs to batch-process.")
    group.add_argument("--test",   action="store_true", help="Test configuration and API connections.")

    parser.add_argument(
        "--source", default="Self-found",
        help='How the paper was discovered (default: "Self-found").',
    )
    parser.add_argument(
        "-r", "--recursive", action="store_true",
        help="When used with --folder, search subdirectories recursively.",
    )
    return parser


def main() -> None:
    setup_logging()
    args = _build_parser().parse_args()

    if not any([args.pdf, args.url, args.doi, args.folder, args.test]):
        _build_parser().print_help()
        sys.exit(1)

    if not args.test:
        errs = validate_config()
        if errs:
            print("Configuration errors — run  python paper_processor.py --test  for details:")
            for e in errs:
                print(f"  • {e}")
            sys.exit(1)

    if args.test:
        sys.exit(0 if test_configuration() else 1)
    elif args.pdf:
        sys.exit(0 if process_single_paper(args.pdf, args.source) else 1)
    elif args.url:
        sys.exit(0 if process_single_paper(args.url, args.source, is_url=True) else 1)
    elif args.doi:
        # Resolve DOI to PDF URL, then process it
        try:
            print(f"Resolving DOI: {args.doi}")
            pdf_url = resolve_doi_to_pdf(args.doi)
            sys.exit(0 if process_single_paper(pdf_url, args.source, is_url=True) else 1)
        except RuntimeError as e:
            print(f"ERROR — {e}")
            sys.exit(1)
    elif args.folder:
        result = process_folder(args.folder, args.source, recursive=args.recursive)
        sys.exit(0 if result["failed"] == 0 else 1)


if __name__ == "__main__":
    main()
