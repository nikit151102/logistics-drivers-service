from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from database.database_app import get_session
from models import User
from routers.auth import get_current_user
from schemas.schemas import VehicleCreate, VehicleOut, LogCreate, LogOut
from crud import create_vehicle, create_log, get_vehicle_logs
from uuid import UUID

router = APIRouter(prefix="/vehicles", tags=["Транспортные средства"])

# Добавление автомобиля
@router.post("/", response_model=VehicleOut)
async def add_vehicle(vehicle: VehicleCreate, db: AsyncSession = Depends(get_session), current_user: User = Depends(get_current_user)):
    user_id = current_user.id
    return await create_vehicle(db, user_id, vehicle)

@router.post("/users/{user_id}", response_model=VehicleOut, )
async def add_vehicle_for_user(user_id: UUID, vehicle: VehicleCreate, db: AsyncSession = Depends(get_session)):
    return await create_vehicle(db, user_id, vehicle)


# Добавление лога для автомобиля
@router.post("/{vehicle_id}/logs", response_model=LogOut)
async def add_log(vehicle_id: UUID, log: LogCreate, db: AsyncSession = Depends(get_session), current_user: User = Depends(get_current_user)):
    user_id = current_user.id
    return await create_log(db, vehicle_id, log, user_id)


# Получение логов для автомобиля
@router.get("/{vehicle_id}/logs", response_model=list[LogOut])
async def get_logs(vehicle_id: UUID, db: AsyncSession = Depends(get_session), current_user: User = Depends(get_current_user)):
    user_id = current_user.id
    return await get_vehicle_logs(db, vehicle_id, user_id)


from sqlalchemy import select
@router.get("/drivers/with-vehicles")
async def get_all_drivers_with_vehicles(
    db: AsyncSession = Depends(get_session)
):
    result = await db.execute(
        select(User)    )
    users = result.scalars().all()
    
    # ��������� ������ ��� ������� ������������
    for user in users:
        await db.refresh(user, attribute_names=["vehicles"])
    
    return users