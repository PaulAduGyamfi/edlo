"""
Start fresh: every episode and everything it owns, gone from the DEV
database, the local upload directory and the dev queue.

    python -m scripts.reset_dev

Refuses a non-SQLite database unless EDLO_RESET_CONFIRM=yes is set.
"""

import os
import shutil
import sys

from sqlalchemy import text

from edlo.config import get_settings
from edlo.db import Base, get_engine


def main() -> int:
    s = get_settings()
    if (
        not s.database_url.startswith("sqlite")
        and os.environ.get("EDLO_RESET_CONFIRM") != "yes"
    ):
        print(
            f"refusing to wipe {s.database_url.split('@')[-1]}; set EDLO_RESET_CONFIRM=yes"
        )
        return 2

    engine = get_engine()
    import edlo.models  # noqa: F401 - register every table on Base

    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            n = conn.execute(text(f"SELECT count(*) FROM {table.name}")).scalar()
            conn.execute(table.delete())
            print(f"  {table.name:<22} {n} rows removed")

    root = s.upload_dir / "episodes"
    if root.exists():
        shutil.rmtree(root)
        print(f"  {root} removed")

    try:
        from redis import Redis

        r = Redis.from_url(s.redis_url, socket_timeout=2)
        gone = r.delete("edlo:ready", "edlo:inflight", "edlo:dead")
        print(f"  queue: {gone} redis keys removed")
    except Exception as e:  # noqa: BLE001 - no Redis is fine for a reset
        print(f"  queue: skipped ({type(e).__name__})")
    print("fresh.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
