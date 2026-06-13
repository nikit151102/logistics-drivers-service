from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from database.database_app import get_session
from models import DeliveryType
from schemas.schemas import DeliveryTypeCreate, DeliveryTypeOut
from uuid import UUID
from utils.error_logger import log_system_error

router = APIRouter(prefix="/delivery-types", tags=["Типы доставки"])


@router.get("/", response_model=list[DeliveryTypeOut], summary="Список типов доставки")
async def get_delivery_types(db: AsyncSession = Depends(get_session), request: Request = None):
    try:
        result = await db.execute(select(DeliveryType))
        return result.scalars().all()
    except Exception as e:
        await log_system_error(
            error=e,
            title="Ошибка при полученнии списка типов доставок",
            section="delivery_types",
            request=request,
            component_name="get_delivery_types",
            additional_metadata={}
        )
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@router.get("/{delivery_type_id}", response_model=DeliveryTypeOut, summary="Получить тип доставки по ID")
async def get_delivery_type(delivery_type_id: UUID, db: AsyncSession = Depends(get_session), request: Request = None):
    try:
        result = await db.execute(select(DeliveryType).where(DeliveryType.id == delivery_type_id))
        delivery_type = result.scalar_one_or_none()
        if not delivery_type:
            raise HTTPException(status_code=404, detail="Тип доставки не найден")
        return delivery_type
    except Exception as e:
        await log_system_error(
            error=e,
            title="Ошибка при полученнии типа доставки по ID",
            section="delivery_types",
            request=request,
            component_name="get_delivery_type",
            additional_metadata={}
        )
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@router.post("/", response_model=DeliveryTypeOut, summary="Создать тип доставки")
async def create_delivery_type(delivery_type: DeliveryTypeCreate, db: AsyncSession = Depends(get_session), request: Request = None):
    try:
        db_type = DeliveryType(**delivery_type.dict())
        db.add(db_type)
        await db.commit()
        await db.refresh(db_type)
        return db_type
    except Exception as e:
        await log_system_error(
            error=e,
            title="Ошибка при создании типа доставки",
            section="delivery_types",
            request=request,
            component_name="create_delivery_type",
            additional_metadata={}
        )
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@router.put("/{delivery_type_id}", response_model=DeliveryTypeOut, summary="Обновить тип доставки")
async def update_delivery_type(
    delivery_type_id: UUID,
    delivery_type: DeliveryTypeCreate,
    db: AsyncSession = Depends(get_session), 
    request: Request = None
):
    try:
        result = await db.execute(select(DeliveryType).where(DeliveryType.id == delivery_type_id))
        db_type = result.scalar_one_or_none()
        if not db_type:
            raise HTTPException(status_code=404, detail="Тип доставки не найден")

        for key, value in delivery_type.dict().items():
            setattr(db_type, key, value)

        if hasattr(db_type, "changeDateTime"):
            db_type.changeDateTime = datetime.utcnow()

        await db.commit()
        await db.refresh(db_type)
        return db_type
    except Exception as e:
        await log_system_error(
            error=e,
            title="Ошибка при редактировании типа доставки",
            section="delivery_types",
            request=request,
            component_name="update_delivery_type",
            additional_metadata={}
        )
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@router.delete("/{delivery_type_id}", summary="Удалить тип доставки")
async def delete_delivery_type(delivery_type_id: UUID, db: AsyncSession = Depends(get_session), request: Request = None):
    try:
        result = await db.execute(select(DeliveryType).where(DeliveryType.id == delivery_type_id))
        db_type = result.scalar_one_or_none()
        if not db_type:
            raise HTTPException(status_code=404, detail="Тип доставки не найден")

        await db.delete(db_type)
        await db.commit()
        return {"detail": "Тип доставки успешно удалён"}
    except Exception as e:
        await log_system_error(
            error=e,
            title="Ошибка при удалении типа доставки",
            section="delivery_types",
            request=request,
            component_name="delete_delivery_type",
            additional_metadata={}
        )
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")
