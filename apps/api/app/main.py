import uuid
import structlog
from fastapi import FastAPI, Request
from edlo.config import get_settings
from edlo.logging_setup import configure_logging

settings = get_settings()

configure_logging(settings.environment)
app = FastAPI(title="Edlo API", version="0.1.0")

log = structlog.get_logger()

@app.middleware("http")
async def add_run_id(request: Request, call_next):
    run_id = str(uuid.uuid4())
    request.state.run_id = run_id
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(run_id=run_id)
    response = await call_next(request)
    response.headers["X-Run-Id"] = run_id
    return response

@app.get("/health")
def health() -> dict[str, str]:
    log.info("health check called")
    return {"status" : "ok", "environment": settings.environment}