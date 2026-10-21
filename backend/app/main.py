import logging
import os
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError

from app.database import check_database_connection, engine
from app import models  # noqa: F401
from app.ratelimit import RateLimitMiddleware
from app.routers import (
    admin,
    auth,
    dashboard,
    messages,
    providers,
    public_providers,
    requests,
    reviews,
    search,
    services,
    users,
)
from app.security import require_admin
from app.storage import UPLOAD_DIR

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"

app = FastAPI(
    title="SkillConnect",
    description="Location-based service marketplace (MVP)",
    version="0.1.0",
)

# Which websites may call this API from a browser. Set CORS_ORIGINS in .env as a
# comma separated list. The default only allows the local development URLs.
DEFAULT_ORIGINS = "http://127.0.0.1:8000,http://localhost:8000"
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", DEFAULT_ORIGINS).split(",")
    if origin.strip() and origin.strip() != "*"  # "*" together with logins is unsafe
]

# Added first = runs closer to the routes. CORS is added last so that even a
# "too many attempts" (429) answer carries the CORS headers.
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    return response


# ---- database / unexpected errors: friendly JSON, never a stack trace ----------
logger = logging.getLogger("skillconnect")


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    logger.warning("Integrity error on %s %s: %s", request.method, request.url.path, exc.orig)
    return JSONResponse(
        status_code=409,
        content={"detail": "This conflicts with existing data (for example, a duplicate). Please check and try again."},
    )


@app.exception_handler(OperationalError)
async def database_down_handler(request: Request, exc: OperationalError):
    logger.error("Database not reachable on %s %s: %s", request.method, request.url.path, exc.orig)
    return JSONResponse(
        status_code=503,
        content={"detail": "The database is not reachable right now. Please try again in a moment."},
    )


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(request: Request, exc: SQLAlchemyError):
    logger.exception("Database error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "A database error occurred. Nothing was saved. Please try again."},
    )


app.include_router(auth.router)
app.include_router(users.router)
app.include_router(providers.router)
app.include_router(public_providers.router)
app.include_router(services.router)
app.include_router(search.router)
app.include_router(requests.router)
app.include_router(messages.router)
app.include_router(reviews.router)
app.include_router(dashboard.router)
app.include_router(admin.router)


@app.get("/api/health")
def health():
    db_ok, db_message = check_database_connection()
    return {
        "status": "ok",
        "app": "SkillConnect",
        "database_connected": db_ok,
        "database_message": db_message,
    }


@app.get("/api/db/tables")
def list_tables(_admin=Depends(require_admin)):
    db_ok, db_message = check_database_connection()
    if not db_ok:
        return {"database_connected": False, "tables": [], "message": db_message}
    tables = inspect(engine).get_table_names()
    return {
        "database_connected": True,
        "table_count": len(tables),
        "tables": sorted(tables),
    }


# Uploaded profile photos. This mount must come BEFORE the "/" frontend mount.
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
