from dataclasses import dataclass
from enum import Enum


class Role(str, Enum):
    AUDIO_EDITOR = "audio_editor"
    VIDEO_EDITOR = "video_editor"
    OWNER = "owner"


@dataclass(frozen=True)
class Actor:
    id: str
    name: str
    role: Role
    tenant_id: str = "sozzled"
