from datetime import date

import pytest

from apps.api.app.main import app
from edlo.models import Episode
from edlo.services.workflow import (
    IllegalTransition,
    NotPermitted,
    WorkflowService,
)


def make_episode(db, stage="registered"):
    ep = Episode(title="Test", recorded_on=date(2026, 3, 1), stage=stage)
    db.add(ep)
    db.flush()
    return ep


def test_cannot_skip_the_workflow(db, paul):
    ep = make_episode(db, stage="registered")
    with pytest.raises(IllegalTransition):
        WorkflowService(db).transition(ep, "published", paul)


def test_only_the_owner_publishes(db, chris):
    ep = make_episode(db, stage="review")
    with pytest.raises(NotPermitted):
        WorkflowService(db).transition(ep, "published", chris)


def test_published_is_terminal(db, paul):
    ep = make_episode(db, stage="published")
    with pytest.raises(IllegalTransition):
        WorkflowService(db).transition(ep, "editing", paul)


def test_every_transition_is_recorded(db, albert):
    ep = make_episode(db, stage="registered")
    WorkflowService(db).transition(ep, "mixing", albert, reason="mix uploaded")

    h = WorkflowService(db).history(ep.id)
    assert len(h) == 1
    assert h[0].actor_id == albert.id
    assert h[0].actor_role == "audio_editor"


def test_no_route_is_unauthenticated(client):
    """Meta-test: a new route cannot ship without an actor dependency."""
    public = (
        "/health",
        "/version",
        "/docs",
        "/openapi.json",
        "/redoc",
        "/docs/oauth2-redirect",
    )
    for route in app.routes:
        dependant = getattr(route, "dependant", None)
        path = getattr(route, "path", None)
        if dependant is None or path is None or path in public:
            continue

        deps = str(dependant)
        assert "actor" in deps or "current_actor" in deps, f"{path} unprotected"
