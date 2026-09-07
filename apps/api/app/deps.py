from typing import Annotated
from fastapi import Depends, Header, HTTPException, status 
from sqlalchemy.orm import Session
from edlo.db import get_session
from edlo.config import get_settings
from edlo.domain.roles import Actor, Role
from edlo.auth.oidc import actor_from_jwt

SessionDep = Annotated[Session, Depends(get_session)]

_PILOT_TOKENS = {
"albert-token": Actor(id="u_albert", name="Albert", role=Role.AUDIO_EDITOR), "chris-token": Actor(id="u_chris", name="Chris", role=Role.VIDEO_EDITOR), "paul-token": Actor(id="u_paul", name="Paul", role=Role.OWNER),
}

def current_actor(authorization: Annotated[str | None, Header()] = None) -> Actor:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token") 
    token = authorization.split(" ", 1)[1].strip()
    settings = get_settings()
    if settings.auth_mode == "pilot_token":
        actor = _PILOT_TOKENS.get(token) 
        if actor is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token") 
        return actor
    return actor_from_jwt(token)

ActorDep = Annotated[Actor, Depends(current_actor)]
def require_role(*allowed: Role):
    """Route-level role gate. Coarse-grained; resource-level checks live in services.""" 
    def _guard(actor: ActorDep) -> Actor:
        if actor.role not in allowed: 
            raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"role {actor.role.value} may not perform this action", )
        return actor 
    return _guard