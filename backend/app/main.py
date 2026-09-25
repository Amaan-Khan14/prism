"""PRism FastAPI application."""
from fastapi import FastAPI

from app.routers import analyses_router

app = FastAPI(title="PRism API", version="0.1.0")

app.include_router(analyses_router)


@app.get("/healthz", tags=["meta"])
async def healthz() -> dict[str, str]:
    return {"status": "ok"}
