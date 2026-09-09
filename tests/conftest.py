import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apps.api.app.deps import SessionDep  # noqa
from apps.api.app.main import app
from edlo.db import Base, get_session
from edlo.domain.roles import Actor, Role


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
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
