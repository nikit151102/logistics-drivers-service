from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from database.database_app import get_session
from models import Store
from schemas.schemas import StoreCreate, StoreOut
from uuid import UUID
from utils.error_logger import log_system_error


router = APIRouter(prefix="/stores", tags=["Магазины"])


@router.get("/stores", summary="Список магазинов")
async def get_stores(db: AsyncSession = Depends(get_session), request: Request = None):
    try:
        result = await db.execute(select(Store))
        return result.scalars().all()
    except Exception as e:
        await log_system_error(
            error=e,
            title="Ошибка при получении списка магазинов",
            section="stores",
            request=request,
            component_name="get_stores",
            additional_metadata={}
        )
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@router.get("/stores/{store_id}", summary="Получить магазин по ID")
async def get_store(store_id: UUID, db: AsyncSession = Depends(get_session), request: Request = None):
    try:
        result = await db.execute(select(Store).where(Store.id == store_id))
        store = result.scalar_one_or_none()
        if not store:
            raise HTTPException(status_code=404, detail="Магазин не найден")
        return store
    except Exception as e:
        await log_system_error(
            error=e,
            title="Ошибка при получении данных магазина",
            section="stores",
            request=request,
            component_name="get_store",
            additional_metadata={}
        )
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@router.post("/stores", response_model=StoreOut, summary="Создать магазин")
async def create_store(store: StoreCreate, db: AsyncSession = Depends(get_session), request: Request = None):
    try:
        result = await db.execute(select(Store).where(Store.uuid_1c == store.uuid_1c))
        existing = result.scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=400, detail="Магазин с таким uuid_1c уже существует")
        db_store = Store(**store.dict())
        db.add(db_store)
        await db.commit()
        await db.refresh(db_store)
        return db_store
    except Exception as e:
        await log_system_error(
            error=e,
            title="Ошибка при создании нового магазина",
            section="stores",
            request=request,
            component_name="create_store",
            additional_metadata={}
        )
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@router.put("/stores/{store_id}", summary="Обновить магазин")
async def update_store(store_id: UUID, store: StoreCreate, db: AsyncSession = Depends(get_session), request: Request = None):
    try:
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
    except Exception as e:
        await log_system_error(
            error=e,
            title="Ошибка при обновлении данных магазина",
            section="stores",
            request=request,
            component_name="update_store",
            additional_metadata={}
        )
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@router.delete("/stores/{store_id}", summary="Удалить магазин")
async def delete_store(store_id: UUID, db: AsyncSession = Depends(get_session), request: Request = None):
    try:
        result = await db.execute(select(Store).where(Store.id == store_id))
        db_store = result.scalar_one_or_none()
        if not db_store:
            raise HTTPException(status_code=404, detail="Магазин не найден")
        await db.delete(db_store)
        await db.commit()
        return {"detail": "Магазин удален"}
    except Exception as e:
        await log_system_error(
            error=e,
            title="Ошибка при удалении магазина",
            section="stores",
            request=request,
            component_name="delete_store",
            additional_metadata={}
        )
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")
