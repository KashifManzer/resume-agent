from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db import init_db
from app.routers import jd, jobs, profile


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()  # create tables + seed the "default" profile on startup (T11)
    yield


app = FastAPI(title="Resume Agent", lifespan=lifespan)
app.include_router(jobs.router)
app.include_router(jd.router)
app.include_router(profile.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
