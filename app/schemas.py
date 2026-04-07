"""
Pydantic schemas for the admin REST API.
"""

import datetime
from typing import Optional

from pydantic import BaseModel, Field



class LeadWebhookPayload(BaseModel):
    full_name: str
    email: str
    phone: str | None = None
    company_name: str
    company_size: str
    industry: str
    job_title: str
    current_situation: str
    looking_for: str
    budget: str
    timeline: str
    is_decision_maker: str
    project_description: str
    how_heard: str | None = None


class LeadScoreResult(BaseModel):
    lead_id: int
    full_name: str
    company_name: str
    email: str
    score: int
    reasoning: str
    is_hot: bool