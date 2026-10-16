from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from sqlalchemy import inspect

from app.database import check_database_connection, engine
from app import models  # noqa: F401
from app.routers import auth, messages, providers, requests, search, services, users
from app.security import require_admin
from app.storage import UPLOAD_DIR

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"

app = FastAPI(
    title="SkillConnect",
    description="Location-based service marketplace (MVP)",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(providers.router)
app.include_router(services.router)
app.include_router(search.router)
app.include_router(requests.router)
app.include_router(messages.router)


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
