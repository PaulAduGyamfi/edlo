import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apps.api.app.deps import SessionDep  # noqa
from apps.api.app.main import app
from edlo.db import Base, get_session
from edlo.domain.roles import Actor, Role
from edlo.storage.local import LocalStorage


@pytest.fixture
def engine(tmp_path, monkeypatch):
    """
    A throwaway SQLite file. A file, not memory, so the API's request thread,
    the test, and a worker session all see the same database.
    """
    engine = create_engine(
        f"sqlite:///{tmp_path}/test.db", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    for module in ("edlo.db", "edlo.jobs.transcribe", "apps.worker.main"):
        monkeypatch.setattr(f"{module}.get_sessionmaker", lambda: factory)
    yield engine
    engine.dispose()


@pytest.fixture
def db(engine):
    with sessionmaker(engine, expire_on_commit=False)() as s:
        yield s


@pytest.fixture
def client(db):
    app.dependency_overrides[get_session] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def albert():
    return Actor(id="u_albert", name="Albert", role=Role.AUDIO_EDITOR)


@pytest.fixture
def chris():
    return Actor(id="u_chris", name="Chris", role=Role.VIDEO_EDITOR)


@pytest.fixture
def paul():
    return Actor(id="u_paul", name="Paul", role=Role.OWNER)


@pytest.fixture
def local_storage(tmp_path, monkeypatch):
    """Point every route and the worker at a throwaway storage root."""
    storage = LocalStorage(tmp_path / "uploads")
    for module in (
        "apps.api.app.routes.audio",
        "apps.api.app.routes.episodes",
        "apps.api.app.routes.dev_storage",
        "apps.api.app.routes.transcripts",
        "edlo.jobs.transcribe",
    ):
        monkeypatch.setattr(f"{module}.get_storage", lambda: storage)
    return storage


@pytest.fixture
def queue(monkeypatch):
    """An in-memory Redis queue that the API's enqueue and the worker share."""
    import fakeredis

    from edlo.queue.rq_queue import RQQueue

    q = RQQueue(
        "redis://unused", connection=fakeredis.FakeRedis(), visibility_timeout=30
    )
    monkeypatch.setattr("edlo.queue.get_queue", lambda: q)
    monkeypatch.setattr(
        "apps.api.app.routes.audio.enqueue",
        lambda kind, payload: q.enqueue(kind, payload),
    )
    return q


@pytest.fixture
def pg_db():
    """
    Postgres, for what SQLite cannot test: FOR UPDATE SKIP LOCKED. CI sets
    TEST_DATABASE_URL to its service; locally, point it at a scratch database.
    """
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not set; SKIP LOCKED needs Postgres")
    engine = create_engine(url)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as s:
        yield s
    Base.metadata.drop_all(engine)
    engine.dispose()
