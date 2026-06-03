from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.database_app import get_session
from models import LoadingPlace, Address
from uuid import UUID

router = APIRouter(prefix="/loading_places", tags=["Места загрузок"])


# ===================== Получить все =====================
@router.get("/", summary="Получить список всех мест загрузок")
async def get_all_loading_places(db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(LoadingPlace))
    return result.scalars().all()


# ===================== Получить одно =====================
@router.get("/{loading_place_id}", summary="Получить место загрузки по ID")
async def get_loading_place(loading_place_id: UUID, db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(LoadingPlace).where(LoadingPlace.id == loading_place_id))
    place = result.scalars().first()
    if not place:
        raise HTTPException(status_code=404, detail="Место загрузки не найдено")
    return place


# ===================== Создать =====================
@router.post("/", summary="Создать новое место загрузки")
async def create_loading_place(
    name: str,
    address_id: UUID,
    contact_name: str | None = None,
    phone: str | None = None,
    work_hours: str | None = None,
    note: str | None = None,
    uuid_1c: str | None = None,
    db: AsyncSession = Depends(get_session)
):
    # Проверка адреса
    result = await db.execute(select(Address).where(Address.id == address_id))
    address = result.scalars().first()
    if not address:
        raise HTTPException(status_code=400, detail="Указанный адрес не найден")

    new_place = LoadingPlace(
        name=name,
        address_id=address.id,
        contact_name=contact_name,
        phone=phone,
        work_hours=work_hours,
        note=note,
        uuid_1c=uuid_1c
    )

    db.add(new_place)
    await db.commit()
    await db.refresh(new_place)
    return new_place


# ===================== Обновить =====================
@router.patch("/{loading_place_id}", summary="Обновить место загрузки")
async def update_loading_place(
    loading_place_id: UUID,
    name: str | None = None,
    contact_name: str | None = None,
    phone: str | None = None,
    work_hours: str | None = None,
    note: str | None = None,
    db: AsyncSession = Depends(get_session)
):
    result = await db.execute(select(LoadingPlace).where(LoadingPlace.id == loading_place_id))
    place = result.scalars().first()
    if not place:
        raise HTTPException(status_code=404, detail="Место загрузки не найдено")

    if name is not None:
        place.name = name
    if contact_name is not None:
        place.contact_name = contact_name
    if phone is not None:
        place.phone = phone
    if work_hours is not None:
        place.work_hours = work_hours
    if note is not None:
        place.note = note

    place.changeDateTime = datetime.utcnow()
    db.add(place)
    await db.commit()
    await db.refresh(place)
    return place


# ===================== Удалить =====================
@router.delete("/{loading_place_id}", summary="Удалить место загрузки")
async def delete_loading_place(loading_place_id: UUID, db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(LoadingPlace).where(LoadingPlace.id == loading_place_id))
    place = result.scalars().first()
    if not place:
        raise HTTPException(status_code=404, detail="Место загрузки не найдено")

    await db.delete(place)
    await db.commit()
    return {"detail": "Удалено успешно"}