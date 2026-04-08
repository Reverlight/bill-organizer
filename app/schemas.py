"""
Pydantic schemas for the admin REST API.
"""

import datetime
from typing import Optional

from pydantic import BaseModel, Field
from typing import Optional


class ReceiptData(BaseModel):
    vendor: Optional[str] = Field(None, description="Store or vendor name")
    date: Optional[str] = Field(None, description="Purchase date in ISO format (YYYY-MM-DD)")
    total: Optional[float] = Field(None, description="Total amount paid")
    currency: Optional[str] = Field(None, description="Currency code (USD, EUR, UAH, etc.)")
    category: Optional[str] = Field(None, description="Spending category (groceries, electronics, etc.)")
    payment_method: Optional[str] = Field(None, description="Payment method (cash, card, etc.)")
    notes: Optional[str] = Field(None, description="Any additional relevant info from the receipt")

class ProcessRequest(BaseModel):
    file_id: str