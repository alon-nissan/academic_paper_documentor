# Academic Paper Management System - Implementation Plan (Manual Processing)

## Project Overview
Build a system to process academic papers and populate a Notion database with AI-extracted metadata, keywords, and summaries.

**Tech Stack:**
- **Database:** Notion (already created)
- **LLM:** Google Gemini (free tier)
- **Input:** Manual file upload (PDF files or URLs)
- **Processing:** Python scripts
- **PDF Extraction:** PyMuPDF

**Workflow:**
1. Your PI emails you a paper
2. You save the PDF or copy the URL
3. Run: `python paper_processor.py --pdf paper.pdf --source "PI Recommendation"`
4. Paper is automatically analyzed and added to Notion database

---

## Phase 1: Manual Setup Actions (YOU DO THIS)

### 1.1 Google Cloud Setup for Gemini API
1. [ ] Go to https://aistudio.google.com/
2. [ ] Sign in with your Google account
3. [ ] Click "Get API Key"
4. [ ] Create a new project (or select existing)
5. [ ] Generate API key
6. [ ] Copy and save the API key securely: `your_gemini_api_key_here`
7. [ ] Note: Free tier = 15 requests/minute, 1500 requests/day

### 1.2 Notion Integration Setup
1. [ ] Go to https://www.notion.so/my-integrations
2. [ ] Click "+ New integration"
3. [ ] Name it "Paper Processor" (or similar)
4. [ ] Select your workspace
5. [ ] Copy the "Internal Integration Token": `your_notion_token_here`
6. [ ] Go to your Academic Papers database: https://www.notion.so/1258f1a8a28945e5bf32e13850787448
7. [ ] Click "..." (three dots) → "Add connections" → Select your integration

### 1.3 Notion Database ID
- [ ] Database ID is already known: `58adebbb-5026-4b09-9882-7a9b47481a19`
- [ ] Verify you can access the database and the integration has permissions

---

## Phase 2: Claude Code Tasks

### Task 2.1: Create Python Processing Script
**File: `paper_processor.py`**

**Requirements:**
- Accept input as PDF file path OR URL (arXiv, journal links)
- Extract text from PDF using PyMuPDF
- For URLs: download PDF first, then extract
- Send extracted text to Gemini API with structured prompt
- Parse LLM response to extract:
  - Title
  - Authors
  - Year
  - Keywords (list)
  - Main Topics (list)
  - Key Findings (summary)
  - Methodology (brief description)
  - Relevance Score suggestion (High/Medium/Low)
  - Research Area suggestion
- Create Notion page with all extracted data
- Handle errors gracefully (malformed PDFs, API failures, etc.)
- Log all operations
- Support batch processing of multiple PDFs

**CLI Usage:**
```bash
# Process single PDF
python paper_processor.py --pdf path/to/paper.pdf --source "PI Recommendation"

# Process PDF from URL
python paper_processor.py --url https://arxiv.org/pdf/2301.12345.pdf --source "Self-found"

# Batch process multiple PDFs in a folder
python paper_processor.py --folder ~/Downloads/papers --source "PI Recommendation"

# Test configuration
python paper_processor.py --test
```

---

### Task 2.2: Create Configuration Management
**File: `config.py`**

**Requirements:**
- Load environment variables from `.env` file
- Store configuration for:
  - Notion API token
  - Notion database ID (data source ID: `58adebbb-5026-4b09-9882-7a9b47481a19`)
  - Gemini API key
  - Default values (status="Inbox", etc.)
- Include validation for required variables
- Provide helpful error messages if config is invalid

**File: `.env.example`**
```
NOTION_API_TOKEN=your_notion_token_here
NOTION_DATABASE_ID=58adebbb-5026-4b09-9882-7a9b47481a19
GEMINI_API_KEY=your_gemini_key_here
```

---

### Task 2.3: Create LLM Prompt Module
**File: `llm_analyzer.py`**

**Requirements:**
- Function to call Gemini API with extracted paper text
- Structured prompt that instructs Gemini to extract:
  - Bibliographic information (title, authors, year)
  - 5-10 keywords relevant to the content
  - 3-5 main topics/themes
  - Key findings (2-3 sentences)
  - Methodology used (1-2 sentences)
  - Suggested relevance score
  - Suggested research area
- Return structured JSON response
- Handle rate limits and retries
- Truncate very long papers to fit within token limits
- Handle papers in different languages (at least detect and note)

**Prompt Template Example:**
```
You are analyzing an academic paper. Extract the following information in JSON format:

{
  "title": "...",
  "authors": "...",
  "year": 2024,
  "keywords": ["keyword1", "keyword2", ...],
  "main_topics": ["topic1", "topic2", ...],
  "key_findings": "...",
  "methodology": "...",
  "relevance_score": "High/Medium/Low",
  "research_area": "Primary Research/Related Field/Methodology/Background"
}

Paper text:
[PAPER_TEXT]
```

---

### Task 2.4: Create PDF Text Extractor
**File: `pdf_extractor.py`**

**Requirements:**
- Extract text from PDF using PyMuPDF (fitz)
- Handle multi-column layouts
- Extract title, abstract, and main body
- Clean extracted text (remove headers/footers, page numbers)
- Return structured text with sections if identifiable
- Handle scanned PDFs gracefully (inform user OCR needed)
- Download PDFs from URLs (arXiv, direct PDF links, common journal sites)
- Extract basic metadata from PDF properties (title, author, creation date)
- Handle password-protected PDFs (inform user and skip)

---

### Task 2.5: Create Notion Integration Module
**File: `notion_client.py`**

**Requirements:**
- Function to create a new page in the Notion database
- Map extracted data to Notion properties:
  - Title → Title field
  - Authors → Authors field (text)
  - Year → Year field (number)
  - Keywords → Keywords field (multi-select, create new options if needed)
  - Main Topics → Main Topics field (multi-select, create new options if needed)
  - Key Findings → Key Findings field (text)
  - Methodology → Methodology field (text)
  - Relevance Score → Relevance Score field (select)
  - Research Area → Research Area field (select)
  - Status → "Inbox" (default)
  - Source → from CLI argument
  - PDF Link → URL if provided, or local file path
  - Date Added → Current date
- Handle Notion API errors with helpful messages
- Return created page URL
- Check for duplicate papers (by title or URL) before creating
- Optionally update existing pages instead of creating duplicates

---

### Task 2.6: Create Requirements File
**File: `requirements.txt`**

**Include:**
```
PyMuPDF>=1.23.0
requests>=2.31.0
python-dotenv>=1.0.0
google-generativeai>=0.3.0
notion-client>=2.2.0
```

---

### Task 2.7: Create README with Setup Instructions
**File: `README.md`**

**Include:**
- Project description and workflow diagram
- Prerequisites (API keys, Python version)
- Installation instructions
- Configuration setup (`.env` file)
- Usage examples with different scenarios
- Troubleshooting common issues
- Tips for organizing papers
- Future enhancement ideas (email automation, etc.)

---

### Task 2.8: Create Batch Processing Helper Script
**File: `batch_process.py`**

**Requirements:**
- Watch a designated folder for new PDFs
- Automatically process any PDFs added to the folder
- Move processed PDFs to "processed" subfolder
- Log all processing activities
- Can run continuously or as one-time batch
- Handle multiple PDFs in parallel (optional, with rate limiting)

**Usage:**
```bash
# Process all PDFs in a folder once
python batch_process.py --folder ~/Downloads/papers --source "PI Recommendation"

# Watch folder continuously
python batch_process.py --watch ~/Downloads/papers --source "PI Recommendation"
```

---

## Phase 3: Manual Final Setup (YOU DO THIS)

### 3.1 Install Python Dependencies
```bash
cd /path/to/project
pip install -r requirements.txt
```

### 3.2 Configure Environment Variables
1. [ ] Copy `.env.example` to `.env`
2. [ ] Fill in your actual API keys and tokens:
   - Notion API token (from Phase 1.2)
   - Gemini API key (from Phase 1.1)
   - Database ID is already set
3. [ ] Save the file

### 3.3 Test Configuration
```bash
python paper_processor.py --test
```
- [ ] Verify all API connections work
- [ ] Check Notion database is accessible
- [ ] Verify Gemini API responds

### 3.4 Test Paper Processing
1. [ ] Download a sample paper PDF (or use one you have)
2. [ ] Run: `python paper_processor.py --pdf sample.pdf --source "Self-found"`
3. [ ] Check Notion database for new entry: https://www.notion.so/1258f1a8a28945e5bf32e13850787448
4. [ ] Verify all fields are populated correctly:
   - Title, Authors, Year
   - Keywords and Main Topics
   - Key Findings and Methodology
   - Relevance Score and Research Area
   - Status = "Inbox"
   - Date Added = today

### 3.5 Test URL Processing
1. [ ] Find an arXiv paper URL (e.g., https://arxiv.org/pdf/2301.12345.pdf)
2. [ ] Run: `python paper_processor.py --url [URL] --source "Self-found"`
3. [ ] Verify it downloads, processes, and creates Notion entry

### 3.6 Set Up Your Workflow
1. [ ] Create a dedicated folder for papers: `~/Papers/ToProcess/`
2. [ ] When PI sends papers:
   - Save PDFs to this folder
   - Or copy URLs to a text file
3. [ ] Run batch processor:
   ```bash
   python batch_process.py --folder ~/Papers/ToProcess/ --source "PI Recommendation"
   ```
4. [ ] Review processed papers in Notion

---

## Phase 4: Testing & Refinement

### 4.1 Test Cases
- [ ] Test with PDF attachment from email
- [ ] Test with arXiv URL
- [ ] Test with direct journal PDF URL
- [ ] Test with multiple PDFs at once (batch)
- [ ] Test with malformed/corrupted PDF
- [ ] Test with very long paper (50+ pages)
- [ ] Test with scanned PDF (should handle gracefully)
- [ ] Test with paper in different language
- [ ] Test duplicate detection (same paper twice)
- [ ] Test Gemini API rate limits (process 20+ papers quickly)

### 4.2 Monitoring & Maintenance
- [ ] Check processing logs regularly
- [ ] Monitor Gemini API usage (stay within free tier)
- [ ] Review processed papers for accuracy
- [ ] Update keywords/topics in Notion as needed
- [ ] Periodically clean up "Inbox" status papers

### 4.3 Optimize Your Workflow
- [ ] Create desktop shortcut/alias for quick processing
- [ ] Set up keyboard shortcut (optional)
- [ ] Consider using Hazel (Mac) or File Juggler (Windows) for automatic folder watching
- [ ] Create templates for common paper types in Notion

---

## Daily Usage Workflow

**When your PI emails you papers:**

1. **Save the PDF** from email to your designated folder (e.g., `~/Papers/ToProcess/`)

2. **Run the processor** (choose one method):
   
   **Method A: Single file**
   ```bash
   python paper_processor.py --pdf ~/Papers/ToProcess/paper.pdf --source "PI Recommendation"
   ```
   
   **Method B: Batch folder**
   ```bash
   python batch_process.py --folder ~/Papers/ToProcess/ --source "PI Recommendation"
   ```
   
   **Method C: From URL**
   ```bash
   python paper_processor.py --url https://arxiv.org/pdf/2301.12345.pdf --source "PI Recommendation"
   ```

3. **Check Notion** - Open your database and see the new entry with all extracted information

4. **Review & Organize** - Update status, add personal notes, adjust relevance score if needed

**That's it!** Takes ~30 seconds per paper.

---

## Future Enhancements (Optional)

Once the manual system is working well, you can add:

- [ ] Email automation (when you're ready to set up domain/email service)
- [ ] Browser extension (right-click PDF → process)
- [ ] Mobile app integration (process from phone)
- [ ] Citation network visualization
- [ ] Paper similarity detection (find related papers)
- [ ] Automatic literature review generation
- [ ] Integration with reference managers (Zotero, Mendeley)
- [ ] Weekly digest email of processed papers
- [ ] Smart recommendations based on your reading history

---

## Project File Structure
```
paper-management-system/
├── README.md
├── requirements.txt
├── .env.example
├── .env (not in git - your secrets)
├── .gitignore
├── paper_processor.py (main CLI tool)
├── batch_process.py (batch/watch folder tool)
├── config.py (configuration management)
├── pdf_extractor.py (PDF text extraction)
├── llm_analyzer.py (Gemini API interaction)
├── notion_client.py (Notion API interaction)
├── logs/ (processing logs)
│   └── paper_processor.log
└── tests/ (unit tests - optional)
    ├── test_pdf_extractor.py
    ├── test_llm_analyzer.py
    └── test_notion_client.py
```

---

## Estimated Timeline

- **Phase 1 (Manual Setup - API Keys):** 15-20 minutes
- **Phase 2 (Claude Code - Python Scripts):** Auto-generated
- **Phase 3 (Installation & Testing):** 30-45 minutes
- **Phase 4 (Testing & Refinement):** 30 minutes

**Total Time to Get Started:** ~1.5-2 hours

**Daily Time per Paper:** ~30 seconds (just run one command)

---

## Support & Troubleshooting

**Common Issues:**

1. **Gemini API rate limits**
   - Free tier = 15 requests/minute, 1500 requests/day
   - Add delays between batch processing
   - Upgrade if you process many papers daily

2. **PDF text extraction fails**
   - May be a scanned PDF - needs OCR
   - Try using Adobe Acrobat or online OCR first
   - Or skip and process manually

3. **Notion API errors**
   - Check integration permissions
   - Verify database ID is correct
   - Make sure integration is connected to database

4. **Gemini returns incomplete data**
   - Paper might be too long (truncated)
   - Try processing abstract/introduction separately
   - Manually fill in missing fields in Notion

5. **Duplicate papers created**
   - Check duplicate detection logic
   - Manually merge in Notion
   - Add paper URL/DOI to improve detection

**Getting Help:**
- Gemini API: https://ai.google.dev/docs
- Notion API: https://developers.notion.com/
- PyMuPDF: https://pymupdf.readthedocs.io/

---

## Tips for Success

1. **Start small** - Process 3-5 papers to test the system
2. **Review results** - Check if extracted keywords/topics are good
3. **Adjust prompts** - Edit `llm_analyzer.py` if needed for better results
4. **Organize Notion** - Create views, filters, and tags that work for you
5. **Be consistent** - Process papers regularly (daily or weekly)
6. **Use batch mode** - More efficient for multiple papers
7. **Keep backups** - Export Notion database monthly

---

## Notes for Claude Code

When implementing, please:
1. Use type hints throughout Python code
2. Include comprehensive error handling with helpful messages
3. Add detailed logging at key points (info, warning, error levels)
4. Write clear docstrings for all functions and classes
5. Follow PEP 8 style guidelines
6. Make the code modular and easy to test
7. Add progress indicators for long operations
8. Handle edge cases gracefully
9. Provide helpful CLI help text and examples
10. Include example .env file with clear comments

**Critical Information:**
- Notion database data source ID: `58adebbb-5026-4b09-9882-7a9b47481a19`
- Use this when creating pages via the Notion API
- Database schema is already defined (see Phase 1.3)
- All fields are described in Task 2.5

**Special Considerations:**
- Handle multi-select fields in Notion (create new options automatically)
- Preserve any manual edits users make in Notion
- Be conservative with API calls (respect rate limits)
- Make CLI output clean and informative
- Support both absolute and relative file paths
