from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

from app.factories import ReceiptFactory
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Receipt
from app.routers.workflow_router import (
    check_and_insert,
    mark_failed,
    process_file,
    process_image,
    process_pdf,
    process_text,
    receipt_flow,
)


# --- mock data ---

MOCK_LLM_RESPONSE = {
    "vendor": "ACME GROCERY STORE",
    "date": "2026-03-15",
    "total": 11.31,
    "tax": 0.84,
    "discount": 1.00,
    "currency": "USD",
    "category": "groceries",
    "payment_method": "Visa",
    "notes": None,
}


# --- helper: get receipt by file_id ---


async def get_receipt_by_file_id(session: AsyncSession, file_id: str) -> Receipt | None:
    result = await session.execute(
        select(Receipt).where(Receipt.file_id == file_id)
    )
    return result.scalar_one_or_none()


# --- helper: patch async_sessionmaker to reuse the test session ---


@pytest.fixture
def patch_sessionmaker(async_db: AsyncSession):
    """
    Patch async_sessionmaker in workflow_router so all DB ops
    (check_and_insert, save_receipt, mark_failed) use the test session.
    """

    @asynccontextmanager
    async def fake_sessionmaker():
        yield async_db

    with patch("app.routers.workflow_router.async_sessionmaker", fake_sessionmaker):
        yield


# --- file fixtures ---


@pytest.fixture
def jpeg_bytes() -> bytes:
    from pathlib import Path

    return (Path(__file__).parent / "fixtures" / "receipt.jpg").read_bytes()


@pytest.fixture
def png_bytes() -> bytes:
    from pathlib import Path

    return (Path(__file__).parent / "fixtures" / "receipt.png").read_bytes()


@pytest.fixture
def pdf_bytes() -> bytes:
    from pathlib import Path

    return (Path(__file__).parent / "fixtures" / "receipt.pdf").read_bytes()


@pytest.fixture
def text_bytes() -> bytes:
    return (
        "ACME GROCERY STORE\n"
        "Date: 2026-03-15\n"
        "Milk $3.99\n"
        "Total $11.31\n"
        "Payment: Visa\n"
    ).encode("utf-8")


# ============================================================
# Unit tests: OCR processors
# ============================================================


class TestProcessors:
    """Test OCR processors directly — real tesseract, no mocks."""

    def test_process_text_decodes_utf8(self, text_bytes: bytes):
        result = process_text(text_bytes)
        assert "ACME GROCERY STORE" in result
        assert "Total $11.31" in result

    def test_process_image_jpeg(self, jpeg_bytes: bytes):
        result = process_image(jpeg_bytes)
        assert "ACME" in result
        assert "Total" in result

    def test_process_image_png(self, png_bytes: bytes):
        result = process_image(png_bytes)
        assert "ACME" in result
        assert "Total" in result

    def test_process_pdf(self, pdf_bytes: bytes):
        result = process_pdf(pdf_bytes)
        assert "ACME" in result
        assert "Total" in result

    def test_process_file_routes_pdf(self, pdf_bytes: bytes):
        result = process_file.fn(pdf_bytes, "pdf")
        assert "ACME" in result

    def test_process_file_routes_image(self, jpeg_bytes: bytes):
        result = process_file.fn(jpeg_bytes, "image")
        assert "ACME" in result

    def test_process_file_routes_text(self, text_bytes: bytes):
        result = process_file.fn(text_bytes, "text")
        assert "ACME" in result

    def test_process_file_raises_on_unknown_type(self):
        with pytest.raises(ValueError, match="Unsupported file type"):
            process_file.fn(b"data", "docx")


# ============================================================
# Unit tests: duplicate detection
# ============================================================


class TestDuplicateDetection:

    @pytest.mark.asyncio
    async def test_new_file_inserts_processing_row(
        self, async_db: AsyncSession, patch_sessionmaker
    ):
        result = await check_and_insert("new-file-001")
        assert result is None

        receipt = await get_receipt_by_file_id(async_db, "new-file-001")
        assert receipt is not None
        assert receipt.status == "processing"

    @pytest.mark.asyncio
    async def test_completed_file_returns_already_processed(
        self, async_db: AsyncSession, patch_sessionmaker
    ):
        await ReceiptFactory.create(async_db, file_id="done-001", status="completed")

        result = await check_and_insert("done-001")
        assert result == "already_processed"

    @pytest.mark.asyncio
    async def test_processing_file_returns_already_processing(
        self, async_db: AsyncSession, patch_sessionmaker
    ):
        await ReceiptFactory.create(async_db, file_id="busy-001", status="processing")

        result = await check_and_insert("busy-001")
        assert result == "already_processing"

    @pytest.mark.asyncio
    async def test_failed_file_allows_reprocessing(
        self, async_db: AsyncSession, patch_sessionmaker
    ):
        await ReceiptFactory.create(
            async_db, file_id="fail-001", status="failed", error_message="old error"
        )

        result = await check_and_insert("fail-001")
        assert result is None

        receipt = await get_receipt_by_file_id(async_db, "fail-001")
        await async_db.refresh(receipt)
        assert receipt.status == "processing"
        assert receipt.error_message is None


# ============================================================
# Integration tests: endpoint
# ============================================================


class TestProcessReceiptEndpoint:

    @pytest.mark.asyncio
    async def test_new_file_returns_processing(
        self, async_client: AsyncClient, async_db: AsyncSession, patch_sessionmaker
    ):
        with patch(
            "app.routers.workflow_router.receipt_flow",
            new=AsyncMock(),
        ):
            response = await async_client.post(
                "/api/workflows/receipts/process",
                params={"file_id": "drive-001"},
            )

        assert response.status_code == 200
        assert response.json()["status"] == "processing"

        receipt = await get_receipt_by_file_id(async_db, "drive-001")
        assert receipt is not None
        assert receipt.status == "processing"

    @pytest.mark.asyncio
    async def test_completed_duplicate_skips_flow(
        self, async_client: AsyncClient, async_db: AsyncSession, patch_sessionmaker
    ):
        await ReceiptFactory.create(async_db, file_id="drive-002", status="completed")

        with patch(
            "app.routers.workflow_router.receipt_flow",
            new=AsyncMock(),
        ) as mock_flow:
            response = await async_client.post(
                "/api/workflows/receipts/process",
                params={"file_id": "drive-002"},
            )

        assert response.status_code == 200
        assert response.json()["status"] == "already_processed"
        mock_flow.assert_not_called()

    @pytest.mark.asyncio
    async def test_processing_duplicate_skips_flow(
        self, async_client: AsyncClient, async_db: AsyncSession, patch_sessionmaker
    ):
        await ReceiptFactory.create(async_db, file_id="drive-003", status="processing")

        with patch(
            "app.routers.workflow_router.receipt_flow",
            new=AsyncMock(),
        ) as mock_flow:
            response = await async_client.post(
                "/api/workflows/receipts/process",
                params={"file_id": "drive-003"},
            )

        assert response.status_code == 200
        assert response.json()["status"] == "already_processing"
        mock_flow.assert_not_called()

    @pytest.mark.asyncio
    async def test_failed_file_reprocesses(
        self, async_client: AsyncClient, async_db: AsyncSession, patch_sessionmaker
    ):
        await ReceiptFactory.create(
            async_db, file_id="drive-004", status="failed", error_message="old"
        )

        with patch(
            "app.routers.workflow_router.receipt_flow",
            new=AsyncMock(),
        ):
            response = await async_client.post(
                "/api/workflows/receipts/process",
                params={"file_id": "drive-004"},
            )

        assert response.status_code == 200
        assert response.json()["status"] == "processing"


# ============================================================
# Integration tests: full flow (mocked drive + LLM + n8n)
# ============================================================


class TestReceiptFlow:

    @pytest.mark.asyncio
    async def test_full_flow_saves_extracted_data(
        self, async_db: AsyncSession, patch_sessionmaker, pdf_bytes: bytes
    ):
        file_id = "flow-001"
        await ReceiptFactory.create(async_db, file_id=file_id, status="processing")

        with (
            patch(
                "app.routers.workflow_router.download_from_google_drive",
                return_value=("pdf", pdf_bytes, "receipt.pdf"),
            ),
            patch(
                "app.routers.workflow_router.llm_parse",
                return_value=MOCK_LLM_RESPONSE,
            ),
            patch(
                "app.routers.workflow_router.send_to_n8n",
            ) as mock_n8n,
        ):
            await receipt_flow.fn(file_id)

        receipt = await get_receipt_by_file_id(async_db, file_id)
        await async_db.refresh(receipt)
        assert receipt.status == "completed"
        assert receipt.vendor == "ACME GROCERY STORE"
        assert receipt.total == 11.31
        assert receipt.tax == 0.84
        assert receipt.discount == 1.00
        assert receipt.currency == "USD"
        assert receipt.date == "2026-03-15"
        assert receipt.payment_method == "Visa"
        assert receipt.file_name == "receipt.pdf"
        assert receipt.processed_at is not None

        mock_n8n.assert_called_once_with(file_id, MOCK_LLM_RESPONSE)

    @pytest.mark.asyncio
    async def test_flow_marks_failed_on_drive_error(
        self, async_db: AsyncSession, patch_sessionmaker
    ):
        file_id = "flow-fail-001"
        await ReceiptFactory.create(async_db, file_id=file_id, status="processing")

        with (
            patch(
                "app.routers.workflow_router.download_from_google_drive",
                side_effect=ValueError("Drive API error: not found"),
            ),
            pytest.raises(ValueError, match="Drive API error"),
        ):
            await receipt_flow.fn(file_id)

        receipt = await get_receipt_by_file_id(async_db, file_id)
        await async_db.refresh(receipt)
        assert receipt.status == "failed"
        assert "Drive API error" in receipt.error_message

    @pytest.mark.asyncio
    async def test_flow_marks_failed_on_llm_error(
        self, async_db: AsyncSession, patch_sessionmaker, jpeg_bytes: bytes
    ):
        file_id = "flow-fail-002"
        await ReceiptFactory.create(async_db, file_id=file_id, status="processing")

        with (
            patch(
                "app.routers.workflow_router.download_from_google_drive",
                return_value=("image", jpeg_bytes, "receipt.jpg"),
            ),
            patch(
                "app.routers.workflow_router.llm_parse",
                side_effect=ValueError("Invalid JSON from OpenAI"),
            ),
            pytest.raises(ValueError, match="Invalid JSON"),
        ):
            await receipt_flow.fn(file_id)

        receipt = await get_receipt_by_file_id(async_db, file_id)
        await async_db.refresh(receipt)
        assert receipt.status == "failed"
        assert "Invalid JSON" in receipt.error_message

    @pytest.mark.asyncio
    async def test_flow_marks_failed_on_n8n_error(
        self, async_db: AsyncSession, patch_sessionmaker, pdf_bytes: bytes
    ):
        file_id = "flow-fail-003"
        await ReceiptFactory.create(async_db, file_id=file_id, status="processing")

        with (
            patch(
                "app.routers.workflow_router.download_from_google_drive",
                return_value=("pdf", pdf_bytes, "receipt.pdf"),
            ),
            patch(
                "app.routers.workflow_router.llm_parse",
                return_value=MOCK_LLM_RESPONSE,
            ),
            patch(
                "app.routers.workflow_router.send_to_n8n",
                side_effect=ConnectionError("n8n unreachable"),
            ),
            pytest.raises(ConnectionError),
        ):
            await receipt_flow.fn(file_id)

        receipt = await get_receipt_by_file_id(async_db, file_id)
        await async_db.refresh(receipt)
        assert receipt.status == "failed"