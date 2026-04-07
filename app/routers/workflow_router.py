from fastapi import APIRouter, BackgroundTasks
from prefect import task, flow
import time

router = APIRouter(prefix="/api/workflows", tags=["receipts"])

@task(log_prints=True)
def download_from_google_drive(file_path: str) -> tuple[str, bytes]:
    print(f"[DRIVE] Downloading: {file_path}")
    # TODO: real implementation
    return "pdf", b"binary content"

@task(log_prints=True)
def process_file(file: bytes, file_type: str) -> str:
    print(f"[OCR] Processing {file_type}")
    processors = {
        "pdf":   process_pdf,
        "text":  process_text,
        "image": process_image,
    }
    processor = processors.get(file_type)
    if not processor:
        raise ValueError(f"Unsupported file type: {file_type}")
    return processor(file)

@task(log_prints=True)
def llm_parse(text: str) -> dict:
    print(f"[LLM] Parsing text...")
    time.sleep(1)
    # TODO: real langchain/openai call
    return {"vendor": "Test Store", "amount": 42.00, "date": "2026-04-07"}

@task(log_prints=True)
def save_to_db(data: dict):
    print(f"[DB] Saving: {data}")
    # TODO: real db call

@task(log_prints=True, retries=3, retry_delay_seconds=30)
def send_to_n8n(data: dict):
    print(f"[N8N] Sending: {data}")
    # TODO: requests.post(N8N_WEBHOOK_URL, json=data)

# --- processors (plain functions, no need to be tasks) ---

def process_pdf(file: bytes) -> str:
    return "text from pdf"

def process_text(file: bytes) -> str:
    return file.decode("utf-8")

def process_image(file: bytes) -> str:
    return "text from image"

# --- flow ---

@flow(name="receipt-pipeline", log_prints=True)
def receipt_flow(file_path: str):
    file_type, file = download_from_google_drive(file_path)
    text = process_file(file, file_type)
    data = llm_parse(text)
    save_to_db(data)
    send_to_n8n(data)

# --- endpoint ---

@router.post("/receipts/process")
async def process_receipt(file_path: str, background_tasks: BackgroundTasks):
    background_tasks.add_task(receipt_flow, file_path)
    return {"status": "processing"}