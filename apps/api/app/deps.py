from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from edlo.db import get_session
from edlo.domain.roles import Actor, Role

SessionDep = Annotated[Session, Depends(get_session)]

_PILOT_TOKENS = {
    "albert-token": Actor(id="u_albert", name="Albert", role=Role.AUDIO_EDITOR),
    "chris-token": Actor(id="u_chris", name="Chris", role=Role.VIDEO_EDITOR),
    "paul-token": Actor(id="u_paul", name="Paul", role=Role.OWNER),
}


def current_actor(authorization: Annotated[str | None, Header()] = None) -> Actor:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    actor = _PILOT_TOKENS.get(authorization.split(" ", 1)[1].strip())
    if actor is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token")
    return actor


ActorDep = Annotated[Actor, Depends(current_actor)]
