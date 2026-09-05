# Edlo Health Request Path

## Purpose

This request proves that the Edlo frontend or another HTTP client can communicate with the FastAPI backend.

## Request Flow

1. A client sends an HTTP GET request to `/health`.
2. Uvicorn receives the request and passes it to the FastAPI application in `apps/api/app/main.py`.
3. FastAPI matches the request to the function decorated with `@app.get("/health")`.
4. The `health()` function runs and returns `{"status": "ok"}`.
5. FastAPI serializes the Python dictionary into JSON.
6. FastAPI returns the JSON response with HTTP status code 200.
7. The client receives the response and can confirm that the API is running.

## Automated Test

The test in `tests/test_main.py` uses FastAPI's `TestClient` to simulate the HTTP request without starting a separate browser.

The test verifies:

- The `/health` endpoint is reachable.
- The response status code is 200.
- The response body equals `{"status": "ok"}`.

## Why This Matters

This is the first proven request path in Edlo. It confirms that the application can receive an HTTP request, execute backend code and return a predictable response.