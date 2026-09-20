import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import init_db
from app.routers import answers, autofill, board, jd, jobs, profile
from app.services.board_sync import cleanup_postings, harvester_loop, retention_loop, scout_loop


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()  # create tables + seed the "default" profile on startup (T11)
    cleanup_postings()
    tasks = [asyncio.create_task(loop()) for loop in (harvester_loop, scout_loop, retention_loop)]
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


app = FastAPI(title="Resume Agent", lifespan=lifespan)
# The autofill extension (T12) and the Vite dev frontend call us cross-origin.
# Scope to chrome-extension:// (any unpacked id) + localhost — not "*".
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^(chrome-extension://[a-p]+|http://localhost:\d+)$",
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(jobs.router)
app.include_router(jd.router)
app.include_router(profile.router)
app.include_router(autofill.router)
app.include_router(answers.router)
app.include_router(board.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
