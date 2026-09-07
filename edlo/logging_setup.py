import logging, structlog
import sys
from edlo.config import get_settings

def configure_logging() -> None: 
    settings = get_settings() 
    structlog.configure(
        processors=[
        structlog.contextvars.merge_contextvars, 
        structlog.stdlib.add_log_level, 
        structlog.processors.TimeStamper(fmt="iso"), 
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer() if settings.environment != "development" else structlog.dev.ConsoleRenderer(),
        ], 
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level) 
        ),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout), 
    )

log = structlog.get_logger()