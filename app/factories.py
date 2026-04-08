from app.db import AsyncSession
from app.models import Receipt


class AsyncBaseFactory:
    model = None
    defaults = {}

    @classmethod
    async def create(cls, session: AsyncSession, **kwargs):
        data = {**cls.defaults, **kwargs}
        obj = cls.model()
        for key, value in data.items():
            setattr(obj, key, value)
        session.add(obj)
        await session.commit()
        await session.refresh(obj)
        return obj

    @classmethod
    async def create_batch(cls, session: AsyncSession, size: int, **kwargs):
        return [await cls.create(session, **kwargs) for _ in range(size)]


class ReceiptFactory(AsyncBaseFactory):
    model = Receipt
    defaults = {
        "file_id": "test-file-001",
        "status": "processing",
    }
