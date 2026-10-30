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

    @property
    def DEBUG(self) -> bool:
        """Derived from APP_ENV rather than an independently-settable flag,
        so a stray/misconfigured env var can't leave debug mode on in a
        staging/production deployment while APP_ENV correctly says so.
        Controls FastAPI's traceback verbosity and whether interactive API
        docs (/docs, /redoc, /openapi.json) are exposed at all — see
        app/main.py. Previously this was a plain field defaulting to
        `True` and was never actually read anywhere (dead config)."""
        return self.APP_ENV == "development"

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

    # The frontend's public URL, used to build the QR verification link
    # printed on invoices (.../verify/{qr_token}) — deliberately a
    # separate setting from CORS origins above, since that list is about
    # API access control, not "what's the canonical URL for a human to
    # visit."
    PUBLIC_APP_URL: str = "http://localhost:5173"

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
    MAX_PAGE_SIZE: int = 200

    # --- Initial admin (seed) ---
    FIRST_ADMIN_EMAIL: str = "admin@pms-demo.com"
    FIRST_ADMIN_PASSWORD: str = "ChangeMe!123"

    class Config:
        env_file = ".env"
        case_sensitive = True
        # pydantic-settings defaults to extra="forbid" for BaseSettings
        # (unlike plain pydantic BaseModel, which defaults to "ignore") —
        # so any .env/environment variable that doesn't map to a
        # currently-declared field raises a hard ValidationError at
        # startup and crashes the whole app before it can even serve a
        # request. That's what happened here: DEBUG was turned from a
        # settable field into a computed property (see above) during the
        # production audit, and the existing .env file still declared
        # DEBUG=true. Explicitly ignoring unrecognized keys means a
        # stray or legacy env var — this one, or any future one — can
        # never take the app down at boot.
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
