from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from models import RoutePlan, RoutePoint, User, Vehicle, LogEntry
from schemas.schemas import UserCreate, UserUpdate, VehicleCreate, LogCreate
from auth import get_password_hash
from sqlalchemy.orm import selectinload
from uuid import UUID


# USERS
async def create_user(db: AsyncSession, user: UserCreate):
    # Проверяем, существует ли пользователь с таким username
    existing_user = await db.execute(select(User).filter(User.username == user.username))
    existing_user = existing_user.scalar_one_or_none()

    if existing_user:
        raise HTTPException(status_code=400, detail="Username already taken")

    # Создаём пользователя
    db_user = User(
        username=user.username,
        hashed_password=get_password_hash(user.password),
        first_name=user.first_name,
        last_name=user.last_name,
        middle_name=user.middle_name,
        rate=user.rate,
        is_active=True
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)

    db_vehicle = Vehicle(
        owner_id = db_user.id, 
        model = "Не указана",
        plate_number = str(db_user.id),   
    )
    db.add(db_vehicle)
    await db.commit()
    await db.refresh(db_vehicle)

    # Можно вернуть пользователя с машиной, если нужно
    return db_user


async def update_user(db: AsyncSession, user: UserUpdate):
    db_user = await db.execute(select(User).where(User.id == user.id))
    db_user = db_user.scalar_one_or_none()

    if not db_user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    if user.username:
        db_user.username = user.username
    if user.first_name:
        db_user.first_name = user.first_name
    if user.last_name:
        db_user.last_name = user.last_name
    if user.middle_name:
        db_user.middle_name = user.middle_name
    if user.rate is not None:
        db_user.rate = user.rate
    if user.is_active is not None:
        db_user.is_active = user.is_active
    if user.transport_company_id is not None:
        db_user.transport_company_id = user.transport_company_id
    if user.tariff_id is not None:
        db_user.tariff_id = user.tariff_id

    db_user.changeDateTime = datetime.utcnow()
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

# VEHICLES
async def create_vehicle(db: AsyncSession, user_id: UUID, vehicle: VehicleCreate):
    db_vehicle = Vehicle(**vehicle.dict(), owner_id=user_id)
    db.add(db_vehicle)
    await db.commit()
    await db.refresh(db_vehicle)
    return db_vehicle


# LOGS
from zoneinfo import ZoneInfo
from datetime import datetime

async def create_log(db: AsyncSession, vehicle_id: UUID, log: LogCreate):
    barnaul_time = datetime.now(ZoneInfo("Asia/Barnaul"))
    
    db_log = LogEntry(vehicle_id=vehicle_id, timestamp=barnaul_time, **log.dict())
    
    db.add(db_log)
    await db.commit()
    await db.refresh(db_log)
    return db_log


async def get_vehicle_logs(db: AsyncSession, vehicle_id: UUID):
    result = await db.execute(select(LogEntry).where(LogEntry.vehicle_id == vehicle_id))
    return result.scalars().all()


# Создать маршрут для автомобиля
async def create_route_plan(db: AsyncSession, vehicle_id: UUID, date: datetime, notes: str = None):
    plan = RoutePlan(vehicle_id=vehicle_id, date=date, notes=notes)
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return plan

# Добавить точку маршрута
async def add_route_point(
    db: AsyncSession,
    route_plan_id: UUID,  # Исправлен тип с int на UUID
    doc: str,
    payment: float,
    counterparty: str,
    address_obj,
    note: str = None,
    order: int | None = None
):
    # Получаем все существующие точки маршрута для этого маршрута
    result = await db.execute(
        select(RoutePoint)
        .where(RoutePoint.route_plan_id == route_plan_id)
        .order_by(RoutePoint.order.asc())
    )
    existing_points = result.scalars().all()

    if order is None:
        # Если order не передан, ставим следующий после максимального
        order = max((p.order for p in existing_points), default=0) + 1
    else:
        # Если order передан, проверяем конфликты и сдвигаем остальные
        for p in existing_points:
            if p.order >= order:
                p.order += 1
                db.add(p)  # помечаем для обновления

    # Создаём новую точку маршрута
    point = RoutePoint(
        route_plan_id=route_plan_id,
        doc=doc,
        payment=payment,
        counterparty=counterparty,
        address_id=address_obj.id,  # Устанавливаем связь через address_id
        order=order,
        arrival_time=None,
        departure_time=None,
        duration_minutes=None,
        note=note,
        latitude=address_obj.latitude,
        longitude=address_obj.longitude,
    )

    db.add(point)
    await db.commit()
    await db.refresh(point)
    return point

# Получить маршрут с точками для автомобиля
async def get_route_plan(db: AsyncSession, vehicle_id: int, date: datetime):
    result = await db.execute(
        select(RoutePlan).where(RoutePlan.vehicle_id == vehicle_id, RoutePlan.date == date).options(selectinload(RoutePlan.points))
    )
    return result.scalars().first()
