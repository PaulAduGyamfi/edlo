import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware

from edlo.logging import log


class TraceMiddleware(BaseHTTPMiddleware):
    """One trace ID per request, bound to every log line in that request."""

    async def dispatch(self, request, call_next):
        trace_id = request.headers.get("X-Trace-Id") or uuid.uuid4().hex
        request.state.trace_id = trace_id
        structlog.contextvars.bind_contextvars(trace_id=trace_id)
        started = time.perf_counter()

        try:
            response = await call_next(request)
            response.headers["X-Trace-Id"] = trace_id
            log.info(
                "http_request",
                method=request.method,
                path=request.url.path,
                status=response.status_code,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
            )
            return response
        finally:
            structlog.contextvars.clear_contextvars()
        return response
