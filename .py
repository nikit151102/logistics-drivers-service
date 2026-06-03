from datetime import datetime
from fastapi import FastAPI, HTTPException, Query
import httpx
from pydantic import BaseModel
from database.database_app import create_db_if_not_exists, create_tables
from migration import run_auto_migrations
from fastapi.middleware.cors import CORSMiddleware
from routers import addresses, deliveryTypes, legalEntities, loading_places, loadings, stats, tariffs, transportCompanies, users, vehicles, logs, auth, trail, stores
from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, or_, select
from database.database_app import get_session
from models import Address, DeliveryType, LegalEntityType, Loading, LoadingPlace, LoadingStatusLog, RoutePointStatusEnum, RouteStatusEnum, StatusEnum, Store, Tariff, TransportCompany, User, Vehicle, LogEntry, RoutePlan, RoutePoint, RoutePointStatusLog

create_db_if_not_exists()
create_tables()

# выполняем autogenerate+upgrade
# run_auto_migrations()

app = FastAPI(debug=True)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],  
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(vehicles.router)
app.include_router(logs.router)
app.include_router(trail.router)
app.include_router(stats.router)
app.include_router(addresses.router)
app.include_router(stores.router)
app.include_router(legalEntities.router)
app.include_router(deliveryTypes.router)
app.include_router(transportCompanies.router)
app.include_router(tariffs.router)
app.include_router(loading_places.router)
app.include_router(loadings.router)

# Определение модели для ответа
class GeocodeResponse(BaseModel):
    lat: float
    lng: float

@app.get("/geocode")
async def geocode(address: str):
    url = f"https://nominatim.openstreetmap.org/search?format=json&q={address}"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers={"User-Agent": "YourAppName (contact@yourapp.com)"})
            response.raise_for_status()  
            data = response.json()
            
            if not data:
                raise HTTPException(status_code=404, detail="Address not found")
            
            return GeocodeResponse(lat=float(data[0]["lat"]), lng=float(data[0]["lon"]))
        
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=f"HTTP error occurred: {e}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
import httpx
import pandas as pd
from io import BytesIO

@app.post("/apply-migrations", summary="Автоматическое применение миграций")
async def apply_migrations():
    try:
        run_auto_migrations()
        return {"message": "Миграции успешно применены"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/geocode_excel")
async def geocode_excel(file: UploadFile = File(...)):
    # Проверка формата файла
    if not file.filename.endswith((".xls", ".xlsx")):
        raise HTTPException(status_code=400, detail="Файл должен быть в формате Excel (.xls или .xlsx)")

    # Чтение Excel-файла
    try:
        contents = await file.read()
        df = pd.read_excel(BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка чтения Excel: {str(e)}")

    # Проверка, что есть хотя бы один столбец
    if df.shape[1] < 1:
        raise HTTPException(status_code=400, detail="Файл должен содержать хотя бы один столбец с адресами")

    # Берём первый столбец как адреса
    address_col = df.columns[0]
    addresses = df[address_col].astype(str).tolist()

    results = []
    async with httpx.AsyncClient() as client:
        for address in addresses:
            try:
                url = "https://nominatim.openstreetmap.org/search"
                params = {"format": "json", "q": address}
                headers = {"User-Agent": "YourAppName (contact@yourapp.com)"}

                resp = await client.get(url, params=params, headers=headers)
                resp.raise_for_status()
                data = resp.json()

                if data:
                    lat = float(data[0]["lat"])
                    lon = float(data[0]["lon"])
                else:
                    lat, lon = None, None

                results.append({"address": address, "lat": lat, "lon": lon})
            except Exception:
                results.append({"address": address, "lat": None, "lon": None})

    # Создаём новый Excel с координатами
    result_df = pd.DataFrame(results)
    output = BytesIO()
    result_df.to_excel(output, index=False)
    output.seek(0)

    # Возвращаем Excel как файл
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="geocoded_addresses.xlsx"'
        },
    )

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
@app.post("/filter_addresses")
async def filter_addresses(
    file: UploadFile = File(...),
    keyword: str = Form(...)
):
    # Проверка формата файла
    if not file.filename.endswith((".xls", ".xlsx")):
        raise HTTPException(status_code=400, detail="Файл должен быть в формате Excel (.xls или .xlsx)")

    # Чтение Excel-файла
    try:
        contents = await file.read()
        df = pd.read_excel(BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка чтения Excel: {str(e)}")

    # Проверяем, что есть хотя бы один столбец
    if df.shape[1] < 1:
        raise HTTPException(status_code=400, detail="Файл должен содержать хотя бы один столбец с адресами")

    # Берём первый столбец как адреса
    address_col = df.columns[0]

    # Фильтрация: удаляем строки, где встречается ключевое слово (нечувствительно к регистру)
    df_filtered = df[~df[address_col].astype(str).str.contains(keyword, case=False, na=False)]

    # Сохраняем результат в Excel
    output = BytesIO()
    df_filtered.to_excel(output, index=False)
    output.seek(0)

    # Возвращаем файл пользователю
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="filtered_addresses.xlsx"'
        },
    )

@app.post("/clear_database", summary="Очистить все таблицы базы данных")
async def clear_database(db: AsyncSession = Depends(get_session)):
    try:
        await db.execute(delete(RoutePointStatusLog))
        await db.execute(delete(RoutePoint))
        await db.execute(delete(RoutePlan))
        await db.execute(delete(LogEntry))
        await db.execute(delete(Vehicle))
        await db.execute(delete(User))

        await db.commit()
        return {"detail": "База данных успешно очищена"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка при очистке базы: {e}")





from sqlalchemy import or_


def dict_keys_to_camel_case(obj):

    if isinstance(obj, list):
        return [dict_keys_to_camel_case(i) for i in obj]
    elif isinstance(obj, dict):
        new_obj = {}
        for k, v in obj.items():
            new_key = k[0].upper() + k[1:] if k else k
            new_obj[new_key] = dict_keys_to_camel_case(v)
        return new_obj
    else:
        return obj
    
def snake_to_pascal(snake_str: str) -> str:
    """Преобразует 'snake_case' → 'PascalCase'."""
    if not isinstance(snake_str, str):
        return snake_str  # защита от неожиданных типов
    components = [comp for comp in snake_str.split('_') if comp]
    return ''.join(comp.capitalize() for comp in components)


def dict_keys_to_pascal_case(obj):
    """Рекурсивно преобразует ключи словарей из snake_case в PascalCase."""
    if isinstance(obj, list):
        return [dict_keys_to_pascal_case(item) for item in obj]
    elif isinstance(obj, dict):
        return {
            snake_to_pascal(key): dict_keys_to_pascal_case(value)
            for key, value in obj.items()
        }
    else:
        return obj
@app.get("/get_changes", summary="Получить объекты, созданные или изменённые после даты")
async def get_changes(
    since: datetime,
    db: AsyncSession = Depends(get_session)
):
    results = {}

    models_to_check = {
        "Directories": { 
            "Users": User,
            "Vehicles": Vehicle,
            "TransportCompanies": TransportCompany,
            "Addresses": Address,
            "Stores": Store,
            "Tariffs": Tariff,
            "LoadingPlaces": LoadingPlace,
        },
        "StaticDirectories": {  
            "LegalEntityTypes": LegalEntityType,
            "DeliveryTypes": DeliveryType
        },
        "Documents": { 
            "RoutePlans": RoutePlan,
            "RoutePoints": RoutePoint,
            "Loadings": Loading,
            "LogEntries": LogEntry,
            "RoutePointStatusLogs": RoutePointStatusLog,
            "LoadingStatusLogs": LoadingStatusLog,
        }
    }

    for section_name, section_models in models_to_check.items():
        results[section_name] = {}
        for model_name, model_class in section_models.items():
            query = await db.execute(
                select(model_class).filter(
                    or_(
                        model_class.createDateTime > since,
                        model_class.changeDateTime > since
                    )
                )
            )
            objs = [obj.__dict__ for obj in query.scalars().all()]
            for obj in objs:
                obj.pop("_sa_instance_state", None)
            # ПРАВИЛЬНО:
            results[section_name][model_name] = dict_keys_to_pascal_case(objs)
            

    return results









# from sqlalchemy.orm import selectinload
# from datetime import datetime, date
# from datetime import timedelta



# from sqlalchemy.orm import selectinload
# from datetime import datetime, date, timedelta

# def calculate_active_time_route_point(point):
#     work_start_statuses = {RoutePointStatusEnum.en_route, RoutePointStatusEnum.loading}
#     work_end_statuses = {RoutePointStatusEnum.completed, RoutePointStatusEnum.loading_completed}

#     active_time = timedelta(0)
#     start_time = None

#     for log in point.status_logs:
#         if log.status in work_start_statuses:
#             start_time = log.timestamp
#         elif log.status in work_end_statuses and start_time:
#             active_time += log.timestamp - start_time
#             start_time = None

#     return active_time


# def calculate_active_time_loading(loading):
#     work_start_statuses = {RoutePointStatusEnum.loading}
#     work_end_statuses = {RoutePointStatusEnum.loading_completed}

#     active_time = timedelta(0)
#     start_time = None

#     for log in loading.status_logs:
#         if log.status in work_start_statuses:
#             start_time = log.timestamp
#         elif log.status in work_end_statuses and start_time:
#             active_time += log.timestamp - start_time
#             start_time = None

#     return active_time




# @app.get("/split", summary="Разбить маршруты по типам (реализация, перемещение, погрузка) с детализацией по водителям")
# async def get_split_routes(
#     start_date: date = Query(..., description="Начало периода"),
#     end_date: date = Query(..., description="Конец периода"),
#     db: AsyncSession = Depends(get_session)
# ):
#     # 1️⃣ Точки маршрутов
#     result = await db.execute(
#         select(RoutePoint)
#         .join(RoutePoint.route_plan)
#         .options(
#             selectinload(RoutePoint.route_plan).selectinload(RoutePlan.vehicle).selectinload(Vehicle.owner),
#             selectinload(RoutePoint.address),
#             selectinload(RoutePoint.store),
#             selectinload(RoutePoint.status_logs),
#         )
#         .where(RoutePlan.date >= start_date)
#         .where(RoutePlan.date <= end_date)
#     )
#     points = result.scalars().all()

#     # 2️⃣ Погрузки
#     loading_result = await db.execute(
#         select(Loading)
#         .join(Loading.route_plan)
#         .where(RoutePlan.date >= start_date)
#         .where(RoutePlan.date <= end_date)
#         .options(
#             selectinload(Loading.loading_place).selectinload(LoadingPlace.address),
#             selectinload(Loading.route_plan).selectinload(RoutePlan.vehicle).selectinload(Vehicle.owner),
#             selectinload(Loading.status_logs),
#         )
#     )
#     loadings = loading_result.scalars().all()

#     realizations, transfers, loading_points = [], [], []
#     total_payment_realizations = 0
#     total_payment_transfers = 0

#     driver_summary = {}

#     # 3️⃣ Обработка точек маршрута
#     for point in points:
#         driver_obj = None
#         driver_id = None
#         driver_rate = 0

#         if point.route_plan and point.route_plan.vehicle and point.route_plan.vehicle.owner:
#             driver = point.route_plan.vehicle.owner
#             driver_id = driver.id
#             driver_obj = {
#                 "id": driver.id,
#                 "first_name": driver.first_name,
#                 "last_name": driver.last_name,
#                 "middle_name": driver.middle_name,
#                 "rate": driver.rate or 0,
#             }
#             driver_rate = driver.rate or 0

#         active_minutes = int(calculate_active_time_route_point(point).total_seconds() / 60)
#         doc_lower = (point.doc or "").lower()

#         data = {
#             "type": 0 if "реализа" in doc_lower else 1,
#             "id": point.id,
#             "route_plan_id": point.route_plan_id,
#             "vehicle": point.route_plan.vehicle.plate_number if point.route_plan and point.route_plan.vehicle else None,
#             "driver": driver_obj,
#             "doc": point.doc,
#             "address": point.address.address_1c if point.address else None,
#             "arrival_time": point.arrival_time,
#             "departure_time": point.departure_time,
#             "active_duration_minutes": active_minutes,
#             "payment": point.payment or 0,
#             "note": point.note,
#             "driver_earnings": round(driver_rate * (active_minutes / 60), 2)
#         }

#         # Списки по типам
#         if "реализа" in doc_lower:
#             realizations.append(data)
#             total_payment_realizations += point.payment or 0
#         elif "перемещ" in doc_lower:
#             transfers.append(data)
#             total_payment_transfers += point.payment or 0

#         # Summary по водителю
#         if driver_id:
#             if driver_id not in driver_summary:
#                 driver_summary[driver_id] = {
#                     "driver": driver_obj,
#                     "total_active_minutes": 0,
#                     "total_earnings": 0.0,
#                     "points_count": {"realizations": 0, "transfers": 0, "loadings": 0},
#                     "total_payment": {"realizations": 0, "transfers": 0}
#                 }

#             ds = driver_summary[driver_id]
#             ds["total_active_minutes"] += active_minutes
#             ds["total_earnings"] += data["driver_earnings"]
#             if "реализа" in doc_lower:
#                 ds["points_count"]["realizations"] += 1
#                 ds["total_payment"]["realizations"] += point.payment or 0
#             elif "перемещ" in doc_lower:
#                 ds["points_count"]["transfers"] += 1
#                 ds["total_payment"]["transfers"] += point.payment or 0

#     # 4️⃣ Обработка погрузок
#     for loading in loadings:
#         driver_obj = None
#         driver_id = None
#         driver_rate = 0

#         if loading.route_plan and loading.route_plan.vehicle and loading.route_plan.vehicle.owner:
#             driver = loading.route_plan.vehicle.owner
#             driver_id = driver.id
#             driver_obj = {
#                 "id": driver.id,
#                 "first_name": driver.first_name,
#                 "last_name": driver.last_name,
#                 "middle_name": driver.middle_name,
#                 "rate": driver.rate or 0,
#             }
#             driver_rate = driver.rate or 0

#         active_minutes = int(calculate_active_time_loading(loading).total_seconds() / 60)

#         loading_data = {
#             "type": 2,
#             "id": loading.id,
#             "route_plan_id": loading.route_plan_id,
#             "vehicle": loading.route_plan.vehicle.plate_number if loading.route_plan and loading.route_plan.vehicle else None,
#             "driver": driver_obj,
#             "doc": loading.doc_number,
#             "address": loading.loading_place.address.address_1c if loading.loading_place and loading.loading_place.address else None,
#             "start_time": loading.start_time,
#             "end_time": loading.end_time,
#             "active_duration_minutes": active_minutes,
#             "payment": 0,
#             "note": loading.note,
#             "driver_earnings": round(driver_rate * (active_minutes / 60), 2)
#         }

#         loading_points.append(loading_data)

#         if driver_id:
#             if driver_id not in driver_summary:
#                 driver_summary[driver_id] = {
#                     "driver": driver_obj,
#                     "total_active_minutes": 0,
#                     "total_earnings": 0.0,
#                     "points_count": {"realizations": 0, "transfers": 0, "loadings": 0},
#                     "total_payment": {"realizations": 0, "transfers": 0}
#                 }

#             ds = driver_summary[driver_id]
#             ds["total_active_minutes"] += active_minutes
#             ds["total_earnings"] += loading_data["driver_earnings"]
#             ds["points_count"]["loadings"] += 1

#     combined = realizations + transfers + loading_points
#     total_active_minutes = sum(r["active_duration_minutes"] for r in combined)

#     return {
#         "period": {"start_date": start_date, "end_date": end_date},
#         "summary": {
#             "realizations": len(realizations),
#             "transfers": len(transfers),
#             "loadings": len(loading_points),
#             "total_active_minutes": total_active_minutes,
#             "total_payment_realizations": total_payment_realizations,
#             "total_payment_transfers": total_payment_transfers,
#         },
#         "driver_summary": list(driver_summary.values()),  # список, чтобы в JSON было удобно
#         "routes": combined
#     }







from sqlalchemy.orm import selectinload
from datetime import datetime, date, timedelta
from collections import defaultdict

def calculate_active_time_route_point(point):
    work_start_statuses = {RoutePointStatusEnum.en_route, RoutePointStatusEnum.loading}
    work_end_statuses = {RoutePointStatusEnum.completed, RoutePointStatusEnum.loading_completed}

    active_time = timedelta(0)
    start_time = None

    for log in point.status_logs:
        if log.status in work_start_statuses:
            start_time = log.timestamp
        elif log.status in work_end_statuses and start_time:
            active_time += log.timestamp - start_time
            start_time = None

    return active_time


def calculate_active_time_loading(loading):
    work_start_statuses = {RoutePointStatusEnum.loading}
    work_end_statuses = {RoutePointStatusEnum.loading_completed}

    active_time = timedelta(0)
    start_time = None

    for log in loading.status_logs:
        if log.status in work_start_statuses:
            start_time = log.timestamp
        elif log.status in work_end_statuses and start_time:
            active_time += log.timestamp - start_time
            start_time = None

    return active_time


@app.get("/split", summary="Разбить маршруты по типам (реализация, перемещение, погрузка) с аналитикой по водителям")
async def get_split_routes(
    start_date: date = Query(..., description="Начало периода"),
    end_date: date = Query(..., description="Конец периода"),
    db: AsyncSession = Depends(get_session)
):
    # 1️⃣ Получаем точки маршрутов
    result = await db.execute(
        select(RoutePoint)
        .join(RoutePoint.route_plan)
        .options(
            selectinload(RoutePoint.route_plan).selectinload(RoutePlan.vehicle).selectinload(Vehicle.owner),
            selectinload(RoutePoint.address),
            selectinload(RoutePoint.status_logs),
        )
        .where(RoutePlan.date >= start_date)
        .where(RoutePlan.date <= end_date)
    )
    points = result.scalars().all()

    # 2️⃣ Получаем погрузки
    loading_result = await db.execute(
        select(Loading)
        .join(Loading.route_plan)
        .options(
            selectinload(Loading.loading_place).selectinload(LoadingPlace.address),
            selectinload(Loading.route_plan).selectinload(RoutePlan.vehicle).selectinload(Vehicle.owner),
            selectinload(Loading.status_logs),
        )
        .where(RoutePlan.date >= start_date)
        .where(RoutePlan.date <= end_date)
    )
    loadings = loading_result.scalars().all()

    # Контейнеры
    realizations, transfers, loading_points = [], [], []
    total_payment_realizations = 0
    total_payment_transfers = 0
    driver_summary, vehicle_summary = {}, {}
    daily_summary = defaultdict(lambda: {"active_minutes": 0, "earnings": 0, "points": 0})

    # 3️⃣ Обработка точек маршрута
    for point in points:
        driver_obj, driver_id, driver_rate = None, None, 0

        if point.route_plan and point.route_plan.vehicle and point.route_plan.vehicle.owner:
            driver = point.route_plan.vehicle.owner
            driver_id = driver.id
            driver_rate = driver.rate or 0
            driver_obj = {
                "id": driver.id,
                "first_name": driver.first_name,
                "last_name": driver.last_name,
                "middle_name": driver.middle_name,
                "rate": driver_rate,
            }

        active_minutes = int(calculate_active_time_route_point(point).total_seconds() / 60)
        doc_lower = (point.doc or "").lower()

        data = {
            "type": 0 if "реализа" in doc_lower else 1,
            "id": point.id,
            "route_plan_id": point.route_plan_id,
            "vehicle": point.route_plan.vehicle.plate_number if point.route_plan and point.route_plan.vehicle else None,
            "driver": driver_obj,
            "doc": point.doc,
            "address": point.address.address_1c if point.address else None,
            "arrival_time": point.arrival_time,
            "departure_time": point.departure_time,
            "active_duration_minutes": active_minutes,
            "payment": point.payment or 0,
            "note": point.note,
            "driver_earnings": round(driver_rate * (active_minutes / 60), 2),
        }

        # Списки по типам
        if "реализа" in doc_lower:
            realizations.append(data)
            total_payment_realizations += point.payment or 0
        elif "перемещ" in doc_lower:
            transfers.append(data)
            total_payment_transfers += point.payment or 0

        # ⏱ Сводка по водителю
        if driver_id:
            ds = driver_summary.setdefault(driver_id, {
                "driver": driver_obj,
                "total_active_minutes": 0,
                "total_earnings": 0.0,
                "points_count": {"realizations": 0, "transfers": 0, "loadings": 0},
                "total_payment": {"realizations": 0, "transfers": 0},
            })
            ds["total_active_minutes"] += active_minutes
            ds["total_earnings"] += data["driver_earnings"]
            if "реализа" in doc_lower:
                ds["points_count"]["realizations"] += 1
                ds["total_payment"]["realizations"] += point.payment or 0
            elif "перемещ" in doc_lower:
                ds["points_count"]["transfers"] += 1
                ds["total_payment"]["transfers"] += point.payment or 0

        # 🚛 Сводка по машине
        if data["vehicle"]:
            vs = vehicle_summary.setdefault(data["vehicle"], {
                "vehicle": data["vehicle"],
                "total_active_minutes": 0,
                "total_earnings": 0.0,
                "points_count": {"realizations": 0, "transfers": 0, "loadings": 0},
            })
            vs["total_active_minutes"] += active_minutes
            vs["total_earnings"] += data["driver_earnings"]
            if data["type"] == 0:
                vs["points_count"]["realizations"] += 1
            elif data["type"] == 1:
                vs["points_count"]["transfers"] += 1

        # 📅 Дневная статистика
        if point.arrival_time:
            key = point.arrival_time.date().isoformat()
            daily_summary[key]["active_minutes"] += active_minutes
            daily_summary[key]["earnings"] += data["driver_earnings"]
            daily_summary[key]["points"] += 1

    # 4️⃣ Погрузки
    for loading in loadings:
        driver_obj, driver_id, driver_rate = None, None, 0
        if loading.route_plan and loading.route_plan.vehicle and loading.route_plan.vehicle.owner:
            driver = loading.route_plan.vehicle.owner
            driver_id = driver.id
            driver_rate = driver.rate or 0
            driver_obj = {
                "id": driver.id,
                "first_name": driver.first_name,
                "last_name": driver.last_name,
                "middle_name": driver.middle_name,
                "rate": driver_rate,
            }

        active_minutes = int(calculate_active_time_loading(loading).total_seconds() / 60)
        data = {
            "type": 2,
            "id": loading.id,
            "route_plan_id": loading.route_plan_id,
            "vehicle": loading.route_plan.vehicle.plate_number if loading.route_plan and loading.route_plan.vehicle else None,
            "driver": driver_obj,
            "doc": loading.doc_number,
            "address": loading.loading_place.address.address_1c if loading.loading_place and loading.loading_place.address else None,
            "start_time": loading.start_time,
            "end_time": loading.end_time,
            "active_duration_minutes": active_minutes,
            "payment": 0,
            "note": loading.note,
            "driver_earnings": round(driver_rate * (active_minutes / 60), 2),
        }

        loading_points.append(data)

        # Водитель
        if driver_id:
            ds = driver_summary.setdefault(driver_id, {
                "driver": driver_obj,
                "total_active_minutes": 0,
                "total_earnings": 0.0,
                "points_count": {"realizations": 0, "transfers": 0, "loadings": 0},
                "total_payment": {"realizations": 0, "transfers": 0},
            })
            ds["total_active_minutes"] += active_minutes
            ds["total_earnings"] += data["driver_earnings"]
            ds["points_count"]["loadings"] += 1

        # Машина
        if data["vehicle"]:
            vs = vehicle_summary.setdefault(data["vehicle"], {
                "vehicle": data["vehicle"],
                "total_active_minutes": 0,
                "total_earnings": 0.0,
                "points_count": {"realizations": 0, "transfers": 0, "loadings": 0},
            })
            vs["total_active_minutes"] += active_minutes
            vs["total_earnings"] += data["driver_earnings"]
            vs["points_count"]["loadings"] += 1

    # 5️⃣ Финальные расчёты
    combined = realizations + transfers + loading_points
    total_active_minutes = sum(r["active_duration_minutes"] for r in combined)
    total_earnings = sum(r["driver_earnings"] for r in combined)

    finance_summary = {
        "total_payment": total_payment_realizations + total_payment_transfers,
        "total_driver_earnings": total_earnings,
        "avg_earning_per_hour": round(total_earnings / (total_active_minutes / 60), 2) if total_active_minutes else 0,
        "avg_earning_per_point": round(total_earnings / len(combined), 2) if combined else 0,
    }

    # 🕒 Диапазон активности
    times = [
        t for r in combined for t in [r.get("arrival_time"), r.get("start_time"), r.get("departure_time"), r.get("end_time")]
        if t
    ]
    time_distribution = {
        "earliest_start": min(times) if times else None,
        "latest_end": max(times) if times else None,
    }

    # 🏆 Топы
    top_drivers_by_earnings = sorted(driver_summary.values(), key=lambda d: d["total_earnings"], reverse=True)[:5]
    top_drivers_by_activity = sorted(driver_summary.values(), key=lambda d: d["total_active_minutes"], reverse=True)[:5]

    return {
        "period": {"start_date": start_date, "end_date": end_date},
        "summary": {
            "realizations": len(realizations),
            "transfers": len(transfers),
            "loadings": len(loading_points),
            "total_active_minutes": total_active_minutes,
        },
        "finance_summary": finance_summary,
        "time_distribution": time_distribution,
        "driver_summary": list(driver_summary.values()),
        "vehicle_summary": list(vehicle_summary.values()),
        "daily_summary": daily_summary,
        "top_drivers_by_earnings": top_drivers_by_earnings,
        "top_drivers_by_activity": top_drivers_by_activity,
        "routes": combined,
    }
