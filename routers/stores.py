from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from database.database_app import get_session
from models import Store
from schemas.schemas import StoreCreate, StoreOut
from uuid import UUID

router = APIRouter(prefix="/stores", tags=["Магазины"])


@router.get("/stores", summary="Список магазинов")
async def get_stores(db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(Store))
    return result.scalars().all()

@router.get("/stores/{store_id}", summary="Получить магазин по ID")
async def get_store(store_id: UUID, db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(Store).where(Store.id == store_id))
    store = result.scalar_one_or_none()
    if not store:
        raise HTTPException(status_code=404, detail="Магазин не найден")
    return store

@router.post("/stores", response_model=StoreOut, summary="Создать магазин")
async def create_store(store: StoreCreate, db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(Store).where(Store.uuid_1c == store.uuid_1c))
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Магазин с таким uuid_1c уже существует")
    db_store = Store(**store.dict())
    db.add(db_store)
    await db.commit()
    await db.refresh(db_store)
    return db_store


@router.put("/stores/{store_id}", summary="Обновить магазин")
async def update_store(store_id: UUID, store: StoreCreate, db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(Store).where(Store.id == store_id))
    db_store = result.scalar_one_or_none()
    if not db_store:
        raise HTTPException(status_code=404, detail="Магазин не найден")
    for key, value in store.dict().items():
        setattr(db_store, key, value)
    db_store.changeDateTime = datetime.utcnow()
    await db.commit()
    await db.refresh(db_store)
    return db_store

@router.delete("/stores/{store_id}", summary="Удалить магазин")
async def delete_store(store_id: UUID, db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(Store).where(Store.id == store_id))
    db_store = result.scalar_one_or_none()
    if not db_store:
        raise HTTPException(status_code=404, detail="Магазин не найден")
    await db.delete(db_store)
    await db.commit()
    return {"detail": "Магазин удален"}
