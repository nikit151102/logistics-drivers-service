from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from database.database_app import get_session
from models import User
from auth import verify_password, create_access_token  
from datetime import timedelta
from auth import SECRET_KEY, ALGORITHM
from jose import JWTError, jwt
from utils.error_logger import log_system_error

router = APIRouter(prefix="/auth", tags=["Авторизация"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

@router.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_session), request: Request = None):
    try:
        result = await db.execute(select(User).where(User.username == form_data.username))
        user = result.scalar_one_or_none()
        if not user or not verify_password(form_data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный логин или пароль",
                headers={"WWW-Authenticate": "Bearer"},
            )

        access_token_expires = timedelta(minutes=60)
        access_token = create_access_token(
            data={"sub": str(user.id)}
        )
        return {"access_token": access_token, "token_type": "bearer"}
    except Exception as e:
        await log_system_error(
            error=e,
            title="Ошибка при авторизации водителя",
            section="auth",
            request=request,
            component_name="login",
            additional_metadata={}
        )
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@router.post("/me")
async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_session), request: Request = None):
    try:
        """Проверка и декодирование токена, возврат текущего пользователя"""
        credentials_exception = HTTPException(
            status_code=401,
            detail="Не удалось авторизовать пользователя",
            headers={"WWW-Authenticate": "Bearer"},
        )
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id: str = payload.get("sub")
            if user_id is None:
                raise credentials_exception
        except JWTError:
            raise credentials_exception

        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            raise credentials_exception
        return user
    except Exception as e:
        await log_system_error(
            error=e,
            title="Ошибка при получении личных данных водителя",
            section="auth",
            request=request,
            component_name="get_current_user",
            additional_metadata={}
        )
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")
