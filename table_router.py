"""
Admin REST API for restaurant table management.

Endpoints:
    GET    /api/tables          — list all tables (optional ?active_only=true)
    POST   /api/tables          — create a new table
    GET    /api/tables/{id}     — get a single table
    PATCH  /api/tables/{id}     — update a table
    DELETE /api/tables/{id}     — delete a table (only if no confirmed reservations)
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_async_db_session
from app.models import Reservation, ReservationStatus, RestaurantTable
from app.schemas import TableCreate, TableRead, TableUpdate

router = APIRouter(prefix="/api/tables", tags=["tables"])


# ── LIST ──────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[TableRead])
async def list_tables(
    active_only: bool = Query(False, description="Return only active tables"),
    db: AsyncSession = Depends(get_async_db_session),
):
    stmt = select(RestaurantTable).order_by(RestaurantTable.name)
    if active_only:
        stmt = stmt.where(RestaurantTable.is_active == True)

    result = await db.execute(stmt)
    return result.scalars().all()


# ── CREATE ────────────────────────────────────────────────────────────────────

@router.post("", response_model=TableRead, status_code=201)
async def create_table(
    body: TableCreate,
    db: AsyncSession = Depends(get_async_db_session),
):
    # Check for duplicate name (case-insensitive)
    existing = await db.execute(
        select(RestaurantTable).where(
            func.lower(RestaurantTable.name) == body.name.strip().lower()
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="A table with this name already exists.")

    table = RestaurantTable(
        name=body.name.strip(),
        capacity=body.capacity,
        is_active=body.is_active,
    )
    db.add(table)
    await db.commit()
    await db.refresh(table)
    return table


# ── GET ONE ───────────────────────────────────────────────────────────────────

@router.get("/{table_id}", response_model=TableRead)
async def get_table(
    table_id: int,
    db: AsyncSession = Depends(get_async_db_session),
):
    table = await db.get(RestaurantTable, table_id)
    if not table:
        raise HTTPException(status_code=404, detail="Table not found.")
    return table


# ── UPDATE ────────────────────────────────────────────────────────────────────

@router.patch("/{table_id}", response_model=TableRead)
async def update_table(
    table_id: int,
    body: TableUpdate,
    db: AsyncSession = Depends(get_async_db_session),
):
    table = await db.get(RestaurantTable, table_id)
    if not table:
        raise HTTPException(status_code=404, detail="Table not found.")

    updates = body.model_dump(exclude_unset=True)

    # If renaming, check uniqueness
    if "name" in updates:
        new_name = updates["name"].strip()
        dup = await db.execute(
            select(RestaurantTable).where(
                func.lower(RestaurantTable.name) == new_name.lower(),
                RestaurantTable.id != table_id,
            )
        )
        if dup.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="A table with this name already exists.")
        updates["name"] = new_name

    for field, value in updates.items():
        setattr(table, field, value)

    await db.commit()
    await db.refresh(table)
    return table


# ── DELETE ────────────────────────────────────────────────────────────────────

@router.delete("/{table_id}", status_code=204)
async def delete_table(
    table_id: int,
    db: AsyncSession = Depends(get_async_db_session),
):
    table = await db.get(RestaurantTable, table_id)
    if not table:
        raise HTTPException(status_code=404, detail="Table not found.")

    # Prevent deletion if any future confirmed reservations reference this table
    future_count = await db.execute(
        select(func.count())
        .select_from(Reservation)
        .where(
            Reservation.table_id == table_id,
            Reservation.status == ReservationStatus.CONFIRMED,
        )
    )
    if future_count.scalar() > 0:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete a table with confirmed reservations. "
                   "Cancel or reassign them first.",
        )

    await db.delete(table)
    await db.commit()