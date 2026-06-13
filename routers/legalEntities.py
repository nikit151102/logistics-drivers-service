from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from database.database_app import get_session
from models import LegalEntityType
from schemas.schemas import LegalEntityTypeCreate, LegalEntityTypeOut
from uuid import UUID
from utils.error_logger import log_system_error

router = APIRouter(prefix="/legal-entities", tags=["Типы юридических лиц"])


@router.get("/", response_model=list[LegalEntityTypeOut], summary="Список типов юридических лиц")
async def get_legal_entities(db: AsyncSession = Depends(get_session), request: Request = None):
    try:
        result = await db.execute(select(LegalEntityType))
        return result.scalars().all()
    except Exception as e:
        await log_system_error(
            error=e,
            title="Ошибка при полученнии списка типов юридических лиц",
            section="legal_entities",
            request=request,
            component_name="get_legal_entities",
            additional_metadata={}
        )
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@router.get("/{entity_id}", response_model=LegalEntityTypeOut, summary="Получить тип юр. лица по ID")
async def get_legal_entity(entity_id: UUID, db: AsyncSession = Depends(get_session), request: Request = None):
    try:
        result = await db.execute(select(LegalEntityType).where(LegalEntityType.id == entity_id))
        entity = result.scalar_one_or_none()
        if not entity:
            raise HTTPException(status_code=404, detail="Тип юридического лица не найден")
        return entity
    except Exception as e:
        await log_system_error(
            error=e,
            title="Ошибка при полученнии типа юридического лица",
            section="legal_entities",
            request=request,
            component_name="get_legal_entity",
            additional_metadata={}
        )
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@router.post("/", response_model=LegalEntityTypeOut, summary="Создать тип юридического лица")
async def create_legal_entity(entity: LegalEntityTypeCreate, db: AsyncSession = Depends(get_session), request: Request = None):
    try:
        db_entity = LegalEntityType(**entity.dict())
        db.add(db_entity)
        await db.commit()
        await db.refresh(db_entity)
        return db_entity
    except Exception as e:
        await log_system_error(
            error=e,
            title="Ошибка при создании типа юридического лица",
            section="legal_entities",
            request=request,
            component_name="create_legal_entity",
            additional_metadata={}
        )
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@router.put("/{entity_id}", response_model=LegalEntityTypeOut, summary="Обновить тип юридического лица")
async def update_legal_entity(entity_id: UUID, entity: LegalEntityTypeCreate, db: AsyncSession = Depends(get_session), request: Request = None):
    try:
        result = await db.execute(select(LegalEntityType).where(LegalEntityType.id == entity_id))
        db_entity = result.scalar_one_or_none()
        if not db_entity:
            raise HTTPException(status_code=404, detail="Тип юридического лица не найден")

        for key, value in entity.dict().items():
            setattr(db_entity, key, value)

        if hasattr(db_entity, "changeDateTime"):
            db_entity.changeDateTime = datetime.utcnow()
        await db.commit()
        await db.refresh(db_entity)
        return db_entity
    except Exception as e:
        await log_system_error(
            error=e,
            title="Ошибка при редактировании типа юридического лица",
            section="legal_entities",
            request=request,
            component_name="update_legal_entity",
            additional_metadata={}
        )
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@router.delete("/{entity_id}", summary="Удалить тип юридического лица")
async def delete_legal_entity(entity_id: UUID, db: AsyncSession = Depends(get_session), request: Request = None):
    try:
        result = await db.execute(select(LegalEntityType).where(LegalEntityType.id == entity_id))
        db_entity = result.scalar_one_or_none()
        if not db_entity:
            raise HTTPException(status_code=404, detail="Тип юридического лица не найден")

        await db.delete(db_entity)
        await db.commit()
        return {"detail": "Тип юридического лица успешно удалён"}
    except Exception as e:
        await log_system_error(
            error=e,
            title="Ошибка при удалении типа юридического лица",
            section="legal_entities",
            request=request,
            component_name="delete_legal_entity",
            additional_metadata={}
        )
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")
