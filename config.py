# config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    LOG_SERVICE_URL: str = "http://logging-service:8000"
    LOG_SERVICE_API_KEY: str = "secret-dev-key"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "production"
    
    class Config:
        env_file = ".env"

settings = Settings()