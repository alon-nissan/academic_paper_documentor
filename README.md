# Academic Paper Management System

Automatically extract metadata from academic papers and populate a Notion database using Google Gemini AI.

## How it works

1. You drop a PDF (or paste a URL)
2. One command extracts text, runs it through Gemini, and creates a Notion page
3. Your database stays organised with zero manual entry

```
PDF / URL  →  extract text  →  Gemini analysis  →  Notion page
```

---

## Prerequisites

- Python 3.9+
- A [Notion](https://notion.so) workspace with an existing database
- A Notion integration token ([create one here](https://www.notion.so/my-integrations))
- A Gemini API key ([get one here](https://aistudio.google.com/))

---

## Installation

```bash
cd /path/to/paper_documentor
pip install -r requirements.txt
```

---

## Configuration

```bash
cp .env.example .env
```

Open `.env` and fill in the three values:

| Variable | Where to find it |
|---|---|
| `NOTION_API_TOKEN` | [Notion Integrations page](https://www.notion.so/my-integrations) |
| `NOTION_DATABASE_ID` | Already set to your database ID in `.env.example` |
| `GEMINI_API_KEY` | [AI Studio](https://aistudio.google.com/) → Get API Key |

Make sure your Notion integration is **connected** to the target database (open the database → `...` → Add connections → select the integration).

---

## Usage

### Verify everything is wired up

```bash
python paper_processor.py --test
```

### Process a single PDF

```bash
python paper_processor.py --pdf paper.pdf --source "PI Recommendation"
```

### Process a paper from a URL (arXiv, direct PDF links)

```bash
python paper_processor.py --url https://arxiv.org/abs/2301.12345 --source "Self-found"
```

### Process a paper from a DOI

```bash
# Accepts various DOI formats
python paper_processor.py --doi 10.1234/example --source "Self-found"
python paper_processor.py --doi https://doi.org/10.1234/example --source "Self-found"
python paper_processor.py --doi doi:10.1234/example --source "Self-found"
```

The system will attempt to resolve the DOI to a PDF URL using:
1. **Unpaywall API** (for open access papers)
2. **Publisher-specific patterns** (arXiv, bioRxiv, etc.)
3. **DOI redirect following** (for direct PDF links)

If the paper is paywalled, you'll get a helpful error message with the DOI URL to check manually.

### Batch-process a folder

```bash
# Process PDFs in a single folder
python paper_processor.py --folder ~/Papers/ToProcess --source "PI Recommendation"

# Process PDFs recursively (including subdirectories)
python paper_processor.py --folder ~/Papers/ToProcess -r --source "PI Recommendation"
```

### Watch a folder for new PDFs (runs continuously)

```bash
# Watch a single folder
python batch_process.py --watch ~/Papers/ToProcess --source "PI Recommendation"

# Watch recursively (including subdirectories)
python batch_process.py --watch ~/Papers/ToProcess -r --source "PI Recommendation"
```

Successfully processed PDFs are automatically moved to a `processed/` subfolder. When using `-r` (recursive), the original directory structure is preserved in the `processed/` folder.

---

## What gets extracted

Each paper produces a Notion page with:

| Field | Description |
|---|---|
| **Title** | Full paper title |
| **Authors** | Comma-separated author list |
| **Year** | Publication year |
| **Keywords** | 5–10 subject terms (multi-select) |
| **Main Topics** | 3–5 broader themes (multi-select) |
| **Key Findings** | 2–3 sentence summary |
| **Methodology** | Brief method description |
| **Relevance Score** | High / Medium / Low |
| **Research Area** | Primary Research / Related Field / Methodology / Background |
| **Status** | Set to "Inbox" — update as you review |
| **Source** | How you found the paper |
| **Date Added** | Today's date |
| **PDF Link** | URL or file path |

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `"Only N characters extracted"` | The PDF is scanned/image-based. Run it through OCR first (Google Docs upload works). |
| DOI cannot be resolved to PDF | Paper may be paywalled. Download the PDF manually and use `--pdf` instead. |
| Notion 403 / permission error | Make sure the integration is connected to the database (see Configuration above). |
| Gemini rate-limit error | Free tier = 15 req/min. The processor adds a 2-second pause between batch items; for large batches, split into smaller runs. |
| Duplicate paper added | Detection is title-based. If titles differ slightly, duplicates slip through — merge manually in Notion. |
| Empty or garbled Gemini response | Very long papers get truncated. Re-run; if it persists, the paper may have unusual formatting. |

---

## File layout

```
paper_documentor/
├── paper_processor.py    # Main CLI — single file, URL, or folder processing
├── batch_process.py      # Folder-watch mode with auto-move
├── config.py             # Loads and validates .env
├── pdf_extractor.py      # PDF → text (PyMuPDF)
├── llm_analyzer.py       # Text → structured metadata (Gemini)
├── notion_client.py      # Metadata → Notion page
├── requirements.txt      # Python dependencies
├── .env.example          # Template for API keys
├── .env                  # Your keys (never committed)
└── logs/
    └── paper_processor.log
```

---

## Rate limits

| Service | Limit (free tier) | Notes |
|---|---|---|
| Gemini | 15 req/min, 1 500/day | Batch mode adds 2 s delay between papers |
| Notion | 3 req/s per integration | No issues at normal volume |

---

## Suggested workflow

1. Create `~/Papers/ToProcess/`
2. When a paper arrives, drop the PDF in that folder
3. Run `python batch_process.py --folder ~/Papers/ToProcess --source "PI Recommendation"`
4. Open Notion — review and triage from the Inbox
