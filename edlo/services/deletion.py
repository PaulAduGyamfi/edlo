"""
Deleting an episode removes everything it owns: audio and transcript rows,
jobs, its posting slot, its history. Rows go first, in one transaction; the
storage objects go afterwards, best effort, because an orphaned object is a
cost while a deleted object under a live row is a broken episode.
"""

from sqlalchemy.orm import Session

from edlo.models import (
    AudioFile,
    Episode,
    Job,
    PlanStep,
    PostingSlot,
    StageTransition,
    Transcript,
)


class CannotDelete(Exception): ...


def delete_episode(db: Session, ep: Episode) -> list[str]:
    """Delete the episode and its rows. Returns the storage keys now orphaned."""
    if ep.stage == "published":
        raise CannotDelete("published episodes are the record; they cannot be deleted")

    keys: list[str] = [
        a.storage_key for a in db.query(AudioFile).filter_by(episode_id=ep.id)
    ]
    for t in db.query(Transcript).filter_by(episode_id=ep.id):
        # Identical audio uploaded twice shares one transcript artifact
        # (the content-addressed cache). Only an unshared artifact is orphaned.
        shared = (
            db.query(Transcript)
            .filter(
                Transcript.storage_key == t.storage_key, Transcript.episode_id != ep.id
            )
            .count()
        )
        if not shared and t.storage_key not in keys:
            keys.append(t.storage_key)

    for model in (AudioFile, Transcript, Job, PostingSlot, StageTransition, PlanStep):
        db.query(model).filter_by(episode_id=ep.id).delete(synchronize_session=False)
    db.delete(ep)
    db.commit()
    return keys
