from datetime import datetime
from sqlalchemy import (
    Boolean, Column, Integer, String, ForeignKey, DateTime, Float, Enum, Table
)
from sqlalchemy.orm import relationship, declarative_base
import enum
import uuid
from sqlalchemy.dialects.postgresql import UUID
Base = declarative_base()

class TimestampMixin:
    createDateTime = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    changeDateTime = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

# ===================== Пользователь =====================
class User(Base, TimestampMixin):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True)
    username = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    middle_name = Column(String, nullable=True)
    rate = Column(Float, nullable=True)
    is_active = Column(Boolean, default=True)
    transport_company_id = Column(UUID(as_uuid=True), ForeignKey("transport_companies.id"), nullable=True)
    tariff_id = Column(UUID(as_uuid=True), ForeignKey("tariffs.id"), nullable=True)

    vehicles = relationship("Vehicle", back_populates="owner")
    transport_company = relationship("TransportCompany", back_populates="users")
    tariff = relationship("Tariff", back_populates="users")

    vehicles = relationship("Vehicle", back_populates="owner")

# ===================== Тип юридического лица =====================
class LegalEntityType(Base, TimestampMixin):
    __tablename__ = "legal_entity_types"

    id = Column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True)
    name = Column(String, nullable=False)

    companies = relationship("TransportCompany", back_populates="legal_entity_type")


# ===================== Транспортная компания =====================
class TransportCompany(Base, TimestampMixin):
    __tablename__ = "transport_companies"

    id = Column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True)
    name = Column(String, nullable=False)
    inn = Column(String, nullable=False)
    kpp = Column(String, nullable=True)
    contacts = Column(String, nullable=True)

    legal_entity_type_id = Column(UUID(as_uuid=True), ForeignKey("legal_entity_types.id"))

    legal_entity_type = relationship("LegalEntityType", back_populates="companies")
    users = relationship("User", back_populates="transport_company")


# ===================== Транспортное средство =====================
class Vehicle(Base, TimestampMixin):
    __tablename__ = "vehicles"

    id = Column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True)
    plate_number = Column(String, unique=True, index=True)
    model = Column(String)

    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    owner = relationship("User", back_populates="vehicles")

    logs = relationship("LogEntry", back_populates="vehicle")
    route_plans = relationship("RoutePlan", back_populates="vehicle")


# ===================== Статусы ТС =====================
class StatusEnum(str, enum.Enum):
    idle = "idle"
    loading = "loading"
    in_transit = "in_transit"
    delivered = "delivered"
    work_start = "work_start"
    work_end = "work_end"


# ===================== Логи транспортных средств =====================
class LogEntry(Base, TimestampMixin):
    __tablename__ = "logs"

    id = Column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True)
    vehicle_id = Column(UUID(as_uuid=True), ForeignKey("vehicles.id"))
    status = Column(Enum(StatusEnum), default=StatusEnum.idle)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    timestamp = Column(DateTime(timezone=True), default=datetime.utcnow)

    vehicle = relationship("Vehicle", back_populates="logs")


# ===================== Тип доставки =====================
class DeliveryType(Base, TimestampMixin):
    __tablename__ = "delivery_types"

    id = Column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True)
    name = Column(String, nullable=False)

    routes = relationship("RoutePlan", back_populates="delivery_type")


# ===================== Статусы маршрута =====================
class RouteStatusEnum(str, enum.Enum):
    planned = "planned"
    in_progress = "in_progress"
    completed = "completed"


# ===================== План маршрута =====================
class RoutePlan(Base, TimestampMixin):
    __tablename__ = "route_plans"

    id = Column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True)
    vehicle_id = Column(UUID(as_uuid=True), ForeignKey("vehicles.id"))
    date = Column(DateTime(timezone=True), default=datetime.utcnow)
    status = Column(Enum(RouteStatusEnum), default=RouteStatusEnum.planned)
    notes = Column(String, nullable=True)

    delivery_type_id = Column(UUID(as_uuid=True), ForeignKey("delivery_types.id"), nullable=True)
    
    start_datetime = Column(DateTime(timezone=True), nullable=True)
    end_datetime = Column(DateTime(timezone=True), nullable=True)

    vehicle = relationship("Vehicle", back_populates="route_plans")
    delivery_type = relationship("DeliveryType", back_populates="routes")
    points = relationship("RoutePoint", back_populates="route_plan", cascade="all, delete-orphan")
    loadings = relationship("Loading", back_populates="route_plan", cascade="all, delete-orphan")


# ===================== Статусы точки маршрута =====================
class RoutePointStatusEnum(str, enum.Enum):
    planned = "planned"
    en_route = "en_route"
    arrived = "arrived"
    completed = "completed"
    skipped = "skipped"
    loading = "loading"    
    loading_completed = "loading_completed"    


# ===================== Адрес =====================
class Address(Base, TimestampMixin):
    __tablename__ = "addresses"

    id = Column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True)
    address_1c = Column(String, nullable=False)
    country = Column(String, nullable=True)
    region = Column(String, nullable=True)
    area = Column(String, nullable=True)
    city = Column(String, nullable=True)
    street = Column(String, nullable=True)
    house = Column(String, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    stores = relationship("Store", back_populates="address")
    route_points = relationship("RoutePoint", back_populates="address")


# ===================== Магазин =====================
class Store(Base, TimestampMixin):
    __tablename__ = "stores"

    id = Column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True)
    uuid_1c = Column(String, nullable=False, unique=True)
    name_1c = Column(String, nullable=False)
    address_id = Column(UUID(as_uuid=True), ForeignKey("addresses.id"))

    address = relationship("Address", back_populates="stores")
    route_points = relationship("RoutePoint", back_populates="store")


# ===================== Точка маршрута =====================
class RoutePoint(Base, TimestampMixin):
    __tablename__ = "route_points"

    id = Column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True)
    route_plan_id = Column(UUID(as_uuid=True), ForeignKey("route_plans.id"))
    order = Column(Integer, nullable=False)
    doc = Column(String, nullable=True)
    payment = Column(Float, nullable=True)
    counterparty = Column(String, nullable=True)
    arrival_time = Column(DateTime(timezone=True), nullable=True)
    departure_time = Column(DateTime(timezone=True), nullable=True)
    duration_minutes = Column(Integer, nullable=True)
    note = Column(String, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    status = Column(Enum(RoutePointStatusEnum), default=RoutePointStatusEnum.planned)

    address_id = Column(UUID(as_uuid=True), ForeignKey("addresses.id"), nullable=True)
    store_id = Column(UUID(as_uuid=True), ForeignKey("stores.id"), nullable=True)

    route_plan = relationship("RoutePlan", back_populates="points")
    address = relationship("Address", back_populates="route_points")
    store = relationship("Store", back_populates="route_points")

    status_logs = relationship(
        "RoutePointStatusLog",
        back_populates="point",
        cascade="all, delete-orphan",
        order_by="RoutePointStatusLog.timestamp"
    )


# ===================== Лог статусов точки маршрута =====================
class RoutePointStatusLog(Base, TimestampMixin):
    __tablename__ = "route_point_status_logs"

    id = Column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True)
    point_id = Column(UUID(as_uuid=True), ForeignKey("route_points.id"), nullable=False)
    status = Column(Enum(RoutePointStatusEnum), nullable=False)
    timestamp = Column(DateTime(timezone=True), default=datetime.utcnow)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    note = Column(String, nullable=True)

    point = relationship("RoutePoint", back_populates="status_logs")


# ===================== Тарифы =====================
class Tariff(Base, TimestampMixin):
    __tablename__ = "tariffs"

    id = Column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True)
    vehicle_type = Column(String, nullable=False)
    city = Column(String, nullable=True)
    unit = Column(String, nullable=True)
    min_payment = Column(Float, nullable=True)
    min_volume = Column(Float, nullable=True)
    max_volume = Column(Float, nullable=True)
    body_type = Column(String, nullable=True)
    description = Column(String, nullable=True)

    users = relationship("User", back_populates="tariff")



# ===================== Места загрузки =====================
class LoadingPlace(Base, TimestampMixin):
    __tablename__ = "loading_places"

    id = Column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True)
    uuid_1c = Column(String, nullable=True, unique=True) 
    name = Column(String, nullable=False) 
    address_id = Column(UUID(as_uuid=True), ForeignKey("addresses.id"), nullable=False)

    contact_name = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    work_hours = Column(String, nullable=True)
    note = Column(String, nullable=True)

    address = relationship("Address")
    loadings = relationship("Loading", back_populates="loading_place")


class Loading(Base, TimestampMixin):
    __tablename__ = "loadings"

    id = Column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True)  # Уникальный идентификатор загрузки
    route_plan_id = Column(UUID(as_uuid=True), ForeignKey("route_plans.id"), nullable=False)  # Ссылка на маршрут (RoutePlan)
    loading_place_id = Column(UUID(as_uuid=True), ForeignKey("loading_places.id"), nullable=False)  # Ссылка на место загрузки (LoadingPlace)

    start_time = Column(DateTime(timezone=True), nullable=True)  # Время начала загрузки
    end_time = Column(DateTime(timezone=True), nullable=True)  # Время окончания загрузки
    doc_number = Column(String, nullable=True)  # Номер накладной или документа 1С
    volume = Column(Float, nullable=True)  # Объём груза
    weight = Column(Float, nullable=True)  # Вес груза
    note = Column(String, nullable=True)  # Примечание / комментарий

    latitude = Column(Float, nullable=True)  # Геолокация: широта
    longitude = Column(Float, nullable=True)  # Геолокация: долгота
    status = Column(Enum(RoutePointStatusEnum), default=RoutePointStatusEnum.planned)  # Текущий статус загрузки

    route_plan = relationship("RoutePlan", back_populates="loadings")
    loading_place = relationship("LoadingPlace", back_populates="loadings")

    status_logs = relationship(
        "LoadingStatusLog",
        back_populates="loading",
        cascade="all, delete-orphan",
        order_by="LoadingStatusLog.timestamp"
    )


# ===================== Лог статусов загрузки =====================
class LoadingStatusLog(Base, TimestampMixin):
    __tablename__ = "loading_status_logs"

    id = Column(Integer, primary_key=True, index=True)
    loading_id = Column(UUID(as_uuid=True), ForeignKey("loadings.id"), nullable=False)
    status = Column(Enum(RoutePointStatusEnum), nullable=False)
    timestamp = Column(DateTime(timezone=True), default=datetime.utcnow)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    note = Column(String, nullable=True)

    loading = relationship("Loading", back_populates="status_logs")
