from fastapi.testclient import TestClient
from structlog.contextvars import merge_contextvars
from structlog.testing import capture_logs

from apps.api.app.main import app

client = TestClient(app)


def test_run_id_appears_in_logs_and_matches_header():
    with capture_logs(processors=[merge_contextvars]) as captured:
        response = client.get("/health")

    header_run_id = response.headers["X-Trace-Id"]

    assert response.status_code == 200
    assert len(captured) > 0
    assert all(entry.get("trace_id") == header_run_id for entry in captured)
