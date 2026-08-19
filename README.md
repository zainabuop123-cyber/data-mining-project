# AI Invoice & Receipt Parser Agent

A complete, working application that converts invoice and receipt PDFs or images
into validated records in a relational database, using a multimodal Vision AI
for extraction and an independent mathematical engine to verify every total
before anything is saved.

```
PDF/Image Upload
  → Document Processing
  → Multimodal Vision AI Extraction
  → Structured JSON
  → Pydantic Validation
  → Business and Mathematical Validation
  → Save Only Valid Records to SQLite
  → Display Results in Streamlit
```

---

## 1. Problem

Manually entering invoice and receipt data into a bookkeeping system is slow
and error-prone. AI vision models can read documents, but they can also
misread numbers, invent values, or silently hallucinate a total that doesn't
actually add up — which is dangerous in a financial context.

## 2. Solution

This app treats the Vision AI as a **fast first-pass reader, not a source of
truth**. Every document it reads goes through three independent checks before
anything touches the database:

1. **Schema validation** (Pydantic) — is the data well-typed and structurally sound?
2. **Business validation** — are required fields present, are amounts sensible (no negative totals), is the data internally consistent?
3. **Calculation validation** — recompute every line subtotal and the grand total *from scratch*, using `Decimal` arithmetic, and compare against what the AI extracted. If they disagree by more than a configurable tolerance, the document is rejected.

Only documents that pass all three checks (status `VALID`) are written to
SQLite. Everything else is shown to the user with a clear explanation of what
went wrong, and is never silently saved.

## 3. Architecture

```
InvoiceAgent                    (agent/document_agent.py — coordinates everything)
├── DocumentProcessor           (services/document_processor.py)
│     Validates & rasterizes PDFs (PyMuPDF) / images (Pillow) into PNG pages
├── VisionExtractor             (services/vision_service.py)
│     Calls a multimodal Vision AI (OpenAI-compatible) with a strict JSON-only prompt
├── SchemaValidator              (services/validation_service.py)
│     Raw JSON → strict ExtractedDocument (Pydantic), catches type/format errors
├── BusinessValidator            (services/validation_service.py)
│     Required fields, negative-value checks, consistency checks
├── CalculationValidator         (services/calculation_service.py)
│     Independent re-verification of every subtotal and the grand total
└── DatabaseService               (services/database_service.py)
      Transactional SQLite persistence (SQLAlchemy), search/filter, rollback on failure
```

The Streamlit UI (`app.py`) only handles presentation — it calls
`InvoiceAgent.process_and_save()` and renders whatever comes back. No business
logic lives in the UI layer.

### Project structure

```
ai_document_parser/
├── app.py                                 Streamlit application (2 pages)
├── requirements.txt
├── README.md
├── .env.example
├── .gitignore
├── pytest.ini
├── config/
│   └── settings.py                        Loads all config from .env
├── models/
│   ├── document_models.py                 Pydantic models (extraction + validation)
│   └── database_models.py                 SQLAlchemy ORM models
├── services/
│   ├── document_processor.py              File validation + PDF/image → PNG
│   ├── vision_service.py                  Multimodal Vision AI wrapper
│   ├── validation_service.py              SchemaValidator + BusinessValidator
│   ├── calculation_service.py             CalculationValidator (math re-check)
│   └── database_service.py                SQLite persistence layer
├── agent/
│   └── document_agent.py                  InvoiceAgent — pipeline coordinator
├── database/
│   ├── database.py                        SQLAlchemy engine/session setup
│   └── schema.sql                         Reference DDL (auto-created at runtime too)
├── utils/
│   ├── helpers.py                         Small shared utilities
│   └── exceptions.py                      Custom exception hierarchy
├── sample_data/
│   ├── valid_invoice.pdf                  Sample invoice (correct totals)
│   ├── invalid_invoice_wrong_total.pdf    Sample invoice (deliberately wrong total)
│   └── *_expected_extraction.json         Reference extraction JSON for each sample
├── uploads/                               Scratch space for uploaded files
└── tests/
    ├── conftest.py                        Shared fixtures
    ├── test_validation.py
    ├── test_calculations.py
    ├── test_database.py
    ├── test_document_processing.py
    └── test_vision_service.py             (mocked — no real API key needed)
```

## 4. Technologies

| Purpose              | Library                          |
|-----------------------|-----------------------------------|
| UI                     | Streamlit                        |
| Data validation        | Pydantic v2                      |
| PDF rendering           | PyMuPDF (`pymupdf`, imported as `fitz`) |
| Image handling          | Pillow                           |
| Database ORM            | SQLAlchemy 2.x + SQLite          |
| Vision AI                | OpenAI SDK (or any OpenAI-compatible endpoint) |
| Config                    | python-dotenv                    |
| Testing                    | pytest                           |

## 5. Installation

### 5.1 Prerequisites
- Python 3.10+
- A Vision AI API key (OpenAI, or any OpenAI-compatible multimodal provider)

### 5.2 Set up a virtual environment

```bash
cd ai_document_parser
python3 -m venv venv

# macOS/Linux
source venv/bin/activate
# Windows
venv\Scripts\activate
```

### 5.3 Install dependencies

```bash
pip install -r requirements.txt
```

### 5.4 Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and set at minimum:

```
VISION_API_KEY=sk-your-real-key-here
VISION_MODEL=gpt-4o-mini
DATABASE_URL=sqlite:///documents.db
```

`VISION_MODEL` can be any vision-capable chat-completions model your provider
exposes. If you're using a non-OpenAI, OpenAI-compatible endpoint (Azure
OpenAI, a proxy, a local gateway, etc.), also set `VISION_BASE_URL`.

**Never commit your `.env` file** — it's already excluded via `.gitignore`.

## 6. Running the app

```bash
streamlit run app.py
```

Streamlit will print a local URL (typically `http://localhost:8501`). Open it
in your browser. The SQLite database and its tables are created automatically
on first run — no manual migration step is needed.

### Using the app

1. **Process Document** page: upload a PDF/PNG/JPG/JPEG invoice or receipt, click **Process Document**, and watch the pipeline run stage by stage (upload → AI extraction → schema validation → business validation → calculation check → save).
2. Review the result: document info, every extracted line item, the financial summary, and the calculated-vs-extracted total comparison.
3. If the status is `VALID`, the record is automatically saved and you'll see a confirmation with its database ID.
4. **Saved Documents** page: search/filter by document number, vendor, type, date range, or status, then select any row to see the full record with line items.

## 7. Running the tests

```bash
pytest
```

or, for verbose per-test output:

```bash
pytest -v
```

The test suite (37 tests) covers:

- `test_validation.py` — schema validation (valid docs, unparseable fields, null-not-invented values) and business rules (negative amounts, missing line items, paid > total)
- `test_calculations.py` — a correct invoice passing, an incorrect total being rejected, multi-line-item summation, rounding tolerance acceptance/rejection, discounts
- `test_database.py` — saving + retrieving a valid document, refusing to save an INVALID one, duplicate-document rejection, search/filter, transaction rollback on failure
- `test_document_processing.py` — valid PNG/JPG/multi-page PDF processing, empty files, unsupported extensions, oversized files, corrupt files, filename sanitization
- `test_vision_service.py` — **mocked** Vision API calls (no real key or network needed) covering missing-key errors, malformed JSON, markdown-fence stripping, rate limits, auth errors, and timeouts

All tests use an isolated temporary SQLite database or mocked services, so
running them never touches your real `documents.db` or makes real API calls.

## 8. Database

SQLite is used by default (`sqlite:///documents.db`, created automatically),
with two related tables:

**`documents`** — one row per invoice/receipt: type, number, date,
vendor/customer details, currency, all financial totals, validation
status/message, source filename, and timestamps. A unique constraint on
`(document_number, vendor_name)` prevents duplicate saves.

**`document_items`** — one row per line item, foreign-keyed to `documents`
with `ON DELETE CASCADE`: product name, description, SKU, quantity, unit
price, discount, tax, subtotal.

Every save happens inside a single transaction (see
`database/database.get_session`), so a failure partway through can never
leave a document with some line items written and others missing — the whole
write rolls back.

**Switching to PostgreSQL** later only requires changing `DATABASE_URL` in
`.env` (e.g. `postgresql://user:pass@host:5432/dbname`) and installing
`psycopg2-binary` — no application code needs to change, since all database
access goes through SQLAlchemy.

## 9. Sample invoice

`sample_data/valid_invoice.pdf` contains this invoice, which the app should
mark **VALID**:

```
2 laptops × 50,000 = 100,000
2 mice    ×  2,000 =   4,000
Subtotal            = 104,000
Tax                  =  10,400
Grand Total          = 114,400
Currency             = PKR
```

`sample_data/invalid_invoice_wrong_total.pdf` has the same structure but a
deliberately wrong grand total on the document (99,999 instead of the correct
33,000), which the app should mark **INVALID** with a calculation-mismatch
error.

Each sample also ships with a `*_expected_extraction.json` reference file
showing what the Vision AI is expected to return for that document — useful
for sanity-checking your provider/model choice, though the app itself never
reads these files; it always calls the live Vision API.

## 10. Expected output (valid sample)

After processing `valid_invoice.pdf`, you should see:

- **Status:** ✅ VALID
- **Document #:** INV-2026-001, dated 2026-08-01
- **Vendor:** TechWorld Traders
- **2 line items:** Laptop (2 × 50,000), Wireless Mouse (2 × 2,000)
- **Calculated total:** PKR 114,400.00 — matches the extracted total exactly (difference: 0.00, within tolerance)
- **Saved to database** with a confirmation message and record ID

## 11. Limitations

- Extraction quality depends entirely on the underlying Vision AI model and image/scan quality — very low-resolution scans or unusual layouts may produce more `NEEDS_REVIEW` results.
- OCR fallback for scanned documents is not implemented yet; all pages are sent directly to the multimodal model as images (the codebase is structured to add a traditional-OCR fallback in `document_processor.py` later without touching other modules).
- Only a single currency per document is supported (no multi-currency line items).
- Duplicate detection is based on `(document_number, vendor_name)` — a vendor that reuses invoice numbers across years could produce false-positive duplicates.

## 12. Future improvements

- Add an OCR fallback (e.g. Tesseract) for documents a vision model can't read well.
- Support batch upload (multiple files processed in one run).
- Add a manual-correction UI for `NEEDS_REVIEW` documents so users can fix and re-save them instead of re-uploading.
- Export saved documents to CSV/Excel.
- Multi-currency support with exchange-rate normalization for reporting.

## 13. Common errors and troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| "No Vision API key configured" | `VISION_API_KEY` missing/blank in `.env` | Add a real key and restart the app |
| "The Vision API rejected the configured key" | Wrong/revoked API key | Check the key in your provider's dashboard |
| "The Vision API did not respond in time" | Network issue or provider outage | Retry; check `VISION_TIMEOUT_SECONDS` |
| "The Vision API rate limit was exceeded" | Too many requests too fast | Wait and retry; consider a higher-tier plan |
| "The Vision API did not return valid JSON" | Model ignored the JSON-only instruction | Try a different/more capable vision model |
| Document always comes back `NEEDS_REVIEW` | Vendor name / document number / date not visible or misread | Check the source scan quality; these are warnings, not blockers, if the math otherwise checks out |
| Document comes back `INVALID` on a total mismatch | The document's printed total doesn't match its own line items, or the AI misread a number | Compare "Calculated total" vs "Extracted total" shown in the UI to see the discrepancy |
| "A document with number '...' from vendor '...' already exists" | Duplicate save attempt | This is expected behavior — the document was already saved previously |
| `ModuleNotFoundError` on startup | Dependencies not installed / wrong virtual environment active | Re-run `pip install -r requirements.txt` inside the activated venv |

---

## Quick reference: install & run

```bash
cd ai_document_parser
python3 -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env    # then edit .env and set VISION_API_KEY
streamlit run app.py
```

## Quick reference: test

```bash
pytest -v
```
