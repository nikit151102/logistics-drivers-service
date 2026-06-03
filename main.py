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


import math
import math
from collections import defaultdict
from datetime import date
from fastapi import Query, Depends
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload


import math
from collections import defaultdict
from datetime import date
from fastapi import Query, Depends
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload


from sqlalchemy.orm import selectinload
from datetime import datetime, date, timedelta
from collections import defaultdict



@app.get("/split", summary="Маршруты по типам с аналитикой")
async def get_split_routes(
    start_date: date = Query(...),
    end_date: date = Query(...),
    include_routes: bool = Query(True, description="Выводить детальные маршруты"),
    include_summary: bool = Query(True, description="Выводить аналитические сводки"),
    db: AsyncSession = Depends(get_session)
):
    # === Запрос маршрутов с загрузкой связей ===
    result = await db.execute(
        select(RoutePlan)
        .options(
            selectinload(RoutePlan.vehicle)
                .selectinload(Vehicle.owner)
                .selectinload(User.transport_company)
                .selectinload(TransportCompany.legal_entity_type),
            selectinload(RoutePlan.points).selectinload(RoutePoint.address),
            selectinload(RoutePlan.points).selectinload(RoutePoint.status_logs),
            selectinload(RoutePlan.loadings)
                .selectinload(Loading.loading_place)
                .selectinload(LoadingPlace.address),
            selectinload(RoutePlan.loadings).selectinload(Loading.status_logs),
        )
        .where(RoutePlan.date >= start_date)
        .where(RoutePlan.date <= end_date)
    )
    route_plans = result.scalars().all()

    # === агрегирующие словари ===
    driver_summary, vehicle_summary, company_summary = {}, {}, {}
    daily_summary = defaultdict(lambda: {"active_minutes": 0, "earnings": 0.0, "points": 0})
    total_active_minutes = 0
    total_earnings = 0.0
    routes_output = []

    def safe_float(val: float) -> float:
        """Безопасное преобразование в float"""
        val = float(val or 0.0)
        return val if math.isfinite(val) else 0.0

    # === Основной цикл по маршрутам ===
    for route in route_plans:
        driver_obj, driver_id, driver_rate = None, None, 0.0
        company = None
        legal_type = None

        # === Водитель, компания и тип юрлица ===
        if route.vehicle and route.vehicle.owner:
            driver = route.vehicle.owner
            driver_id = driver.id
            driver_rate = safe_float(driver.rate)
            company = driver.transport_company
            legal_type = company.legal_entity_type if company else None

            driver_obj = {
                "id": driver.id,
                "first_name": driver.first_name,
                "last_name": driver.last_name,
                "middle_name": driver.middle_name,
                "rate": driver_rate,
                "transport_company": {
                    "id": company.id if company else None,
                    "name": company.name if company else None,
                    "inn": company.inn if company else None,
                    "kpp": company.kpp if company else None,
                    "type": {
                        "id": legal_type.id if legal_type else None,
                        "name": legal_type.name if legal_type else None,
                    } if legal_type else None,
                } if company else None,
            }

            ds = driver_summary.setdefault(driver_id, {
                "driver": driver_obj,
                "total_active_minutes": 0,
                "total_earnings": 0.0,
                "points_count": {"realizations": 0, "transfers": 0, "loadings": 0},
            })

        points_grouped = {"realizations": [], "transfers": [], "loadings": []}

        # === точки маршрута ===
        for point in route.points:
            active_minutes = max(0, int(calculate_active_time_route_point(point).total_seconds() / 60))
            point_type = "realizations" if (point.doc or "").lower().find("реализа") >= 0 else "transfers"
            driver_earnings = safe_float(round(driver_rate * (active_minutes / 60), 2))

            data = {
                "id": point.id,
                "doc": point.doc,
                "address": point.address.address_1c if point.address else None,
                "arrival_time": point.arrival_time,
                "departure_time": point.departure_time,
                "active_duration_minutes": active_minutes,
                "payment": safe_float(point.payment),
                "note": point.note,
                "driver_earnings": driver_earnings,
            }
            points_grouped[point_type].append(data)

            total_active_minutes += active_minutes
            total_earnings += driver_earnings

            if point.arrival_time:
                key = point.arrival_time.date().isoformat()
                daily_summary[key]["active_minutes"] += active_minutes
                daily_summary[key]["earnings"] += driver_earnings
                daily_summary[key]["points"] += 1

            if driver_id:
                ds["total_active_minutes"] += active_minutes
                ds["total_earnings"] += driver_earnings
                ds["points_count"][point_type] += 1

        # === погрузки ===
        for loading in route.loadings:
            active_minutes = max(0, int(calculate_active_time_loading(loading).total_seconds() / 60))
            driver_earnings = safe_float(round(driver_rate * (active_minutes / 60), 2))

            data = {
                "id": loading.id,
                "doc": loading.doc_number,
                "address": loading.loading_place.address.address_1c
                    if loading.loading_place and loading.loading_place.address else None,
                "start_time": loading.start_time,
                "end_time": loading.end_time,
                "active_duration_minutes": active_minutes,
                "payment": 0.0,
                "note": loading.note,
                "driver_earnings": driver_earnings,
            }
            points_grouped["loadings"].append(data)

            total_active_minutes += active_minutes
            total_earnings += driver_earnings

            if loading.start_time:
                key = loading.start_time.date().isoformat()
                daily_summary[key]["active_minutes"] += active_minutes
                daily_summary[key]["earnings"] += driver_earnings
                daily_summary[key]["points"] += 1

            if driver_id:
                ds["total_active_minutes"] += active_minutes
                ds["total_earnings"] += driver_earnings
                ds["points_count"]["loadings"] += 1

        # === vehicle summary ===
        if route.vehicle:
            vs = vehicle_summary.setdefault(route.vehicle.plate_number, {
                "vehicle": route.vehicle.plate_number,
                "total_active_minutes": 0,
                "total_earnings": 0.0,
                "points_count": {"realizations": 0, "transfers": 0, "loadings": 0},
            })
            for t in ["realizations", "transfers", "loadings"]:
                vs["points_count"][t] += len(points_grouped[t])
                vs["total_active_minutes"] += sum(p["active_duration_minutes"] for p in points_grouped[t])
                vs["total_earnings"] += sum(safe_float(p["driver_earnings"]) for p in points_grouped[t])

        # === company summary ===
        if driver_id and company:
            cs = company_summary.setdefault(company.id, {
                "company": {
                    "id": company.id,
                    "name": company.name,
                    "inn": company.inn,
                    "kpp": company.kpp,
                    "type": legal_type.name if legal_type else None,
                },
                "total_active_minutes": 0,
                "total_earnings": 0.0,
                "drivers_count": set(),
            })
            cs["total_active_minutes"] += ds["total_active_minutes"]
            cs["total_earnings"] += ds["total_earnings"]
            cs["drivers_count"].add(driver_id)

        # === разбиваем маршрут по типам ===
        for type_name, points in points_grouped.items():
            if not points:
                continue

            stats = {
                "less_15": 0,
                "between_15_40": 0,
                "more_40": 0,
                "total_points": len(points)
            }
            for p in points:
                dur = p["active_duration_minutes"]
                if dur < 15:
                    stats["less_15"] += 1
                elif 15 <= dur <= 40:
                    stats["between_15_40"] += 1
                else:
                    stats["more_40"] += 1

            route_data = {
                "route_plan_id": route.id,
                "type": type_name,
                "vehicle": route.vehicle.plate_number if route.vehicle else None,
                "driver": driver_obj,
                "start_datetime": route.start_datetime,
                "end_datetime": route.end_datetime,
                "points": points if include_routes else [],
                "stats": stats,
                "total_active_minutes": sum(p["active_duration_minutes"] for p in points),
                "total_driver_earnings": safe_float(sum(p["driver_earnings"] for p in points)),
            }

            routes_output.append(route_data)

    # === общая аналитика ===
    avg_earning_per_hour = (
        safe_float(round(total_earnings / (total_active_minutes / 60), 2))
        if total_active_minutes > 0 else 0.0
    )

    finance_summary = {
        "total_driver_earnings": safe_float(total_earnings),
        "total_active_minutes": total_active_minutes,
        "avg_earning_per_hour": avg_earning_per_hour,
    }

    result = {
        "period": {"start_date": start_date, "end_date": end_date},
    }

    if include_summary:
        result.update({
            "driver_summary": list(driver_summary.values()),
            "vehicle_summary": list(vehicle_summary.values()),
            "daily_summary": daily_summary,
            "finance_summary": finance_summary,
            "company_summary": [
                {**v, "drivers_count": len(v["drivers_count"])} for v in company_summary.values()
            ],
        })

    if include_routes:
        result["routes"] = routes_output

    return result









from sqlalchemy.orm import selectinload
from datetime import datetime, date, timedelta
from collections import defaultdict
from calendar import monthrange

def validate_and_adjust_dates(start_date: date, end_date: date) -> tuple[date, date]:
    """Проверяет и корректирует даты для избежания ошибок"""
    if start_date > end_date:
        start_date, end_date = end_date, start_date
    
    try:
        date(end_date.year, end_date.month, end_date.day)
    except ValueError:
        last_day = monthrange(end_date.year, end_date.month)[1]
        end_date = end_date.replace(day=last_day)
    
    return start_date, end_date






from datetime import datetime, date, time, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from collections import defaultdict

# Для Алтайского края (UTC+7) нужно настроить смещение
# Рабочий день: 6:00-20:00 по местному времени (UTC+7)
# что соответствует 23:00-13:00 UTC
ALTAI_TIMEZONE_OFFSET = timedelta(hours=7)  # UTC+7

def convert_to_local_time(utc_time):
    """Конвертирует UTC время в местное время Алтайского края (UTC+7)"""
    if not utc_time:
        return None
    return utc_time + ALTAI_TIMEZONE_OFFSET

def filter_logs_by_work_time(logs, route_date):
    """Фильтрует логи по рабочему времени с учетом временной зоны"""
    if not logs or not route_date:
        return []
    
    filtered_logs = []
    for log in logs:
        if log.timestamp:
            # Конвертируем в местное время
            local_time = convert_to_local_time(log.timestamp)
            local_date = local_time.date()
            local_hour = local_time.hour
            
            # Только логи в тот же календарный день по местному времени
            # и в рабочее время (6:00-20:00 по местному времени)
            if local_date == route_date and 6 <= local_hour <= 20:
                filtered_logs.append(log)
    
    return filtered_logs

#def calculate_route_work_hours(plan):
#    """Рассчитывает часы работы для маршрута с фильтрацией ночных логов"""
#    if not plan.start_datetime:
#        return 0
    
#    route_date = plan.date.date() if plan.date else None
#    if not route_date:
#        return 0
    
#    # Конвертируем start_datetime в местное время
#    local_start_time = convert_to_local_time(plan.start_datetime)
    
    # Собираем все timestamp'ы из всех логов точек маршрута и погрузок
#    all_local_timestamps = []
    
    # Собираем timestamp'ы из точек маршрута (с фильтрацией)
#    for point in plan.points:
#        if point.status_logs:
            # Фильтруем логи по рабочему времени
#            filtered_logs = filter_logs_by_work_time(point.status_logs, route_date)
#            point_timestamps = [convert_to_local_time(log.timestamp) for log in filtered_logs]
#            all_local_timestamps.extend(point_timestamps)
    
    # Собираем timestamp'ы из погрузок (с фильтрацией)
#    for loading in plan.loadings:
#        if loading.status_logs:
            # Фильтруем логи по рабочему времени
#            filtered_logs = filter_logs_by_work_time(loading.status_logs, route_date)
#            loading_timestamps = [convert_to_local_time(log.timestamp) for log in filtered_logs]
#            all_local_timestamps.extend(loading_timestamps)
    
    # Если нет отфильтрованных логов, не можем рассчитать время работы
#    if not all_local_timestamps:
#        return 0
    
    # Находим самый первый и самый последний timestamp среди отфильтрованных логов
#    first_log_timestamp = min(all_local_timestamps)
#    last_timestamp = max(all_local_timestamps)
    
    # Начало рабочего дня - либо start_datetime маршрута, либо первый лог, если он раньше
#    actual_start_time = local_start_time
#    if first_log_timestamp < local_start_time:
#        actual_start_time = first_log_timestamp
    
    # Проверяем, что последний лог не раньше начала
#    if last_timestamp < actual_start_time:
#        return 0
    
    # Рассчитываем разницу между последним логом и фактическим началом рабочего дня
#    work_duration = last_timestamp - actual_start_time
    
    # Преобразуем в часы и округляем до 2 знаков
#    hours = work_duration.total_seconds() / 3600
    
    # Ограничиваем максимальное количество часов (например, 14 часов в день)
#    max_hours_per_day = 14.0
#    hours = min(hours, max_hours_per_day)
    
    # Также устанавливаем минимальное время работы (если есть логи, но разница маленькая)
#    min_hours_per_operation = 0.5  # минимум 30 минут на операцию
#    if len(all_local_timestamps) > 0 and hours < min_hours_per_operation:
#        hours = min_hours_per_operation
    
#    return round(max(0, hours), 2)

def calculate_route_work_hours(plan):

    if not plan.start_datetime:
        return 0
    
    route_date = plan.date.date() if plan.date else None
    if not route_date:
        return 0
    
    local_start_time = convert_to_local_time(plan.start_datetime)
    
    if plan.end_datetime:
        local_end_time = convert_to_local_time(plan.end_datetime)

        if local_end_time < local_start_time:
            return 0
        work_duration = local_end_time - local_start_time
        hours = work_duration.total_seconds() / 3600
        
        max_hours_per_day = 14.0
        hours = min(hours, max_hours_per_day)
        
        min_hours_per_operation = 0.5
        if hours < min_hours_per_operation:
            hours = min_hours_per_operation
        
        return round(max(0, hours), 2)
    
    all_local_timestamps = []
    
    for point in plan.points:
        if point.status_logs:
            filtered_logs = filter_logs_by_work_time(point.status_logs, route_date)
            point_timestamps = [convert_to_local_time(log.timestamp) for log in filtered_logs]
            all_local_timestamps.extend(point_timestamps)
    
    for loading in plan.loadings:
        if loading.status_logs:
            filtered_logs = filter_logs_by_work_time(loading.status_logs, route_date)
            loading_timestamps = [convert_to_local_time(log.timestamp) for log in filtered_logs]
            all_local_timestamps.extend(loading_timestamps)
    
    if not all_local_timestamps:
        return 0
    
    first_log_timestamp = min(all_local_timestamps)
    last_timestamp = max(all_local_timestamps)
    
    actual_start_time = local_start_time
    if first_log_timestamp < local_start_time:
        actual_start_time = first_log_timestamp
    
    if last_timestamp < actual_start_time:
        return 0
    
    work_duration = last_timestamp - actual_start_time
    
    hours = work_duration.total_seconds() / 3600
    
    max_hours_per_day = 14.0
    hours = min(hours, max_hours_per_day)
    
    min_hours_per_operation = 0.5
    if len(all_local_timestamps) > 0 and hours < min_hours_per_operation:
        hours = min_hours_per_operation
    
    return round(max(0, hours), 2)

def has_relevant_logs(logs, route_date):
    """Проверяет, есть ли релевантные логи для даты маршрута"""
    if not logs or not route_date:
        return False
    
    # Используем ту же логику фильтрации
    filtered_logs = filter_logs_by_work_time(logs, route_date)
    if len(filtered_logs) > 0:
        return True
    
    # Если нет отфильтрованных логов, проверяем любые логи за этот день по местному времени
    for log in logs:
        if log.timestamp:
            local_time = convert_to_local_time(log.timestamp)
            if local_time.date() == route_date:
                return True
    
    return False

@app.get("/companies-drivers-stats", summary="Статистика по компаниям и водителям за период")
async def get_companies_drivers_stats(
    start_date: date = Query(..., description="Начало периода"),
    end_date: date = Query(..., description="Конец периода"),
    db: AsyncSession = Depends(get_session)
):
    # Корректируем даты
    start_date, end_date = validate_and_adjust_dates(start_date, end_date)
    
    # Структура для хранения данных
    companies_dict = {}

    # 1️⃣ Получаем RoutePlan за период и сразу загружаем все связанные данные
    route_plans_result = await db.execute(
        select(RoutePlan)
        .where(RoutePlan.date >= start_date)
        .where(RoutePlan.date <= end_date)
        .options(
            selectinload(RoutePlan.vehicle)
            .selectinload(Vehicle.owner)
            .selectinload(User.transport_company)
            .selectinload(TransportCompany.legal_entity_type),
            selectinload(RoutePlan.points)
            .selectinload(RoutePoint.status_logs),
            selectinload(RoutePlan.loadings)
            .selectinload(Loading.status_logs)
        )
    )
    route_plans = route_plans_result.scalars().all()

    # 2️⃣ Обрабатываем все точки маршрутов из полученных планов
    for plan in route_plans:
        if not plan.vehicle or not plan.vehicle.owner:
            continue
            
        driver = plan.vehicle.owner
        company = driver.transport_company
        
        if not company:
            continue

        # Рассчитываем часы работы для маршрута (с фильтрацией ночных логов)
        work_hours = calculate_route_work_hours(plan)
        
        # Считаем суммы платежей по типам операций
        realizations_payment = 0.0
        transfers_payment = 0.0
        
        # Дата маршрута для дневной статистики
        route_date = plan.date.date() if plan.date else None

        # Безопасно получаем название типа юридического лица
        legal_entity_type_name = None
        if company.legal_entity_type:
            legal_entity_type_name = company.legal_entity_type.name

        # Обрабатываем точки маршрута
        for point in plan.points:
            # Определяем тип операции по документу
            doc_lower = (point.doc or "").lower()
            operation_type = None
            if "реализа" in doc_lower:
                operation_type = "realizations"
                # Суммируем платежи по реализациям
                if point.payment:
                    realizations_payment += point.payment
            elif "перемещ" in doc_lower:
                operation_type = "transfers"
                # Суммируем платежи по перемещениям
                if point.payment:
                    transfers_payment += point.payment

            if not operation_type:
                continue

            # ФИЛЬТРАЦИЯ ЛОГОВ ПО ДАТЕ МАРШРУТА И ВРЕМЕНИ СУТОК
            has_relevant_status_logs = has_relevant_logs(point.status_logs, route_date)

            # Если нет релевантных логов, пропускаем точку
            if not has_relevant_status_logs:
                continue

            # Добавляем компанию в словарь
            if company.id not in companies_dict:
                companies_dict[company.id] = {
                    "company": {
                        "id": company.id,
                        "name": company.name,
                        "inn": company.inn,
                        "kpp": company.kpp,
                        "contacts": company.contacts,
                        "legal_entity_type": legal_entity_type_name
                    },
                    "drivers": {}
                }

            company_data = companies_dict[company.id]
            
            # Добавляем водителя в компанию
            if driver.id not in company_data["drivers"]:
                company_data["drivers"][driver.id] = {
                    "driver": {
                        "id": driver.id,
                        "first_name": driver.first_name,
                        "last_name": driver.last_name,
                        "middle_name": driver.middle_name,
                        "rate": driver.rate,
                        "username": driver.username
                    },
                    "stats": {
                        "realizations": 0,
                        "transfers": 0,
                        "loadings": 0,
                        "total_operations": 0,
                        "total_work_hours": 0.0,
                        "total_routes": 0,
                        "realizations_payment": 0.0,
                        "transfers_payment": 0.0,
                        "total_payment": 0.0
                    },
                    "daily_stats": defaultdict(lambda: {
                        "realizations": 0,
                        "transfers": 0,
                        "loadings": 0,
                        "total_operations": 0,
                        "work_hours": 0.0,
                        "routes": 0,
                        "realizations_payment": 0.0,
                        "transfers_payment": 0.0,
                        "total_payment": 0.0
                    })
                }

            driver_data = company_data["drivers"][driver.id]
            
            # Обновляем общую статистику водителя
            driver_data["stats"][operation_type] += 1
            driver_data["stats"]["total_operations"] += 1
            
            # Обновляем платежи в общей статистике
            if point.payment:
                if operation_type == "realizations":
                    driver_data["stats"]["realizations_payment"] += point.payment
                elif operation_type == "transfers":
                    driver_data["stats"]["transfers_payment"] += point.payment
                driver_data["stats"]["total_payment"] += point.payment
            
            # Обновляем дневную статистику водителя
            if route_date:
                driver_data["daily_stats"][route_date.isoformat()][operation_type] += 1
                driver_data["daily_stats"][route_date.isoformat()]["total_operations"] += 1
                
                # Обновляем платежи в дневной статистике
                if point.payment:
                    if operation_type == "realizations":
                        driver_data["daily_stats"][route_date.isoformat()]["realizations_payment"] += point.payment
                    elif operation_type == "transfers":
                        driver_data["daily_stats"][route_date.isoformat()]["transfers_payment"] += point.payment
                    driver_data["daily_stats"][route_date.isoformat()]["total_payment"] += point.payment

        # Обрабатываем погрузки
        for loading in plan.loadings:
            # ФИЛЬТРАЦИЯ ЛОГОВ ПОГРУЗОК ПО ДАТЕ МАРШРУТА И ВРЕМЕНИ СУТОК
            has_relevant_loading_logs = has_relevant_logs(loading.status_logs, route_date)

            # Если нет релевантных логов, пропускаем погрузку
            if not has_relevant_loading_logs:
                continue

            # Добавляем компанию в словарь (если еще не добавлена)
            if company.id not in companies_dict:
                companies_dict[company.id] = {
                    "company": {
                        "id": company.id,
                        "name": company.name,
                        "inn": company.inn,
                        "kpp": company.kpp,
                        "contacts": company.contacts,
                        "legal_entity_type": legal_entity_type_name
                    },
                    "drivers": {}
                }

            company_data = companies_dict[company.id]
            
            # Добавляем водителя в компанию (если еще не добавлен)
            if driver.id not in company_data["drivers"]:
                company_data["drivers"][driver.id] = {
                    "driver": {
                        "id": driver.id,
                        "first_name": driver.first_name,
                        "last_name": driver.last_name,
                        "middle_name": driver.middle_name,
                        "rate": driver.rate,
                        "username": driver.username
                    },
                    "stats": {
                        "realizations": 0,
                        "transfers": 0,
                        "loadings": 0,
                        "total_operations": 0,
                        "total_work_hours": 0.0,
                        "total_routes": 0,
                        "realizations_payment": 0.0,
                        "transfers_payment": 0.0,
                        "total_payment": 0.0
                    },
                    "daily_stats": defaultdict(lambda: {
                        "realizations": 0,
                        "transfers": 0,
                        "loadings": 0,
                        "total_operations": 0,
                        "work_hours": 0.0,
                        "routes": 0,
                        "realizations_payment": 0.0,
                        "transfers_payment": 0.0,
                        "total_payment": 0.0
                    })
                }

            driver_data = company_data["drivers"][driver.id]
            
            # Обновляем статистику водителя для погрузок
            driver_data["stats"]["loadings"] += 1
            driver_data["stats"]["total_operations"] += 1
            
            # Обновляем дневную статистику водителя для погрузок
            if route_date:
                driver_data["daily_stats"][route_date.isoformat()]["loadings"] += 1
                driver_data["daily_stats"][route_date.isoformat()]["total_operations"] += 1

        # Обновляем статистику по маршрутам и часам работы
        # Проверяем, есть ли у маршрута какие-либо активности за день
        #if driver.id in company_data["drivers"]:
        #    driver_data = company_data["drivers"][driver.id]
        #    driver_data["stats"]["total_work_hours"] += work_hours
        #    driver_data["stats"]["total_routes"] += 1
            
        #    if route_date:
        #        driver_data["daily_stats"][route_date.isoformat()]["work_hours"] += work_hours
        #        driver_data["daily_stats"][route_date.isoformat()]["routes"] += 1

        # Если компания не была добавлена — пропускаем маршрут
        if company.id not in companies_dict:
            continue

        company_data = companies_dict[company.id]

# Если водитель не был добавлен — пропускаем маршрут
        if driver.id not in company_data["drivers"]:
            continue

        driver_data = company_data["drivers"][driver.id]

        driver_data["stats"]["total_work_hours"] += work_hours
        driver_data["stats"]["total_routes"] += 1

        if route_date:
            driver_data["daily_stats"][route_date.isoformat()]["work_hours"] += work_hours
            driver_data["daily_stats"][route_date.isoformat()]["routes"] += 1

    # 3️⃣ Преобразуем в нужный формат
    companies_list = []
    for company_data in companies_dict.values():
        drivers_list = []
        
        # Преобразуем словарь водителей в список
        for driver_id, driver_data in company_data["drivers"].items():
            # Преобразуем defaultdict в обычный dict для дневной статистики
            daily_stats_dict = dict(driver_data["daily_stats"])
            
            # Сортируем дневную статистику по дате
            sorted_daily_stats = {
                date_str: stats for date_str, stats in sorted(
                    daily_stats_dict.items(), 
                    key=lambda x: x[0]
                )
            }
            
            drivers_list.append({
                "driver": driver_data["driver"],
                "stats": driver_data["stats"],
                "daily_stats": sorted_daily_stats
            })
        
        # Сортируем водителей по количеству операций (по убыванию)
        drivers_list.sort(key=lambda x: x["stats"]["total_operations"], reverse=True)
        
        # Считаем общую статистику по компании
        company_stats = {
            "total_realizations": sum(d["stats"]["realizations"] for d in drivers_list),
            "total_transfers": sum(d["stats"]["transfers"] for d in drivers_list),
            "total_loadings": sum(d["stats"]["loadings"] for d in drivers_list),
            "total_operations": sum(d["stats"]["total_operations"] for d in drivers_list),
            "total_work_hours": round(sum(d["stats"]["total_work_hours"] for d in drivers_list), 2),
            "total_routes": sum(d["stats"]["total_routes"] for d in drivers_list),
            "total_drivers": len(drivers_list),
            "total_realizations_payment": round(sum(d["stats"]["realizations_payment"] for d in drivers_list), 2),
            "total_transfers_payment": round(sum(d["stats"]["transfers_payment"] for d in drivers_list), 2),
            "total_payment": round(sum(d["stats"]["total_payment"] for d in drivers_list), 2)
        }
        
        companies_list.append({
            "company": company_data["company"],
            "drivers": drivers_list,
            "company_stats": company_stats
        })

    # Сортируем компании по общему количеству операций (по убыванию)
    companies_list.sort(key=lambda x: x["company_stats"]["total_operations"], reverse=True)

    return {
        "period": {
            "start_date": start_date,
            "end_date": end_date
        },
        "summary": {
            "total_companies": len(companies_list),
            "total_drivers": sum(c["company_stats"]["total_drivers"] for c in companies_list),
            "total_realizations": sum(c["company_stats"]["total_realizations"] for c in companies_list),
            "total_transfers": sum(c["company_stats"]["total_transfers"] for c in companies_list),
            "total_loadings": sum(c["company_stats"]["total_loadings"] for c in companies_list),
            "total_operations": sum(c["company_stats"]["total_operations"] for c in companies_list),
            "total_work_hours": sum(c["company_stats"]["total_work_hours"] for c in companies_list),
            "total_routes": sum(c["company_stats"]["total_routes"] for c in companies_list),
            "total_realizations_payment": sum(c["company_stats"]["total_realizations_payment"] for c in companies_list),
            "total_transfers_payment": sum(c["company_stats"]["total_transfers_payment"] for c in companies_list),
            "total_payment": sum(c["company_stats"]["total_payment"] for c in companies_list)
        },
        "companies": companies_list
    }