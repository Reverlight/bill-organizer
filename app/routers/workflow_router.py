import io
import logging
from datetime import datetime, timedelta, timezone

import instructor
import pytesseract
import requests
from fastapi import APIRouter, BackgroundTasks
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from openai import OpenAI
from pdf2image import convert_from_bytes
from PIL import Image
from prefect import flow, task
from sqlalchemy import select

from app import settings
from app.db import async_sessionmaker
from app.models import Receipt
from app.schemas import ProcessRequest, ReceiptData

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/workflows", tags=["receipts"])


# --- mime type to file type mapping ---
MIME_MAP = {
    "application/pdf": "pdf",
    "image/png": "image",
    "image/jpeg": "image",
    "text/plain": "text",
}


# --- tasks ---

import json

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials


def get_drive_creds():
    creds = Credentials.from_authorized_user_info(
        settings.GOOGLE_SERVICE_ACCOUNT_JSON,
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return creds


@task(log_prints=True)
def download_from_google_drive(file_id: str) -> tuple[str, bytes, str]:
    """Download file from Google Drive by file_id. Returns (file_type, bytes, file_name)."""
    print(f"[DRIVE] Downloading file_id: {file_id}")

    creds = get_drive_creds()
    service = build("drive", "v3", credentials=creds)

    meta = service.files().get(fileId=file_id, fields="name,mimeType").execute()
    file_name = meta["name"]
    mime_type = meta["mimeType"]

    file_type = MIME_MAP.get(mime_type)
    if not file_type:
        raise ValueError(f"Unsupported MIME type: {mime_type} for file {file_name}")

    request = service.files().get_media(fileId=file_id)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()

    print(
        f"[DRIVE] Downloaded {file_name} ({mime_type} -> {file_type}), {buffer.tell()} bytes"
    )
    return file_type, buffer.getvalue(), file_name


@task(log_prints=True)
def process_file(file: bytes, file_type: str) -> str:
    """OCR/extract text from file based on type."""
    print(f"[OCR] Processing {file_type}")

    processors = {
        "pdf": process_pdf,
        "text": process_text,
        "image": process_image,
    }
    processor = processors.get(file_type)
    if not processor:
        raise ValueError(f"Unsupported file type: {file_type}")

    text = processor(file)
    print(f"[OCR] Extracted {len(text)} chars")
    return text


@task(log_prints=True)
def llm_parse(text: str) -> dict:
    """Parse receipt text into structured data via instructor + OpenAI."""
    print("[LLM] Parsing text...")

    client = instructor.from_openai(OpenAI(api_key=settings.OPENAI_API_KEY))

    receipt = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        response_model=ReceiptData,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a receipt parser. Extract structured data from the receipt text. "
                    "Normalize dates to ISO format (YYYY-MM-DD). "
                    "Amounts should be floats. "
                    "If a field is not found, leave it as null."
                ),
            },
            {"role": "user", "content": text},
        ],
    )

    data = receipt.model_dump()
    print(f"[LLM] Parsed: {data}")
    return data


@task(log_prints=True)
async def save_receipt(file_id: str, file_name: str, data: dict):
    """Update receipt row with extracted data, set status to completed."""
    print(f"[DB] Saving results for {file_id}")

    async with async_sessionmaker() as session:
        receipt = await session.execute(
            select(Receipt).where(Receipt.file_id == file_id)
        )
        receipt = receipt.scalar_one_or_none()
        if not receipt:
            raise ValueError(f"Receipt row not found for file_id: {file_id}")

        receipt.file_name = file_name
        receipt.vendor = data.get("vendor")
        receipt.date = data.get("date")
        receipt.total = data.get("total")
        receipt.tax = data.get("tax")
        receipt.discount = data.get("discount")
        receipt.currency = data.get("currency")
        receipt.category = data.get("category")
        receipt.payment_method = data.get("payment_method")
        receipt.notes = data.get("notes")
        receipt.status = "completed"
        receipt.processed_at = datetime.now(timezone.utc)

        await session.commit()
        print("[DB] Saved successfully")


@task(log_prints=True, retries=3, retry_delay_seconds=30)
def send_to_n8n(file_id: str, data: dict):
    """POST extracted receipt data back to n8n webhook."""
    print(f"[N8N] Sending results for {file_id}")

    payload = {"file_id": file_id, **data}
    resp = requests.post(settings.N8N_WEBHOOK, json=payload, timeout=30)
    resp.raise_for_status()

    print(f"[N8N] Sent, status {resp.status_code}")


# --- processors ---


def process_pdf(file: bytes) -> str:
    """Convert PDF pages to images, then OCR each page."""
    images = convert_from_bytes(file)
    texts = []
    for i, img in enumerate(images):
        page_text = pytesseract.image_to_string(img)
        texts.append(page_text)
    return "\n\n".join(texts)


def process_text(file: bytes) -> str:
    return file.decode("utf-8")


def process_image(file: bytes) -> str:
    img = Image.open(io.BytesIO(file))
    return pytesseract.image_to_string(img)


# --- db helpers ---


async def mark_failed(file_id: str, error: str):
    """Mark receipt as failed in db."""
    try:
        async with async_sessionmaker() as session:
            result = await session.execute(
                select(Receipt).where(Receipt.file_id == file_id)
            )
            receipt = result.scalar_one_or_none()
            if receipt:
                receipt.status = "failed"
                receipt.error_message = error
                await session.commit()
    except Exception:
        logger.exception(f"[FLOW] Could not update failure status for {file_id}")


PROCESSING_TIMEOUT = timedelta(minutes=2)


async def check_and_insert(file_id: str) -> str | None:
    async with async_sessionmaker() as session:
        result = await session.execute(
            select(Receipt).where(Receipt.file_id == file_id)
        )
        receipt = result.scalar_one_or_none()

        if receipt:
            if receipt.status == "completed":
                return "already_processed"

            if receipt.status == "processing":
                age = datetime.now(timezone.utc) - receipt.created_at
                if age < PROCESSING_TIMEOUT:
                    return "already_processing"
                # stuck — treat as failed, allow reprocessing
                logger.warning(
                    f"[DUP] {file_id} stuck in processing for {age}, reprocessing"
                )

            # failed or stuck -> allow reprocessing
            receipt.status = "processing"
            receipt.error_message = None
            receipt.updated_at = datetime.now(timezone.utc)
            await session.commit()
            return None

        session.add(Receipt(file_id=file_id, status="processing"))
        await session.commit()
        return None


# --- flow ---


@flow(name="receipt-pipeline", log_prints=True)
async def receipt_flow(file_id: str):
    try:
        file_type, file_bytes, file_name = download_from_google_drive(file_id)
        text = process_file(file_bytes, file_type)
        data = llm_parse(text)
        await save_receipt(file_id, file_name, data)
        send_to_n8n(file_id, data)
    except Exception as e:
        logger.exception(f"[FLOW] Failed for {file_id}: {e}")
        await mark_failed(file_id, str(e))
        raise


import asyncio


@router.post("/receipts/process")
async def process_receipt(request: ProcessRequest, background_tasks: BackgroundTasks):
    existing = await check_and_insert(request.file_id)
    if existing:
        return {"status": existing}

    asyncio.ensure_future(receipt_flow(request.file_id))
    return {"status": "processing"}


@router.post("/receipts/test-webhook")
async def test_webhook():
    """Send test data to n8n webhook to verify the connection."""
    import requests

    test_data = {
        "file_id": "test-001",
        "vendor": "ACME GROCERY STORE",
        "date": "2026-03-15",
        "total": 11.31,
        "tax": 0.84,
        "discount": 1.00,
        "currency": "USD",
        "category": "groceries",
        "payment_method": "Visa",
        "notes": "Milk $3.99, Bread $2.49, Eggs $4.99, Discount -$1.00, Tax $0.84",
    }
    print(settings.N8N_WEBHOOK)
    try:
        resp = requests.post(settings.N8N_WEBHOOK, json=test_data, timeout=30)
        return {
            "status": "sent",
            "n8n_status_code": resp.status_code,
            "data": test_data,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
