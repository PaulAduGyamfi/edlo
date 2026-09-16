from dataclasses import dataclass

from edlo.transcription.schema import TranscriptArtifact, TranscriptSegment


@dataclass(frozen=True)
class Window:
    index: int
    start_ms: int
    end_ms: int
    segments: list[TranscriptSegment]


def make_windows(
    t: TranscriptArtifact,
    *,
    window_ms: int = 5 * 60 * 1000,
    overlap_ms: int = 30 * 1000,
) -> list[Window]:
    """
    Overlap matters: a great twenty-second moment straddling a boundary would
    otherwise be truncated in both windows and proposed in neither. Thirty
    seconds is longer than any cold open we would accept, so nothing is lost.
    """
    windows: list[Window] = []
    start = 0
    while start < t.duration_ms:
        end = min(start + window_ms, t.duration_ms)
        segs = [s for s in t.segments if s.end_ms > start and s.start_ms < end]
        if segs:
            windows.append(Window(len(windows), start, end, segs))
        if end >= t.duration_ms:
            break
        start = end - overlap_ms
    return windows


def _stamp(ms: int) -> str:
    s, frac = divmod(ms, 1000)
    return f"{s // 60}:{s % 60:02d}.{frac:03d}"


def render(window: Window) -> str:
    """One line per segment, timecoded, so the model can quote and cite exactly."""
    return "\n".join(
        f"[{_stamp(s.start_ms)}-{_stamp(s.end_ms)}] {s.text}" for s in window.segments
    )
