"""What the model is asked to return. Schema conformance is not correctness:
every candidate still goes through grounding.py before it can reach a person."""

from pydantic import BaseModel, Field


class Grounded(BaseModel):
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    exact_quote: str
    confidence: float = Field(ge=0, le=1)


class Candidate(Grounded):
    kind: str = "remove"
    reason: str


class CutProposal(BaseModel):
    candidates: list[Candidate] = []


class ColdOpenCandidate(Grounded):
    why: str


class ColdOpenProposal(BaseModel):
    candidates: list[ColdOpenCandidate] = []


class Chapter(BaseModel):
    start_ms: int = Field(ge=0)
    title: str


class PublishingPackDraft(BaseModel):
    title: str
    description: str
    chapters: list[Chapter] = []
    links: list[str] = []
    sponsors: list[str] = []
