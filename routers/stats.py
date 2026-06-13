from fastapi import APIRouter, Query, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import desc, select, func, case
from datetime import date
from database.database_app import get_session
from models import (
    RoutePointStatusLog, User, Vehicle, RoutePlan, RoutePoint, RoutePointStatusEnum
)
from sqlalchemy.sql import over
from utils.error_logger import log_system_error

router = APIRouter(prefix="/statistics", tags=["Статистика"])

@router.get("/full", summary="Полная статистика за период")
async def full_statistics(
    start_date: date = Query(..., description="Начало периода"),
    end_date: date = Query(..., description="Конец периода"),
    db: AsyncSession = Depends(get_session)
):
    """
    points_summary – сводка по точкам маршрута:

    total_points — всего точек за период

    completed, en_route, arrived, planned, skipped — по каждому статусу

    in_progress — объединение en_route + arrived

    remaining — объединение planned + skipped

    status_counts — словарь со всеми статусами и их количеством

    longest_road – точка с самой долгой дорогой:

    point_id — ID точки 

    address — адрес точки

    travel_time_seconds — время в пути к точке

    longest_service – точка с самой долгой работой:

    point_id — ID точки

    address — адрес точки

    duration_minutes — время работы на точке

    avg_duration_minutes — среднее время работы на точке по всем маршрутам

    drivers_stats – статистика по водителям:

    driver_id — ID водителя

    name — ФИО

    total_points — количество точек, за которые водитель отвечает

    completed_points — количество завершённых точек

    completion_percentage — процент выполнения

    avg_duration_minutes — среднее время на точку для водителя

    vehicles_stats – статистика по транспортным средствам:

    vehicle_id — ID машины

    plate_number — номерной знак

    total_points — всего точек на этом транспортном средстве

    completed_points — завершённые точки

    completion_percentage — процент выполнения

    avg_duration_minutes — среднее время на точку для машины

    total_summary – общая сводка:

    total_points — общее количество точек

    completed_points — общее количество завершённых точек

    total_payment — общая сумма оплаты

    avg_duration_minutes — среднее время на точку за весь период
    """

    latest_status_subq = (
        select(
            RoutePointStatusLog.point_id,
            RoutePointStatusLog.status,
            func.row_number().over(
                partition_by=RoutePointStatusLog.point_id,
                order_by=RoutePointStatusLog.timestamp.desc()
            ).label("rn")
        )
        .join(RoutePoint)
        .join(RoutePlan)
        .where(RoutePlan.date >= start_date, RoutePlan.date <= end_date)
    ).subquery()

    # --- 1. Сводка по точкам ---
    points_res = await db.execute(
        select(
            latest_status_subq.c.status,
            func.count(latest_status_subq.c.point_id)
        )
        .where(latest_status_subq.c.rn == 1)
        .group_by(latest_status_subq.c.status)
    )
    points_stats = dict(points_res.all())

    points_summary = {
        "total_points": sum(points_stats.values()) if points_stats else 0,
        "completed": points_stats.get(RoutePointStatusEnum.completed, 0),
        "en_route": points_stats.get(RoutePointStatusEnum.en_route, 0),
        "arrived": points_stats.get(RoutePointStatusEnum.arrived, 0),
        "planned": points_stats.get(RoutePointStatusEnum.planned, 0),
        "skipped": points_stats.get(RoutePointStatusEnum.skipped, 0),
        "in_progress": points_stats.get(RoutePointStatusEnum.en_route, 0) + points_stats.get(RoutePointStatusEnum.arrived, 0),
        "remaining": points_stats.get(RoutePointStatusEnum.planned, 0) + points_stats.get(RoutePointStatusEnum.skipped, 0),
        "status_counts": points_stats
    }

    # --- 2. Самая долгая дорога ---
    longest_road_res = await db.execute(
        select(
            RoutePoint.id,
            RoutePoint.address,
            (func.extract("epoch", RoutePoint.arrival_time) - func.extract("epoch", RoutePoint.departure_time)).label("travel_time")
        )
        .join(RoutePoint.route_plan)
        .where(
            RoutePlan.date >= start_date,
            RoutePlan.date <= end_date,
            RoutePoint.arrival_time.isnot(None),
            RoutePoint.departure_time.isnot(None)
        )
        .order_by((func.extract("epoch", RoutePoint.arrival_time) - func.extract("epoch", RoutePoint.departure_time)).desc())
        .limit(1)
    )
    longest_road_row = longest_road_res.first()
    longest_road = {
        "point_id": longest_road_row.id,
        "address": longest_road_row.address,
        "travel_time_seconds": longest_road_row.travel_time
    } if longest_road_row else None

    # --- 3. Самая долгая работа на точке ---
    longest_service_res = await db.execute(
        select(
            RoutePoint.id,
            RoutePoint.address,
            RoutePoint.duration_minutes
        )
        .join(RoutePoint.route_plan)
        .where(
            RoutePlan.date >= start_date,
            RoutePlan.date <= end_date,
            RoutePoint.duration_minutes.isnot(None)
        )
        .order_by(RoutePoint.duration_minutes.desc())
        .limit(1)
    )
    longest_service_row = longest_service_res.first()
    longest_service = {
        "point_id": longest_service_row.id,
        "address": longest_service_row.address,
        "duration_minutes": longest_service_row.duration_minutes
    } if longest_service_row else None

    # --- 4. Среднее время на точку ---
    avg_duration_res = await db.execute(
        select(func.avg(RoutePoint.duration_minutes))
        .join(RoutePoint.route_plan)
        .where(RoutePlan.date >= start_date, RoutePlan.date <= end_date)
        .where(RoutePoint.duration_minutes.isnot(None))
    )
    avg_duration = avg_duration_res.scalar() or 0

    # --- 5. Статистика по водителям ---
    drivers_res = await db.execute(
        select(
            User.id,
            User.first_name,
            User.last_name,
            func.count(RoutePoint.id).label("total_points"),
            func.sum(
                case(
                    (latest_status_subq.c.status == RoutePointStatusEnum.completed, 1),
                    else_=0
                )
            ).label("completed_points"),
            func.avg(RoutePoint.duration_minutes).label("avg_duration_minutes")
        )
        .outerjoin(Vehicle, Vehicle.owner_id == User.id)
        .outerjoin(RoutePlan, RoutePlan.vehicle_id == Vehicle.id)
        .outerjoin(RoutePoint, RoutePoint.route_plan_id == RoutePlan.id)
        .outerjoin(latest_status_subq, latest_status_subq.c.point_id == RoutePoint.id)
        .where(
            ((RoutePlan.date >= start_date) & (RoutePlan.date <= end_date)) | (RoutePlan.id == None)
        )
        .where((latest_status_subq.c.rn == 1) | (latest_status_subq.c.rn == None))
        .group_by(User.id)
    )

    drivers_stats = [
        {
            "driver_id": r.id,
            "name": f"{r.first_name} {r.last_name}",
            "total_points": r.total_points,
            "completed_points": r.completed_points,
            "completion_percentage": (r.completed_points / r.total_points * 100) if r.total_points else 0,
            "avg_duration_minutes": r.avg_duration_minutes or 0
        }
        for r in drivers_res.all()
    ]

    # --- 6. Статистика по транспортным средствам ---
    vehicles_res = await db.execute(
        select(
            Vehicle.id,
            Vehicle.plate_number,
            func.count(RoutePoint.id).label("total_points"),
            func.sum(case((latest_status_subq.c.status == RoutePointStatusEnum.completed, 1), else_=0)).label("completed_points"),
            func.avg(RoutePoint.duration_minutes).label("avg_duration_minutes")
        )
        .outerjoin(RoutePlan, RoutePlan.vehicle_id == Vehicle.id)
        .outerjoin(RoutePoint, RoutePoint.route_plan_id == RoutePlan.id)
        .outerjoin(latest_status_subq, latest_status_subq.c.point_id == RoutePoint.id)
        .where(
            ((RoutePlan.date >= start_date) & (RoutePlan.date <= end_date)) | (RoutePlan.id == None)
        )
        .where((latest_status_subq.c.rn == 1) | (latest_status_subq.c.rn == None))
        .group_by(Vehicle.id)
    )

    vehicles_stats = [
        {
            "vehicle_id": r.id,
            "plate_number": r.plate_number,
            "total_points": r.total_points,
            "completed_points": r.completed_points,
            "completion_percentage": (r.completed_points / r.total_points * 100) if r.total_points else 0,
            "avg_duration_minutes": r.avg_duration_minutes or 0
        }
        for r in vehicles_res.all()
    ]

    # --- 7. Общая сводка ---
    summary_res = await db.execute(
        select(
            func.count(RoutePoint.id).label("total_points"),
            func.sum(case((latest_status_subq.c.status == RoutePointStatusEnum.completed, 1), else_=0)).label("completed_points"),
            func.sum(RoutePoint.payment).label("total_payment")
        )
        .join(RoutePoint.route_plan)
        .join(latest_status_subq, latest_status_subq.c.point_id == RoutePoint.id)
        .where(RoutePlan.date >= start_date, RoutePlan.date <= end_date)
        .where(latest_status_subq.c.rn == 1)
    )
    summary_row = summary_res.first()
    total_summary = {
        "total_points": summary_row.total_points or 0,
        "completed_points": summary_row.completed_points or 0,
        "total_payment": summary_row.total_payment or 0.0,
        "avg_duration_minutes": avg_duration
    }

    return {
        "points_summary": points_summary,
        "longest_road": longest_road,
        "longest_service": longest_service,
        "avg_duration_minutes": avg_duration,
        "drivers_stats": drivers_stats,
        "vehicles_stats": vehicles_stats,
        "total_summary": total_summary
    }
