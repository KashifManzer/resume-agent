from fastapi import FastAPI

app = FastAPI(title="Resume Agent")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
