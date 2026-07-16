"""
Application configuration.
Loaded from environment variables (.env file locally, real env vars in Azure).
"""
from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # --- App ---
    APP_NAME: str = "Property Management System"
    APP_ENV: str = "development"  # development | staging | production
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = True

    # --- Security ---
    SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION_USE_AZURE_KEY_VAULT"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 60

    # --- Database ---
    DATABASE_URL: str = "postgresql+psycopg2://pms_user:pms_password@localhost:5432/pms_db"

    # --- CORS ---
    # NOTE: kept as a plain string in .env (comma-separated), not a List[str],
    # because pydantic-settings attempts to JSON-parse env values for list-typed
    # fields *before* any validator runs, which crashes on a plain comma-separated
    # string. We parse it ourselves via the cors_origins property below.
    BACKEND_CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.BACKEND_CORS_ORIGINS.split(",") if origin.strip()]

    # --- File storage ---
    STORAGE_BACKEND: str = "local"  # local | azure_blob
    LOCAL_STORAGE_PATH: str = "./storage"
    MAX_UPLOAD_SIZE_MB: int = 25
    ALLOWED_UPLOAD_EXTENSIONS: List[str] = [
        ".pdf", ".png", ".jpg", ".jpeg", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt"
    ]

    # Azure Blob Storage (used when STORAGE_BACKEND=azure_blob)
    AZURE_STORAGE_CONNECTION_STRING: str = ""
    AZURE_STORAGE_CONTAINER: str = "pms-attachments"

    # --- Pagination ---
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    # --- Initial admin (seed) ---
    FIRST_ADMIN_EMAIL: str = "admin@pms-demo.com"
    FIRST_ADMIN_PASSWORD: str = "ChangeMe!123"

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
