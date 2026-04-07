from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models import Lead

MOCK_SCORE_RESPONSE = {
    "score": 9,
    "reasoning": "TechCorp has a clear immediate need and a $20k+ budget. The contact is the CTO and decision maker. Timeline is this week.",
}

HOT_LEAD_PAYLOAD = {
    "full_name": "Sarah Mitchell",
    "email": "sarah.mitchell@techcorp.io",
    "phone": "+14155552671",
    "company_name": "TechCorp Solutions",
    "company_size": "201–1000 employees",
    "industry": "SaaS / Software",
    "job_title": "CTO",
    "current_situation": "We have a specific problem and need a solution now",
    "looking_for": "AI / LLM integrations",
    "budget": "$20,000+",
    "timeline": "Immediately (this week)",
    "is_decision_maker": "Yes, I make the final call",
    "project_description": "We are building an internal AI assistant for our support team.",
    "how_heard": "LinkedIn",
}

COLD_LEAD_PAYLOAD = {
    **HOT_LEAD_PAYLOAD,
    "full_name": "Mike Peters",
    "email": "mike.peters@gmail.com",
    "phone": None,
    "company_name": "Self employed",
    "company_size": "1–10 employees",
    "budget": "Under $1,000",
    "timeline": "No fixed timeline",
    "is_decision_maker": "No, I'm gathering info for someone else",
    "current_situation": "Just exploring / not sure yet",
    "project_description": "Just curious about what AI can do for small businesses.",
}


@pytest.mark.asyncio
async def test_lead_webhook_hot_lead_is_stored(
    async_client: AsyncClient, async_db: AsyncSession
):
    """Hot lead: score >= 7, is_hot=True, stored in DB."""
    with patch(
        "app.routers.lead_router.score_lead",
        new=AsyncMock(return_value=MOCK_SCORE_RESPONSE),
    ):
        response = await async_client.post("/api/leads/webhook", json=HOT_LEAD_PAYLOAD)

    assert response.status_code == 200
    data = response.json()

    assert data["score"] == 9
    assert data["is_hot"] is True
    assert data["full_name"] == "Sarah Mitchell"
    assert data["company_name"] == "TechCorp Solutions"
    assert data["email"] == "sarah.mitchell@techcorp.io"
    assert "reasoning" in data
    assert data["lead_id"] is not None

    lead = await async_db.get(Lead, data["lead_id"])
    assert lead is not None
    assert lead.score == 9
    assert lead.is_hot is True
    assert lead.email == "sarah.mitchell@techcorp.io"


@pytest.mark.asyncio
async def test_lead_webhook_cold_lead_is_not_hot(
    async_client: AsyncClient, async_db: AsyncSession
):
    """Cold lead: score < 7, is_hot=False, still stored in DB."""
    cold_score = {"score": 3, "reasoning": "Low budget, no timeline, not a decision maker."}

    with patch(
        "app.routers.lead_router.score_lead",
        new=AsyncMock(return_value=cold_score),
    ):
        response = await async_client.post("/api/leads/webhook", json=COLD_LEAD_PAYLOAD)

    assert response.status_code == 200
    data = response.json()

    assert data["score"] == 3
    assert data["is_hot"] is False

    lead = await async_db.get(Lead, data["lead_id"])
    assert lead is not None
    assert lead.is_hot is False
    assert lead.score == 3


@pytest.mark.asyncio
async def test_lead_webhook_boundary_score_at_threshold(
    async_client: AsyncClient, async_db: AsyncSession
):
    """Score exactly at threshold (7) should be hot."""
    boundary_score = {"score": 7, "reasoning": "Meets minimum threshold exactly."}

    with patch(
        "app.routers.lead_router.score_lead",
        new=AsyncMock(return_value=boundary_score),
    ):
        response = await async_client.post("/api/leads/webhook", json=HOT_LEAD_PAYLOAD)

    assert response.status_code == 200
    assert response.json()["is_hot"] is True


@pytest.mark.asyncio
async def test_lead_webhook_score_below_threshold_is_cold(
    async_client: AsyncClient, async_db: AsyncSession
):
    """Score of 6 should NOT be hot."""
    with patch(
        "app.routers.lead_router.score_lead",
        new=AsyncMock(return_value={"score": 6, "reasoning": "Just below threshold."}),
    ):
        response = await async_client.post("/api/leads/webhook", json=HOT_LEAD_PAYLOAD)

    assert response.status_code == 200
    assert response.json()["is_hot"] is False


@pytest.mark.asyncio
async def test_lead_webhook_optional_fields_can_be_null(
    async_client: AsyncClient, async_db: AsyncSession
):
    """phone and how_heard are optional — should not cause errors."""
    payload = {**HOT_LEAD_PAYLOAD, "phone": None, "how_heard": None}

    with patch(
        "app.routers.lead_router.score_lead",
        new=AsyncMock(return_value=MOCK_SCORE_RESPONSE),
    ):
        response = await async_client.post("/api/leads/webhook", json=payload)

    assert response.status_code == 200
    data = response.json()

    lead = await async_db.get(Lead, data["lead_id"])
    assert lead.phone is None
    assert lead.how_heard is None


@pytest.mark.asyncio
async def test_lead_webhook_openai_failure_returns_502(
    async_client: AsyncClient, async_db: AsyncSession
):
    """If scorer raises ValueError (bad OpenAI response), endpoint returns 502."""
    with patch(
        "app.routers.lead_router.score_lead",
        new=AsyncMock(side_effect=ValueError("Invalid JSON from OpenAI: ...")),
    ):
        response = await async_client.post("/api/leads/webhook", json=HOT_LEAD_PAYLOAD)

    assert response.status_code == 502


@pytest.mark.asyncio
async def test_lead_webhook_missing_required_field_returns_422(
    async_client: AsyncClient, async_db: AsyncSession
):
    """Missing required field should return 422 from Pydantic validation."""
    payload = {**HOT_LEAD_PAYLOAD}
    del payload["email"]

    response = await async_client.post("/api/leads/webhook", json=payload)

    assert response.status_code == 422