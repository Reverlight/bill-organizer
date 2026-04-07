import io
import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_async_db_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/main", tags=["main"])

"""
@router.get("")
async def basic_api(
    db: AsyncSession = Depends(get_async_db_session),
) -> list[dict]:
    result = await db.execute(
        select(
            MenuDocument.id, MenuDocument.filename, MenuDocument.created_at
        ).order_by(MenuDocument.created_at.desc())
    )
    return [
        {"id": row.id, "filename": row.filename, "created_at": str(row.created_at)}
        for row in result.all()
    ]
"""

@router.get("")
async def basic_api(
) -> dict:
    return {'result': 'API success'}
