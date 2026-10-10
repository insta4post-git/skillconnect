from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from sqlalchemy import inspect

from app.database import check_database_connection, engine
from app import models  # noqa: F401
from app.routers import auth
from app.security import get_current_user

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
def list_tables(_user=Depends(get_current_user)):
    db_ok, db_message = check_database_connection()
    if not db_ok:
        return {"database_connected": False, "tables": [], "message": db_message}
    tables = inspect(engine).get_table_names()
    return {
        "database_connected": True,
        "table_count": len(tables),
        "tables": sorted(tables),
    }


app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
