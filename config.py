# config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    LOG_SERVICE_URL: str = "http://192.54.100.195:6410"
    LOG_SERVICE_API_KEY: str = "secret-dev-key"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "production"
    
    class Config:
        env_file = ".env"

settings = Settings()