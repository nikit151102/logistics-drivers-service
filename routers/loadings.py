from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from database.database_app import get_session
from routers.auth import get_current_user
from models import Address, Loading, LoadingPlace, LoadingStatusLog, RoutePointStatusEnum, Vehicle, RoutePlan, User
from datetime import datetime
from uuid import UUID

router = APIRouter(prefix="/loadings", tags=["Погрузки"])


@router.post("/{route_id}/loadings", summary="Добавить место погрузки в маршрут")
async def add_loading_to_route(
    route_id: UUID,
    loading_place_id: UUID | None = None,
    loading_place_uuid: str | None = None,
    loading_place_name: str | None = None,
    address: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    doc_number: str | None = None,
    volume: float | None = None,
    weight: float | None = None,
    note: str | None = None,
    db: AsyncSession = Depends(get_session)
):
    result = await db.execute(
        select(RoutePlan).options(selectinload(RoutePlan.vehicle)).where(RoutePlan.id == route_id)
    )
    route = result.scalars().first()
    if not route:
        raise HTTPException(status_code=404, detail="Маршрут не найден")

    loading_place = None
    if loading_place_id:
        result = await db.execute(select(LoadingPlace).where(LoadingPlace.id == loading_place_id))
        loading_place = result.scalars().first()
    elif loading_place_uuid:
        result = await db.execute(select(LoadingPlace).where(LoadingPlace.uuid_1c == loading_place_uuid))
        loading_place = result.scalars().first()

    if not loading_place:
        if not loading_place_name or not address:
            raise HTTPException(status_code=400, detail="Для нового места погрузки нужно указать 'loading_place_name' и 'address'")
        addr = Address(address_1c=address)
        db.add(addr)
        await db.flush()
        loading_place = LoadingPlace(uuid_1c=loading_place_uuid, name=loading_place_name, address_id=addr.id)
        db.add(loading_place)
        await db.flush()

    loading = Loading(
        route_plan_id=route.id,
        loading_place_id=loading_place.id,
        start_time=start_time,
        end_time=end_time,
        doc_number=doc_number,
        volume=volume,
        weight=weight,
        note=note
    )
    loading.changeDateTime = datetime.utcnow()

    db.add(loading)
    await db.commit()
    await db.refresh(loading)
    return loading



@router.get("/{route_id}/loadings", summary="Получить все погрузки маршрута (для администратора)")
async def get_route_loadings(route_id: UUID, db: AsyncSession = Depends(get_session)):
    result = await db.execute(
        select(Loading)
        .join(Loading.route_plan)
        .where(RoutePlan.id == route_id)
        .options(selectinload(Loading.loading_place).selectinload(LoadingPlace.address))
    )
    return result.scalars().all()



@router.get("/{route_id}/me/loadings", summary="Получить погрузки маршрута (для водителя)")
async def get_my_route_loadings(
    route_id: UUID,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(Loading)
        .join(Loading.route_plan)
        .join(RoutePlan.vehicle)
        .where(RoutePlan.id == route_id, Vehicle.owner_id == current_user.id)
        .options(selectinload(Loading.loading_place).selectinload(LoadingPlace.address))
    )
    return result.scalars().all()



@router.get("/item/{loading_id}", summary="Получить конкретную погрузку по ID")
async def get_loading_by_id(loading_id: UUID, db: AsyncSession = Depends(get_session)):
    result = await db.execute(
        select(Loading)
        .where(Loading.id == loading_id)
        .options(selectinload(Loading.loading_place).selectinload(LoadingPlace.address))
    )
    loading = result.scalars().first()
    if not loading:
        raise HTTPException(status_code=404, detail="Погрузка не найдена")
    return loading



@router.patch("/item/{loading_id}", summary="Обновить данные о погрузке")
async def update_loading(
    loading_id: UUID,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    doc_number: str | None = None,
    volume: float | None = None,
    weight: float | None = None,
    note: str | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_session)
):
    result = await db.execute(select(Loading).where(Loading.id == loading_id))
    loading = result.scalars().first()
    if not loading:
        raise HTTPException(status_code=404, detail="Погрузка не найдена")

    updates = dict(
        start_time=start_time,
        end_time=end_time,
        doc_number=doc_number,
        volume=volume,
        weight=weight,
        note=note,
        status=status
    )
    for k, v in updates.items():
        if v is not None and hasattr(loading, k):
            setattr(loading, k, v)

    loading.changeDateTime = datetime.utcnow()
    
    db.add(loading)
    await db.commit()
    await db.refresh(loading)
    return loading



@router.delete("/item/{loading_id}", summary="Удалить погрузку")
async def delete_loading(loading_id: UUID, db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(Loading).where(Loading.id == loading_id))
    loading = result.scalars().first()
    if not loading:
        raise HTTPException(status_code=404, detail="Погрузка не найдена")

    await db.delete(loading)
    await db.commit()
    return {"detail": "Погрузка успешно удалена"}


@router.get("/item/{loading_id}/logs", summary="Получить логи статусов погрузки")
async def get_loading_logs(loading_id: UUID, db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(LoadingStatusLog).where(LoadingStatusLog.loading_id == loading_id))
    return result.scalars().all()

@router.post("/item/{loading_id}/logs", summary="Добавить лог статуса погрузки")
async def add_loading_log(
    loading_id: UUID,
    status: RoutePointStatusEnum,  # Используем Enum для валидации
    note: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    db: AsyncSession = Depends(get_session)
):
    # Получаем погрузку
    result = await db.execute(select(Loading).where(Loading.id == loading_id))
    loading = result.scalars().first()
    if not loading:
        raise HTTPException(status_code=404, detail="Погрузка не найдена")

    # Создаём лог
    log = LoadingStatusLog(
        loading_id=loading.id,
        status=status,
        note=note,
        latitude=latitude,
        longitude=longitude
    )
    db.add(log)

    # Обновляем статус самой погрузки
    loading.status = status
    if latitude is not None:
        loading.latitude = latitude
    if longitude is not None:
        loading.longitude = longitude
    db.add(loading)

    await db.commit()
    await db.refresh(loading)

    return {
        "detail": "Статус обновлён",
        "loading_id": loading.id,
        "status": loading.status
    }



from datetime import datetime

@router.patch("/loadings/{loading_id}/status", summary="Обновить статус загрузки")
async def update_loading_status(
    loading_id: UUID,
    status: RoutePointStatusEnum,
    latitude: float | None = None,
    longitude: float | None = None,
    note: str | None = None,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(Loading)
        .options(selectinload(Loading.route_plan).selectinload(RoutePlan.vehicle))
        .where(Loading.id == loading_id)
    )
    loading = result.scalars().first()
    if not loading:
        raise HTTPException(status_code=404, detail="Загрузка не найдена")

    if loading.route_plan.vehicle.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Нет доступа")

    # Обновляем статус
    loading.status = status

    # Создаем лог статуса
    from models import LoadingStatusLog
    log = LoadingStatusLog(
        loading_id=loading.id,
        status=status,
        timestamp=datetime.utcnow(),
        latitude=latitude,
        longitude=longitude,
        note=note
    )

    db.add_all([loading, log])
    await db.commit()
    await db.refresh(loading)
    return loading

