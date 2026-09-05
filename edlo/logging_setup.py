import logging, structlog

def configure_logging(environment: str) -> None:
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.add_log_level,
    ]
    if environment == "development":
        renderer = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    structlog.configure(processors=[*shared_processors, renderer])