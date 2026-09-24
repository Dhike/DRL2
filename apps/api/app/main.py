from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.market.registry import shutdown_providers
from app.scanner.background import start_scanner_loop, stop_scanner_loop
from app.routers import auth, market, scanner


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    start_scanner_loop()
    yield
    await stop_scanner_loop()
    await shutdown_providers()


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(market.router)
app.include_router(scanner.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "drl2-api",
        "environment": settings.environment,
    }
