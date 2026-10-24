"""Aplicación ASGI principal."""

import logging
from uuid import UUID, uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.v1 import auth, collection, consistency, datasets, models
from app.core.config import get_settings
from app.infrastructure.database import verify_hu01_schema, verify_hu03_schema, verify_hu04_schema

settings = get_settings()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def verify_schema_on_startup() -> None:
    verify_hu01_schema()
    verify_hu03_schema()
    verify_hu04_schema()


app = FastAPI(title=settings.app_name, version="0.1.0", on_startup=[verify_schema_on_startup])
app.state.limiter = auth.limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.middleware("http")
async def request_context(request: Request, call_next):
    supplied_id = request.headers.get("X-Request-ID", "")
    try:
        request_id = str(UUID(supplied_id))
    except (ValueError, AttributeError):
        request_id = str(uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(RequestValidationError)
async def invalid_request(_request: Request, exc: RequestValidationError) -> JSONResponse:
    issues = [
        {
            "field": ".".join(str(part) for part in issue.get("loc", ())),
            "reason": str(issue.get("type", "invalid")),
        }
        for issue in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={
            "detail": {
                "code": "validation_error",
                "message": "La solicitud contiene campos inválidos.",
                "issues": issues,
            }
        },
    )


@app.exception_handler(Exception)
async def unexpected_error(_request: Request, _exc: Exception) -> JSONResponse:
    logging.getLogger(__name__).error("Error inesperado no controlado; error_type=%s", type(_exc).__name__)
    return JSONResponse(
        status_code=500,
        content={"detail": {"code": "internal_error", "message": "Error interno del servidor."}},
    )


@app.get("/healthz", tags=["Operación"])
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(auth.router, prefix="/api/v1")
app.include_router(collection.router, prefix="/api/v1")
app.include_router(datasets.router, prefix="/api/v1")
app.include_router(models.router, prefix="/api/v1")
app.include_router(consistency.router, prefix="/api/v1")

# Envuelve toda la app para que las respuestas 500 también conserven los encabezados CORS.
app = CORSMiddleware(
    app=app,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)
