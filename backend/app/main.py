"""
Application entrypoint. Wires middleware, static file serving for local
attachment storage, global exception handling, and the versioned API router.
"""
import time
import logging
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.api.v1.api import api_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pms")

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Cloud-native Property Management System API (Phase 1: Foundation)",
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    docs_url=f"{settings.API_V1_PREFIX}/docs",
    redoc_url=f"{settings.API_V1_PREFIX}/redoc",
)

# CORS: required for the React SPA (served from a different origin/port) to
# call this API. Origins are environment-driven so production locks down to
# the real frontend domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    response.headers["X-Process-Time-Ms"] = str(round((time.time() - start) * 1000, 2))
    return response


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail, "path": str(request.url.path)})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Validation error", "errors": exc.errors(), "path": str(request.url.path)},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s", request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected error occurred. Please try again or contact support."},
    )


@app.get("/health", tags=["Health"])
def health_check():
    """Used by Azure App Service / load balancer health probes."""
    return {"status": "healthy", "app": settings.APP_NAME, "env": settings.APP_ENV}


app.include_router(api_router, prefix=settings.API_V1_PREFIX)

# Serve locally-stored uploads (dev/local storage backend only; in Azure
# production this is replaced by Azure Blob Storage with CDN in front).
if settings.STORAGE_BACKEND == "local":
    import os
    os.makedirs(settings.LOCAL_STORAGE_PATH, exist_ok=True)
    app.mount("/files", StaticFiles(directory=settings.LOCAL_STORAGE_PATH), name="files")
