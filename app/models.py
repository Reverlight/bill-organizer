import datetime
import enum

from sqlalchemy import (
    Boolean,
    Date,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class AuditMixin:
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )


class Lead(Base, AuditMixin):
    __tablename__ = "leads"

    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    company_name: Mapped[str] = mapped_column(String(100), nullable=False)
    company_size: Mapped[str] = mapped_column(String(50), nullable=False)
    industry: Mapped[str] = mapped_column(String(50), nullable=False)
    job_title: Mapped[str] = mapped_column(String(100), nullable=False)
    current_situation: Mapped[str] = mapped_column(String(200), nullable=False)
    looking_for: Mapped[str] = mapped_column(String(200), nullable=False)
    budget: Mapped[str] = mapped_column(String(50), nullable=False)
    timeline: Mapped[str] = mapped_column(String(50), nullable=False)
    is_decision_maker: Mapped[str] = mapped_column(String(100), nullable=False)
    project_description: Mapped[str] = mapped_column(Text, nullable=False)
    how_heard: Mapped[str | None] = mapped_column(String(100), nullable=True)

    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_hot: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)