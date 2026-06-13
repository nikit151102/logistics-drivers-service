from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from database.database_app import get_session
from datetime import datetime
from models import Address
from schemas.schemas import AddressCreate, AddressOut
from uuid import UUID
import pandas as pd
from fastapi import UploadFile, File, HTTPException, Depends
import io
from utils.error_logger import log_system_error

router = APIRouter(prefix="/addresses", tags=["Адреса"])


def snake_to_pascal(snake_str: str) -> str:

    if not isinstance(snake_str, str):
        return snake_str 
    components = [comp for comp in snake_str.split('_') if comp]
    return ''.join(comp.capitalize() for comp in components)


def dict_keys_to_pascal_case(obj):

    if isinstance(obj, list):
        return [dict_keys_to_pascal_case(item) for item in obj]
    elif isinstance(obj, dict):
        return {
            snake_to_pascal(key): dict_keys_to_pascal_case(value)
            for key, value in obj.items()
        }
    else:
        return obj
    

@router.get("/", response_model=list[AddressOut], summary="Список адресов")
async def get_addresses(db: AsyncSession = Depends(get_session), request: Request = None):
    try:
        result = await db.execute(select(Address))
        return result.scalars().all()
    except Exception as e:
        await log_system_error(
            error=e,
            title="Ошибка при получении адресов",
            section="addresses",
            request=request,
            component_name="get_addresses",
            additional_metadata={}
        )
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@router.get("/camelCase/", summary="Список адресов")
async def get_addressesCamelCase(db: AsyncSession = Depends(get_session), request: Request = None):
    try:
        result = await db.execute(select(Address))
        address = result.scalars().all()
        address_dicts = []
        for addres in address:
            addres_dict = {key: value for key, value in addres.__dict__.items() if key != '_sa_instance_state'}
            address_dicts.append(addres_dict)
        
        return dict_keys_to_pascal_case(address_dicts)
    except Exception as e:
        await log_system_error(
            error=e,
            title="Ошибка при получении адресов camelCase",
            section="addresses",
            request=request,
            component_name="get_addressesCamelCase",
            additional_metadata={}
        )
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")



@router.get("/{address_id}", response_model=AddressOut, summary="Получить адрес по ID")
async def get_address(address_id: UUID, db: AsyncSession = Depends(get_session), request: Request = None):
    try:
        result = await db.execute(select(Address).where(Address.id == address_id))
        address = result.scalar_one_or_none()
        if not address:
            raise HTTPException(status_code=404, detail="Адрес не найден")
        return address
    except Exception as e:
        await log_system_error(
            error=e,
            title="Ошибка при получении адреса по ID",
            section="addresses",
            request=request,
            component_name="get_address",
            additional_metadata={}
        )
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")



@router.post("/", response_model=AddressOut, summary="Создать адрес")
async def create_address(address: AddressCreate, db: AsyncSession = Depends(get_session), request: Request = None):
    try:
        db_address = Address(**address.dict())
        db.add(db_address)
        await db.commit()
        await db.refresh(db_address)
        return db_address
    except Exception as e:
        await log_system_error(
            error=e,
            title="Ошибка при создании адреса",
            section="addresses",
            request=request,
            component_name="create_address",
            additional_metadata={}
        )
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")



@router.put("/{address_id}", response_model=AddressOut, summary="Обновить адрес")
async def update_address(address_id: UUID, address: AddressCreate, db: AsyncSession = Depends(get_session), request: Request = None):
    try:
        result = await db.execute(select(Address).where(Address.id == address_id))
        db_address = result.scalar_one_or_none()
        if not db_address:
            raise HTTPException(status_code=404, detail="Адрес не найден")

        for key, value in address.dict().items():
            setattr(db_address, key, value)

        if hasattr(db_address, "changeDateTime"):
            db_address.changeDateTime = datetime.utcnow()

        db.add(db_address)
        await db.commit()
        await db.refresh(db_address)
        return db_address
    except Exception as e:
        await log_system_error(
            error=e,
            title="Ошибка при обновлении данных адреса",
            section="addresses",
            request=request,
            component_name="update_address",
            additional_metadata={}
        )
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")



@router.delete("/{address_id}", summary="Удалить адрес")
async def delete_address(address_id: UUID, db: AsyncSession = Depends(get_session), request: Request = None):
    try:
        result = await db.execute(select(Address).where(Address.id == address_id))
        db_address = result.scalar_one_or_none()
        if not db_address:
            raise HTTPException(status_code=404, detail="Адрес не найден")

        await db.delete(db_address)
        await db.commit()
        return {"detail": "Адрес успешно удалён"}
    except Exception as e:
        await log_system_error(
            error=e,
            title="Ошибка при удалении адреса",
            section="addresses",
            request=request,
            component_name="delete_address",
            additional_metadata={}
        )
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@router.post("/bulk-upload", summary="Загрузить адреса из Excel файла")
async def bulk_upload_addresses(
    file: UploadFile = File(..., description="Excel файл с колонками: address_1c, latitude, longitude"),
    db: AsyncSession = Depends(get_session), 
    request: Request = None
):
    try:
        # Проверяем расширение файла
        if not file.filename.endswith(('.xlsx', '.xls')):
            raise HTTPException(status_code=400, detail="Файл должен быть в формате Excel (.xlsx или .xls)")
        
        try:
            # Читаем файл в память
            contents = await file.read()
            df = pd.read_excel(io.BytesIO(contents))
            
            # Проверяем наличие обязательных колонок
            required_columns = ['address_1c', 'latitude', 'longitude']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                raise HTTPException(
                    status_code=400, 
                    detail=f"В файле отсутствуют обязательные колонки: {', '.join(missing_columns)}"
                )
            
            # Удаляем пустые строки в address_1c
            df = df.dropna(subset=['address_1c'])
            
            # Получаем существующие адреса для проверки дубликатов
            result = await db.execute(select(Address.address_1c))
            existing_addresses = {row[0] for row in result.fetchall()}
            
            # Подготавливаем данные для вставки
            addresses_to_create = []
            new_addresses_count = 0
            duplicate_addresses_count = 0
            
            for _, row in df.iterrows():
                address_1c = str(row['address_1c']).strip()
                
                # Пропускаем пустые адреса
                if not address_1c:
                    continue
                    
                # Проверяем на дубликат
                if address_1c in existing_addresses:
                    duplicate_addresses_count += 1
                    continue
                
                # Создаем объект адреса только с тремя полями
                address_data = {
                    'address_1c': address_1c,
                    'latitude': float(row['latitude']) if pd.notna(row['latitude']) else None,
                    'longitude': float(row['longitude']) if pd.notna(row['longitude']) else None,
                }
                
                addresses_to_create.append(Address(**address_data))
                existing_addresses.add(address_1c)  # Добавляем в множество для избежания дубликатов в текущем файле
                new_addresses_count += 1
            
            # Сохраняем в базу данных
            if addresses_to_create:
                db.add_all(addresses_to_create)
                await db.commit()
                
                # Обновляем объекты чтобы получить их ID
                for address in addresses_to_create:
                    await db.refresh(address)
            
            return {
                "message": "Обработка файла завершена",
                "total_rows_in_file": len(df),
                "new_addresses_created": new_addresses_count,
                "duplicates_skipped": duplicate_addresses_count,
                "addresses": [
                    {
                        "id": str(address.id),
                        "address_1c": address.address_1c,
                        "latitude": address.latitude,
                        "longitude": address.longitude
                    } for address in addresses_to_create
                ]
            }
            
        except pd.errors.EmptyDataError:
            raise HTTPException(status_code=400, detail="Файл пуст")
        except pd.errors.ParserError:
            raise HTTPException(status_code=400, detail="Ошибка при чтении файла")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Ошибка в данных: {str(e)}")
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Ошибка при обработке файла: {str(e)}")
        
    except Exception as e:
        await log_system_error(
            error=e,
            title="Ошибка при импорте адресов из Excel файла",
            section="addresses",
            request=request,
            component_name="bulk_upload_addresses",
            additional_metadata={}
        )
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

