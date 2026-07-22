from fastapi import FastAPI

from app.routers import jd, jobs

app = FastAPI(title="Resume Agent")
app.include_router(jobs.router)
app.include_router(jd.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
