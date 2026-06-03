from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from database.database_app import get_session
from models import Tariff
from schemas.schemas import TariffCreate, TariffOut
from uuid import UUID

router = APIRouter(prefix="/tariffs", tags=["Тарифы"])


@router.get("/", response_model=list[TariffOut], summary="Список тарифов")
async def get_tariffs(db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(Tariff))
    return result.scalars().all()


@router.get("/{tariff_id}", response_model=TariffOut, summary="Получить тариф по ID")
async def get_tariff(tariff_id: UUID, db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(Tariff).where(Tariff.id == tariff_id))
    tariff = result.scalar_one_or_none()
    if not tariff:
        raise HTTPException(status_code=404, detail="Тариф не найден")
    return tariff


@router.post("/", response_model=TariffOut, summary="Создать тариф")
async def create_tariff(tariff: TariffCreate, db: AsyncSession = Depends(get_session)):
    db_tariff = Tariff(**tariff.dict())
    db.add(db_tariff)
    await db.commit()
    await db.refresh(db_tariff)
    return db_tariff


@router.put("/{tariff_id}", response_model=TariffOut, summary="Обновить тариф")
async def update_tariff(tariff_id: UUID, tariff: TariffCreate, db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(Tariff).where(Tariff.id == tariff_id))
    db_tariff = result.scalar_one_or_none()
    if not db_tariff:
        raise HTTPException(status_code=404, detail="Тариф не найден")

    for key, value in tariff.dict().items():
        setattr(db_tariff, key, value)

    await db.commit()
    await db.refresh(db_tariff)
    return db_tariff


@router.delete("/{tariff_id}", summary="Удалить тариф")
async def delete_tariff(tariff_id: UUID, db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(Tariff).where(Tariff.id == tariff_id))
    db_tariff = result.scalar_one_or_none()
    if not db_tariff:
        raise HTTPException(status_code=404, detail="Тариф не найден")

    await db.delete(db_tariff)
    await db.commit()
    return {"detail": "Тариф успешно удален"}
