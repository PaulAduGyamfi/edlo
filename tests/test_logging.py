from structlog.testing import capture_logs
from structlog.contextvars import merge_contextvars
from fastapi.testclient import TestClient
from apps.api.app.main import app


client = TestClient(app)

def test_run_id_appears_in_logs_and_matches_header():
    with capture_logs(processors=[merge_contextvars]) as captured:
        response = client.get("/health")

    header_run_id = response.headers["X-Run-Id"]

    assert response.status_code == 200
    assert len(captured) > 0
    assert all(entry.get("run_id") == header_run_id for entry in captured)