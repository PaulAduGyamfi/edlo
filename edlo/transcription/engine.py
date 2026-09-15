from functools import lru_cache

from faster_whisper import WhisperModel

from edlo.transcription.schema import TranscriptArtifact, TranscriptSegment

ENGINE = "faster-whisper"
MODEL_VERSION = "small.en"


class AudioDecodeError(Exception): ...


class TranscriptTooShort(Exception): ...


@lru_cache(maxsize=1)
def _model() -> WhisperModel:
    # Loaded once per process. ~15 seconds cold. Remember that number --
    # it is one reason the worker in Chapter 15 is a long-running service.
    return WhisperModel(MODEL_VERSION, device="cpu", compute_type="int8")


def transcribe_file(path: str, audio_checksum: str) -> TranscriptArtifact:
    try:
        segments, info = _model().transcribe(path, vad_filter=True, language="en")
    except Exception as e:
        raise AudioDecodeError(f"could not decode audio: {type(e).__name__}") from e

    rows: list[TranscriptSegment] = []
    for seg in segments:  # a generator: streams, low memory
        text = seg.text.strip()
        if text:
            rows.append(
                TranscriptSegment(
                    index=len(rows),
                    start_ms=round(seg.start * 1000),
                    end_ms=round(seg.end * 1000),
                    text=text,
                )
            )
    if len(rows) < 3:
        raise TranscriptTooShort(f"only {len(rows)} segments produced")

    return TranscriptArtifact(
        audio_checksum=audio_checksum,
        engine=ENGINE,
        model_version=MODEL_VERSION,
        language=info.language,
        duration_ms=round(info.duration * 1000),
        segments=rows,
    )
