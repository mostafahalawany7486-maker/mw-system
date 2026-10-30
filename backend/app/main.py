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
from app.core.i18n import get_locale_from_request, translate_error_detail, translate_validation_errors, translate
from app.core.rate_limit import limiter, RATE_LIMITING_AVAILABLE
from app.api.v1.api import api_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pms")

# Same defensive posture as app/core/rate_limit.py: SlowAPIMiddleware and
# RateLimitExceeded are separate imports from the same optional
# dependency, and an unguarded failure here would be just as capable of
# taking down the entire application as the one already guarded there.
if RATE_LIMITING_AVAILABLE:
    from slowapi.middleware import SlowAPIMiddleware
    from slowapi.errors import RateLimitExceeded
else:
    SlowAPIMiddleware = None
    RateLimitExceeded = None

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Cloud-native Property Management System API (Phase 1: Foundation)",
    debug=settings.DEBUG,
    # Interactive API docs reveal the full endpoint/schema surface, which
    # is useful in development but unnecessary attack-surface reconnaissance
    # to leave open in staging/production — gated behind the same DEBUG
    # flag (itself derived from APP_ENV, see config.py) rather than always
    # being publicly reachable regardless of environment.
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json" if settings.DEBUG else None,
    docs_url=f"{settings.API_V1_PREFIX}/docs" if settings.DEBUG else None,
    redoc_url=f"{settings.API_V1_PREFIX}/redoc" if settings.DEBUG else None,
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

# Rate limiting (see app/core/rate_limit.py) — applied per-endpoint via the
# @limiter.limit(...) decorator (see routers/auth.py), not globally, since
# most of this API's endpoints don't need it and a blanket limit would
# throttle legitimate bulk operations (e.g. paginated list scrolling).
app.state.limiter = limiter


async def rate_limit_exceeded_handler(request: Request, exc):
    lang = get_locale_from_request(request)
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": translate("errors.rate_limited", lang)},
        headers={"Content-Language": lang, "Retry-After": "60"},
    )


if RATE_LIMITING_AVAILABLE:
    app.add_middleware(SlowAPIMiddleware)
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    response.headers["X-Process-Time-Ms"] = str(round((time.time() - start) * 1000, 2))
    return response


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    lang = get_locale_from_request(request)
    detail = translate_error_detail(exc.detail, lang)
    return JSONResponse(status_code=exc.status_code, content={"detail": detail, "path": str(request.url.path)}, headers={"Content-Language": lang})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    lang = get_locale_from_request(request)
    localized_errors = translate_validation_errors(exc.errors(), lang)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": translate("errors.validation_failed", lang), "errors": localized_errors, "path": str(request.url.path)},
        headers={"Content-Language": lang},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s", request.url.path)
    lang = get_locale_from_request(request)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": translate("errors.unexpected", lang)},
        headers={"Content-Language": lang},
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
