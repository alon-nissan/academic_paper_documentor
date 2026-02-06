"""Batch-process a folder of PDFs, or watch it continuously for new arrivals."""

import argparse
import logging
import shutil
import sys
import time
from pathlib import Path

from config import validate_config
from paper_processor import setup_logging, process_single_paper

logger = logging.getLogger(__name__)


def _processed_dir(folder: Path) -> Path:
    """Ensure and return the 'processed' sub-directory."""
    d = folder / "processed"
    d.mkdir(exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# One-shot batch
# ---------------------------------------------------------------------------


def batch(folder_path: str, source: str, recursive: bool = False) -> dict[str, int]:
    """Process all PDFs once, moving successes into processed/.

    Args:
        folder_path: Directory to search.
        source: Source label for papers.
        recursive: If True, search subdirectories recursively.
    """
    folder = Path(folder_path)
    if not folder.is_dir():
        print(f"ERROR — not a directory: {folder_path}")
        sys.exit(1)

    proc_dir = _processed_dir(folder)
    pdfs = sorted(folder.rglob("*.pdf") if recursive else folder.glob("*.pdf"))
    counts = {"success": 0, "failed": 0}

    if not pdfs:
        search_desc = "recursively" if recursive else ""
        print(f"No PDFs found in {folder_path} {search_desc}".strip())
        return counts

    search_desc = "(including subdirectories)" if recursive else ""
    print(f"\nProcessing {len(pdfs)} PDF(s) from {folder_path} {search_desc}\n".strip())

    for i, pdf in enumerate(pdfs, 1):
        # Show relative path for recursive searches
        display_path = str(pdf.relative_to(folder)) if recursive else pdf.name
        print(f"\n[{i}/{len(pdfs)}] {display_path}")
        if process_single_paper(str(pdf), source):
            counts["success"] += 1
            # Preserve relative structure in processed/ folder when recursive
            if recursive:
                rel_path = pdf.relative_to(folder)
                dest = proc_dir / rel_path
                dest.parent.mkdir(parents=True, exist_ok=True)
            else:
                dest = proc_dir / pdf.name
            shutil.move(str(pdf), str(dest))
            print(f"  → Moved to processed/{dest.relative_to(proc_dir)}")
        else:
            counts["failed"] += 1
        if i < len(pdfs):
            time.sleep(2)  # Gemini rate-limit courtesy

    print(f"\nDone — {counts['success']} ok, {counts['failed']} failed")
    return counts


# ---------------------------------------------------------------------------
# Continuous watch
# ---------------------------------------------------------------------------


def watch(folder_path: str, source: str, interval: int = 10, recursive: bool = False) -> None:
    """Poll *folder_path* for new PDFs every *interval* seconds.

    Args:
        folder_path: Directory to watch.
        source: Source label for papers.
        interval: Seconds between scans.
        recursive: If True, watch subdirectories recursively.
    """
    folder = Path(folder_path)
    if not folder.is_dir():
        print(f"ERROR — not a directory: {folder_path}")
        sys.exit(1)

    proc_dir = _processed_dir(folder)
    # Track by full relative path to handle recursive properly
    seen: set[str] = {str(p.relative_to(proc_dir)) for p in proc_dir.rglob("*.pdf")}

    search_desc = "(including subdirectories)" if recursive else ""
    print(f"\nWatching {folder_path} {search_desc} (poll every {interval}s) … Ctrl+C to stop\n".strip())

    while True:
        current_pdfs = folder.rglob("*.pdf") if recursive else folder.glob("*.pdf")
        current_paths = {str(p.relative_to(folder)): p for p in current_pdfs}
        new = sorted(set(current_paths.keys()) - seen)

        for rel_path_str in new:
            pdf_path = current_paths[rel_path_str]
            print(f"\nNew PDF: {rel_path_str}")
            if process_single_paper(str(pdf_path), source):
                # Preserve directory structure in processed/
                dest = proc_dir / rel_path_str
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(pdf_path), str(dest))
                seen.add(rel_path_str)
                print(f"  → Moved to processed/{rel_path_str}")
            else:
                print(f"  → Failed — will retry on next scan")
        time.sleep(interval)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    setup_logging()

    parser = argparse.ArgumentParser(
        prog="batch_process",
        description="Batch-process or watch a folder for academic PDFs.",
        epilog=(
            "Examples:\n"
            "  python batch_process.py --folder ~/Papers --source \"PI Recommendation\"\n"
            "  python batch_process.py --folder ~/Papers -r --source \"PI Recommendation\"\n"
            "  python batch_process.py --watch ~/Papers --source \"Conference\"\n"
            "  python batch_process.py --watch ~/Papers -r --source \"Conference\""
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--folder",   metavar="PATH", help="Process all PDFs once and move to processed/.")
    group.add_argument("--watch",    metavar="PATH", help="Watch folder continuously for new PDFs.")
    parser.add_argument("--source",   default="Self-found", help='Source label (default: "Self-found").')
    parser.add_argument("--interval", type=int, default=10, help="Watch poll interval in seconds (default: 10).")
    parser.add_argument("-r", "--recursive", action="store_true", help="Search subdirectories recursively.")

    args = parser.parse_args()

    errs = validate_config()
    if errs:
        print("Configuration errors:")
        for e in errs:
            print(f"  • {e}")
        sys.exit(1)

    if args.folder:
        batch(args.folder, args.source, recursive=args.recursive)
    else:
        watch(args.watch, args.source, args.interval, recursive=args.recursive)


if __name__ == "__main__":
    main()
