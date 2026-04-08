# 📄 Receipt Pipeline

Automated receipt processing service that extracts structured data from files in Google Drive using OCR and LLM parsing, then pushes results to n8n for downstream automation.

## How it works

1. **Trigger** — POST a Google Drive `file_id` to the API
2. **Download** — File is fetched from Drive (PDF, image, or plain text)
3. **OCR** — Text is extracted via Tesseract
4. **Parse** — OpenAI + Instructor converts raw text into structured receipt data
5. **Save** — Results are stored in the database
6. **Notify** — Extracted data is forwarded to an n8n webhook

## Stack

- **FastAPI** — REST API and request handling
- **Prefect** — Task orchestration and retry logic
- **Tesseract / pdf2image / Pillow** — OCR for PDFs and images
- **Instructor + OpenAI** — Structured LLM extraction
- **SQLAlchemy (async)** — Database layer
- **Google Drive API** — File source
- **n8n** — Downstream webhook consumer

## Extracted fields

`vendor` · `date` · `total` · `tax` · `discount` · `currency` · `category` · `payment_method` · `notes`

## Duplicate handling

| File status | Behavior |
|---|---|
| `completed` | Skipped — returns `already_processed` |
| `processing` (fresh) | Skipped — returns `already_processing` |
| `processing` (stuck >2min) | Re-queued |
| `failed` | Re-queued |
