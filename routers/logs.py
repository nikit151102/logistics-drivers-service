from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from database.database_app import get_session
from routers.auth import get_current_user
from schemas.schemas import LogCreate, LogOut
from models import LogEntry, User, Vehicle
from crud import create_log, get_vehicle_logs
from uuid import UUID
from utils.error_logger import log_system_error

router = APIRouter(prefix="/logs", tags=["Логи"])

# Получение автомобиля пользователя по vehicle_id и user_id
async def get_vehicle_by_user(db: AsyncSession, user_id: UUID, vehicle_id: UUID):
    result = await db.execute(
        select(Vehicle).where(Vehicle.id == vehicle_id, Vehicle.owner_id == user_id)
    )
    vehicle = result.scalars().first()
    return vehicle

# Получение автомобиля пользователя по его id
async def get_user_vehicle(db: AsyncSession, user_id: int):
    result = await db.execute(
        select(Vehicle).where(Vehicle.owner_id == user_id)
    )
    vehicle = result.scalars().first()  # Берем первый найденный автомобиль
    return vehicle

# Добавление лога для машины пользователя (автомобиль выбирается автоматически)
@router.post("/", response_model=LogOut, summary="Добавить лог", description="Записывает новое событие: смена статуса, геопозиция и время")
async def add_log(log: LogCreate, db: AsyncSession = Depends(get_session), 
                  current_user: User = Depends(get_current_user), 
                  request: Request = None):
    try:
        vehicle = await get_user_vehicle(db, current_user.id)
        
        if not vehicle:
            raise HTTPException(status_code=403, detail="У вас нет автомобилей для записи логов")
        
        return await create_log(db, vehicle.id, log)
    except Exception as e:
        await log_system_error(
            error=e,
            title="Ошибка при записи нового события (лога)",
            section="logs",
            request=request,
            component_name="add_log",
            additional_metadata={}
        )
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


# Получение логов для машины пользователя (автомобиль выбирается автоматически)
@router.get("/", response_model=list[LogOut], summary="История машины", description="Возвращает все логи для выбранной машины")
async def get_logs(db: AsyncSession = Depends(get_session), 
                   current_user: User = Depends(get_current_user), 
                   request: Request = None):
    try:
        vehicle = await get_user_vehicle(db, current_user.id)

        if not vehicle:
            raise HTTPException(status_code=403, detail="У вас нет автомобилей для получения логов")
        
        return await get_vehicle_logs(db, vehicle.id)
    except Exception as e:
        await log_system_error(
            error=e,
            title="Ошибка при выводе логов выбранной машины",
            section="logs",
            request=request,
            component_name="get_logs",
            additional_metadata={}
        )
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


# Получение всех логов для всех машин пользователя
@router.get("/all", response_model=list[LogOut], summary="Все логи", description="Возвращает список всех логов по всем машинам пользователя")
async def get_all_logs(db: AsyncSession = Depends(get_session), 
                       current_user: User = Depends(get_current_user), 
                       request: Request = None):
    try:
        user_vehicles = current_user.vehicles
        
        if not user_vehicles:
            return []
        
        vehicle_ids = [vehicle.id for vehicle in user_vehicles]
        result = await db.execute(
            select(LogEntry).where(LogEntry.vehicle_id.in_(vehicle_ids))
        )
        return result.scalars().all()
    except Exception as e:
        await log_system_error(
            error=e,
            title="Ошибка при выводе логов по всем машинам пользователя",
            section="logs",
            request=request,
            component_name="get_all_logs",
            additional_metadata={}
        )
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


# Получение логов для автомобилей пользователя
@router.get("/{vehicle_id}", response_model=list[LogOut], summary="История машины", description="Возвращает все логи для выбранной машины")
async def get_logs_by_cars(vehicle_id: UUID, 
                   db: AsyncSession = Depends(get_session), 
                   current_user: User = Depends(get_current_user), 
                   request: Request = None):
    try:
        vehicle = await get_vehicle_by_user(db, current_user.id, vehicle_id)

        if not vehicle:
            raise HTTPException(status_code=403, detail="У вас нет доступа к этому автомобилю")
    
        return await get_vehicle_logs(db, vehicle_id)
    except Exception as e:
        await log_system_error(
            error=e,
            title="Ошибка при выводе логов выбранной машины пользовтаеля",
            section="logs",
            request=request,
            component_name="get_logs_by_cars",
            additional_metadata={}
        )
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")















