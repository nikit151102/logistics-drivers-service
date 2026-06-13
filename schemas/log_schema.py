# schemas/log_schema.py
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from enum import Enum
from uuid import UUID

class LogLevel(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class Environment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"

class LogCreate(BaseModel):
    # Важно: добавляем model_config для корректной сериализации UUID
    model_config = ConfigDict(
        json_encoders={
            UUID: str  # Говорим Pydantic: "превращай UUID в строку при конвертации в JSON"
        },
        # Или более современный способ для Pydantic v2.10+:
        # serialize_as_any=True 
    )

    service_id: str | UUID  # Разрешаем и строку, и UUID
    title: str
    message: str
    level: LogLevel = LogLevel.ERROR
    section: Optional[str] = None
    url: Optional[str] = None
    previous_url: Optional[str] = None
    user_id: Optional[str | UUID] = None # Разрешаем и строку, и UUID
    session_id: Optional[str] = None
    ip_address: Optional[str] = None
    environment: Environment = Environment.PRODUCTION
    app_version: Optional[str] = None
    build_id: Optional[str] = None
    browser: Optional[str] = None
    os: Optional[str] = None
    device_type: Optional[str] = None
    screen_resolution: Optional[str] = None
    language: Optional[str] = None
    api_endpoint: Optional[str] = None
    http_method: Optional[str] = None
    status_code: Optional[int] = None
    request_id: Optional[str | UUID] = None
    is_online: Optional[bool] = True
    stack_trace: Optional[str] = None
    component_name: Optional[str] = None
    tags: Optional[List[str]] = []
    metadata: Optional[Dict[str, Any]] = {}
    group_id: Optional[str | UUID] = None
    targets: Optional[List[int]] = []
    topic_id: Optional[int] = None

    def dict(self, *args, **kwargs):
        # Переопределяем dict, чтобы UUID точно стали строками перед отправкой
        kwargs.setdefault('exclude_none', True)
        data = super().dict(*args, **kwargs)
        
        # Рекурсивная функция для поиска UUID в словаре
        def convert_uuids(obj):
            if isinstance(obj, UUID):
                return str(obj)
            elif isinstance(obj, dict):
                return {k: convert_uuids(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_uuids(i) for i in obj]
            return obj
            
        return convert_uuids(data)