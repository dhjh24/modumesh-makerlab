"""FastAPI application entry point."""

from __future__ import annotations

from fastapi import FastAPI

from app.routers import health

app = FastAPI(
    title="ModuMesh MakerLab API",
    version="0.1.0",
    description="Self-hosted 3D generator platform API",
)

app.include_router(health.router)


@app.get("/")
async def root() -> dict:
    return {"service": "modumesh-api", "version": "0.1.0", "status": "running"}
