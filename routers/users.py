from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from database.database_app import get_session
from schemas.schemas import UserCreate, UserOut, UserUpdate
from models import TransportCompany, User
from crud import create_user, update_user
from sqlalchemy.orm import joinedload
from uuid import UUID
from utils.error_logger import log_system_error

router = APIRouter(prefix="/users", tags=["Пользователи"])


@router.post("/", summary="Создать нового водителя", description="Регистрирует нового водителя в системе")
async def add_user(user: UserCreate, db: AsyncSession = Depends(get_session), request: Request = None):
    try:
        return await create_user(db, user)
    except Exception as e:
        await log_system_error(
            error=e,
            title="Ошибка при создании водителя",
            section="users",
            request=request,
            component_name="create_user",
            additional_metadata={"user_data": user.dict()}
        )
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

@router.get("/", summary="Список водителей", description="Возвращает список всех водителей")
async def get_users(db: AsyncSession = Depends(get_session), request: Request = None):
    try:
        result = await db.execute(select(User)
            .options(
                joinedload(User.transport_company),  
                joinedload(User.tariff) 
            ))
        return result.scalars().all()
    except Exception as e:
        await log_system_error(
            error=e,
            title="Ошибка при получении всех водителей",
            section="users",
            request=request,
            component_name="get_users",
            additional_metadata={}
        )
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@router.get("/{user_id}", response_model=UserOut, summary="Получить пользователя по ID", description="Возвращает данные пользователя по его ID, включая связанную информацию о транспортной компании и тарифе")
async def get_user(user_id: UUID, db: AsyncSession = Depends(get_session), request: Request = None):
    try:
        result = await db.execute(
            select(User)
            .options(
                joinedload(User.transport_company),  
                joinedload(User.tariff) 
            )
            .where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        return user
    except Exception as e:
        await log_system_error(
            error=e,
            title="Ошибка при получении данных водителя",
            section="users",
            request=request,
            component_name="get_user",
            additional_metadata={"user_id": user_id}
        )
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")
    
@router.patch("/{user_id}", response_model=UserOut, summary="Редактировать пользователя", description="Редактирует данные пользователя по ID")
async def update_user_endpoint( user: UserUpdate, db: AsyncSession = Depends(get_session), request: Request = None):
    try:
        return await update_user(db, user)
    except Exception as e:
        await log_system_error(
            error=e,
            title="Ошибка при редактировании данных водителя",
            section="users",
            request=request,
            component_name="update_user_endpoint",
            additional_metadata={"user_data": user.dict()}
        )
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")
    

@router.delete("/{user_id}", summary="Удалить пользователя", description="Удаление пользователя по ID")
async def delete_user(user_id: UUID, db: AsyncSession = Depends(get_session), request: Request = None):
    try:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
    
        await db.delete(user)
        await db.commit()
        return None
    except Exception as e:
        await log_system_error(
            error=e,
            title="Ошибка при удалении водителя",
            section="users",
            request=request,
            component_name="delete_user",
            additional_metadata={"user_data": user.dict()}
        )
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")
    

@router.post("/{user_id}/assign-company/{company_id}", summary="Привязать транспортную компанию к пользователю")
async def assign_company_to_user(
    user_id: UUID,
    company_id: UUID,
    db: AsyncSession = Depends(get_session), 
    request: Request = None
):
    try:
        result_user = await db.execute(select(User).where(User.id == user_id))
        user = result_user.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        result_company = await db.execute(select(TransportCompany).where(TransportCompany.id == company_id))
        company = result_company.scalar_one_or_none()
        if not company:
            raise HTTPException(status_code=404, detail="Транспортная компания не найдена")

        user.transport_company_id = company.id

        await db.commit()
        await db.refresh(user)

        return {
            "message": f"Компания '{company.name}' успешно привязана к пользователю {user.username}",
            "user_id": str(user.id),
            "company_id": str(company.id)
        }
    except Exception as e:
        await log_system_error(
            error=e,
            title="Ошибка привязки транспортной компании к пользователю",
            section="users",
            request=request,
            component_name="assign_company_to_user",
            additional_metadata={"user_data": user.dict()}
        )
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")
    