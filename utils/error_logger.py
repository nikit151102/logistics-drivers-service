import traceback
import uuid
from typing import Optional
from fastapi import Request
from services.log_service import get_log_client
from schemas.log_schema import LogCreate, LogLevel, Environment
from config import settings

async def log_system_error(
    error: Exception,
    title: str,
    section: str = "system",
    request: Optional[Request] = None,
    user_id: Optional[str] = None,
    component_name: Optional[str] = None,
    additional_metadata: Optional[dict] = None
):
    """
    Логирует системную ошибку в сервис логирования
    """
    try:
        log_client = get_log_client()
        
        url = None
        method = None
        ip_address = None
        endpoint = None
        
        if request:
            url = str(request.url)
            method = request.method
            ip_address = request.client.host if request.client else None
            endpoint = request.url.path
        
        stack_trace = traceback.format_exc()
        
        # Создаем объект лога
        log_entry = LogCreate(
            service_id="user-service",  
            title=title,
            message=str(error),
            level=LogLevel.ERROR,
            section=section,
            url=url,
            user_id=user_id,
            ip_address=ip_address,
            environment=Environment(settings.ENVIRONMENT),
            app_version=settings.APP_VERSION,
            api_endpoint=endpoint,
            http_method=method,
            request_id=str(uuid.uuid4()),
            stack_trace=stack_trace,
            component_name=component_name,
            tags=["error", "system", section],
            metadata=additional_metadata or {},
            targets=[0]
        )
        
        await log_client.send_log(log_entry)
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Не удалось отправить лог ошибки: {e}")