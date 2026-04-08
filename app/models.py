import datetime

from sqlalchemy import Float, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class AuditMixin:
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )


class Receipt(AuditMixin, Base):
    __tablename__ = "receipts"

    file_id: Mapped[str | None] = mapped_column(String, nullable=True)
    file_name: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="processing")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_at: Mapped[datetime.datetime | None] = mapped_column(nullable=True)

    # extracted fields
    vendor: Mapped[str | None] = mapped_column(String, nullable=True)
    date: Mapped[str | None] = mapped_column(String, nullable=True)
    total: Mapped[float | None] = mapped_column(Float, nullable=True)
    tax: Mapped[float | None] = mapped_column(Float, nullable=True)
    discount: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str | None] = mapped_column(String, nullable=True)
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    payment_method: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
