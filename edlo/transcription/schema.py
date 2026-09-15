from pydantic import BaseModel, Field, model_validator


class TranscriptSegment(BaseModel):
    index: int = Field(ge=0)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    text: str = Field(min_length=1)

    @model_validator(mode="after")
    def end_follows_start(self):
        if self.end_ms <= self.start_ms:
            raise ValueError(f"segment {self.index}: end_ms must be after start_ms")
        return self


class TranscriptArtifact(BaseModel):
    audio_checksum: str = Field(min_length=64, max_length=64)
    engine: str
    model_version: str
    language: str
    duration_ms: int = Field(gt=0)
    segments: list[TranscriptSegment]

    @model_validator(mode="after")
    def ordered_and_in_range(self):
        # Two DISTINCT checks with DISTINCT messages. Ordering and overlap are
        # different defects and a combined check produces a misleading error.
        for a, b in zip(self.segments, self.segments[1:], strict=False):
            if b.start_ms < a.start_ms:
                raise ValueError(
                    f"out of order: segment {b.index} starts before {a.index}"
                )
            if b.start_ms < a.end_ms:
                raise ValueError(
                    f"overlap: {a.index} ends at {a.end_ms}, {b.index} starts at {b.start_ms}"
                )
        if self.segments and self.segments[-1].end_ms > self.duration_ms:
            raise ValueError("last segment extends beyond the declared audio duration")
        return self

    def text_between(self, start_ms: int, end_ms: int) -> str:
        """Used by the grounding validator in Chapter 20."""
        return " ".join(
            s.text for s in self.segments if s.end_ms > start_ms and s.start_ms < end_ms
        )
