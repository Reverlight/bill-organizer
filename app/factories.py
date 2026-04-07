import datetime

from app.db import AsyncSession
from app.models import MenuDocument


class AsyncBaseFactory:
    model = None
    defaults = {}

    @classmethod
    async def create(cls, session: AsyncSession, **kwargs):
        data = {**cls.defaults, **kwargs}
        obj = cls.model(**data)
        session.add(obj)
        await session.commit()
        await session.refresh(obj)
        return obj

    @classmethod
    async def create_batch(cls, session: AsyncSession, size: int, **kwargs):
        return [await cls.create(session, **kwargs) for _ in range(size)]




# class MenuDocumentFactory(AsyncBaseFactory):
#     model = MenuDocument
#     defaults = {
#         "filename": "menu.pdf",
#         "extracted_text": "Margherita Pizza - $12\nCarbonara Pasta - $15",
#     }
