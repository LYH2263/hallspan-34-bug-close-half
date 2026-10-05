from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.api.router import api_router
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.services.seed import seed_if_empty


def ensure_schema_columns() -> None:
    """对已存在的旧库幂等补列：candidates.is_key、seat_plans.session_status。"""
    insp = inspect(engine)
    with engine.begin() as conn:
        if insp.has_table("candidates"):
            cols = {c["name"] for c in insp.get_columns("candidates")}
            if "is_key" not in cols:
                conn.execute(text("ALTER TABLE candidates ADD COLUMN is_key BOOLEAN NOT NULL DEFAULT FALSE"))
        if insp.has_table("seat_plans"):
            cols = {c["name"] for c in insp.get_columns("seat_plans")}
            if "session_status" not in cols:
                conn.execute(text("ALTER TABLE seat_plans ADD COLUMN session_status VARCHAR(8) NOT NULL DEFAULT 'open'"))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_schema_columns()
    if settings.seed_on_empty:
        db = SessionLocal()
        try:
            seed_if_empty(db)
        finally:
            db.close()
    yield


app = FastAPI(title="HallSpan", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix="/api")
