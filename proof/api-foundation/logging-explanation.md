# Edlo Structured Logging & Request Correlation

## Purpose

This documents the logging setup added to the API: structured logging via `structlog`, plus a per-request `run_id` generated in middleware and attached to both server logs and the response headers.

## Request Flow

1. A client sends an HTTP request to the FastAPI application.
2. The request first passes through custom middleware, which generates a unique `run_id`.
3. The middleware binds `run_id` into `structlog`'s context vars, so it's available to any logger for the remainder of the request, and adds `run_id` as a header on the outgoing response.
4. `configure_logging()`, called once at application startup, has already set up `structlog`'s processor pipeline: it merges bound context vars (including `run_id`), adds a UTC ISO-8601 timestamp, adds the log level, and renders the result — as JSON in non-development environments, or as readable console output when `environment == "development"`.
5. The matched endpoint runs. Any log call made during this request (`log.info(...)`, etc.) automatically includes `run_id`, `timestamp`, and `level`, without those needing to be passed in manually at each call site.
6. FastAPI returns the response to the client, with `run_id` present in the response headers.


## Why This Matters

Without this, log lines from concurrent requests had no way to be distinguished from one another. Binding `run_id` at the middleware level means every log line for a given request is automatically tagged and filterable, and a client can report a `run_id` from a response header that maps directly back to the exact server-side logs for that request — no timestamp-guessing or log-scraping required.