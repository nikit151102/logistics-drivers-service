from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List
from models import RoutePointStatusEnum, StatusEnum
from uuid import UUID

class UserCreate(BaseModel):
    username: str
    first_name: str
    last_name: str
    middle_name: str
    rate: float
    password: str
    transport_company_id: Optional[UUID] = None
    tariff_id: Optional[UUID] = None

class UserUpdate(BaseModel):
    id: UUID
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    middle_name: Optional[str] = None
    rate: Optional[float] = None
    is_active: Optional[bool] = None  
    transport_company_id: Optional[UUID] = None
    tariff_id: Optional[UUID] = None

    class Config:
        orm_mode = True

class UserOut(BaseModel):
    id: UUID
    username: str
    first_name: str
    last_name: str
    middle_name: str
    rate: float
    transport_company_id: Optional[UUID] = None
    tariff_id: Optional[UUID] = None
    createDateTime: datetime
    changeDateTime: datetime

    class Config:
        orm_mode = True



class VehicleCreate(BaseModel):
    plate_number: str
    model: str


class VehicleOut(BaseModel):
    id: UUID
    plate_number: str
    model: str
    createDateTime: datetime
    changeDateTime: datetime

    class Config:
        orm_mode = True


class LogCreate(BaseModel):
    status: StatusEnum
    latitude: Optional[float]
    longitude: Optional[float]


class LogOut(BaseModel):
    id: UUID
    status: StatusEnum
    latitude: Optional[float]
    longitude: Optional[float]
    timestamp: datetime
    createDateTime: datetime
    changeDateTime: datetime
    
    class Config:
        orm_mode = True



class RouteDateUpdate(BaseModel):
    start_datetime: datetime | None = None
    end_datetime: datetime | None = None
    
class PointStatusUpdate(BaseModel):
    new_status: RoutePointStatusEnum
    lat: Optional[float] = None
    lng: Optional[float] = None
    timestamp: Optional[datetime] = None



from pydantic import BaseModel, Field
from typing import Optional, List


# ===================== Адрес =====================
class AddressBase(BaseModel):
    address_1c: str
    country: Optional[str] = None
    region: Optional[str] = None
    area: Optional[str] = None
    city: Optional[str] = None
    street: Optional[str] = None
    house: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class AddressCreate(AddressBase):
    pass


class AddressOut(AddressBase):
    id: UUID
    createDateTime: datetime
    changeDateTime: datetime
    
    class Config:
        orm_mode = True


# ===================== Магазин =====================
class StoreBase(BaseModel):
    uuid_1c: str
    name_1c: str
    address_id: Optional[UUID] = None


class StoreCreate(StoreBase):
    pass


class StoreOut(StoreBase):
    id: UUID
    address: Optional[AddressOut] = None
    createDateTime: datetime
    changeDateTime: datetime
    
    class Config:
        orm_mode = True


# ===================== Тип доставки =====================
class DeliveryTypeBase(BaseModel):
    name: str


class DeliveryTypeCreate(DeliveryTypeBase):
    pass


class DeliveryTypeOut(DeliveryTypeBase):
    id: UUID
    createDateTime: datetime
    changeDateTime: datetime
    
    class Config:
        orm_mode = True


# ===================== Тип юр. лица =====================
class LegalEntityTypeBase(BaseModel):
    name: str


class LegalEntityTypeCreate(LegalEntityTypeBase):
    pass


class LegalEntityTypeOut(LegalEntityTypeBase):
    id: UUID
    createDateTime: datetime
    changeDateTime: datetime
    
    class Config:
        orm_mode = True


# ===================== Транспортная компания =====================
class TransportCompanyBase(BaseModel):
    name: str
    inn: str
    kpp: Optional[str] = None
    contacts: Optional[str] = None
    legal_entity_type_id: Optional[UUID] = None


class TransportCompanyCreate(TransportCompanyBase):
    pass


class TransportCompanyOut(TransportCompanyBase):
    id: UUID
    legal_entity_type: Optional[LegalEntityTypeOut] = None
    createDateTime: datetime
    changeDateTime: datetime
    
    class Config:
        orm_mode = True


# ===================== Тариф =====================
class TariffBase(BaseModel):
    vehicle_type: str
    city: Optional[str] = None
    unit: Optional[str] = None
    min_payment: Optional[float] = None
    min_volume: Optional[float] = None
    max_volume: Optional[float] = None
    body_type: Optional[str] = None
    description: Optional[str] = None


class TariffCreate(TariffBase):
    pass


class TariffOut(TariffBase):
    id: UUID
    createDateTime: datetime
    changeDateTime: datetime
    
    class Config:
        orm_mode = True
