import httpx
import logging
from typing import Optional
from fastapi import Request
from schemas.log_schema import LogCreate, LogLevel, Environment

logger = logging.getLogger(__name__)

class LogServiceClient:
    def __init__(
        self, 
        log_service_url: str, 
        api_key: str,
        timeout: int = 5
    ):
        self.log_service_url = log_service_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)
    
    async def send_log(self, log_data: LogCreate) -> bool:
        """Отправляет лог в сервис логирования"""
        try:
            response = await self.client.post(
                f"{self.log_service_url}/api/v1/logs",
                json=log_data.dict(exclude_none=True),
                headers={
                    "X-API-Key": self.api_key,
                    "Content-Type": "application/json"
                }
            )
            
            if response.status_code == 200 or response.status_code == 201:
                logger.info(f"Лог успешно отправлен: {log_data.title}")
                return True
            else:
                logger.error(
                    f"Ошибка при отправке лога. Status: {response.status_code}, "
                    f"Response: {response.text}"
                )
                return False
                
        except httpx.TimeoutException:
            logger.error("Таймаут при отправке лога")
            return False
        except httpx.ConnectError:
            logger.error("Ошибка подключения к сервису логов")
            return False
        except Exception as e:
            logger.error(f"Неожиданная ошибка при отправке лога: {str(e)}")
            return False
    
    async def close(self):
        """Закрытие клиента"""
        await self.client.aclose()


log_client: Optional[LogServiceClient] = None

def get_log_client() -> LogServiceClient:
    global log_client
    if log_client is None:
        # Загружаем из настроек
        from config import settings
        print('settings', settings)
        log_client = LogServiceClient(
            log_service_url=settings.LOG_SERVICE_URL,
            api_key=settings.LOG_SERVICE_API_KEY
        )
    return log_client