import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from apps.api.app.middleware import TraceMiddleware
from apps.api.app.routes import episodes
from edlo.config import get_settings
from edlo.logging import configure_logging, log

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    log.info("service_started", environment=settings.environment, version=app.version)
    yield
    log.info("service_stopping")


app = FastAPI(title="Edlo API", version="0.1.0", lifespan=lifespan)
app.include_router(episodes.router)
app.add_middleware(TraceMiddleware)


@app.get("/health")
def health() -> dict[str, str]:
    log.info("health check called")
    return {"status": "ok", "environment": settings.environment}


@app.get("/version")
def version() -> dict[str, str]:
    return {
        "version": app.version,
        "environment": settings.environment,
        "commit": os.getenv("GIT_SHA", "unknown"),
    }
