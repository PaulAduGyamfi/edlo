# Edlo Database Layer

## Purpose

This proves that Edlo has a real, persistent data layer: Python model definitions turned into actual database tables, connected through a shared engine and session factory, with schema changes tracked as versioned migrations rather than ad-hoc edits.

## Flow

1. Model classes in `edlo/models.py` (`Episode`, `AudioFile`, `PlanStep`, `StageTransition`) inherit from the shared `Base` in `edlo/db.py` — this is Python's representation of each table's shape.
2. `Base.metadata` collects every model's table definition once those classes are imported.
3. Alembic compares `Base.metadata` against the live database and generates a migration script — the versioned, reviewable record of the actual schema change.
4. `alembic upgrade head` executes that script, turning the model definitions into real tables in the database.
5. At runtime, the shared `engine` (built from `Settings.database_url`) and `SessionLocal` factory in `edlo/db.py` give the app a consistent way to open a database connection and a session per unit of work.
6. Through this session, Edlo can now store and query episodes, their audio files, ordered plan steps, and stage transition history.

## Test

`test_rollback_does_not_persist` verifies that a session's `add()` is only staged in memory — nothing is durable until `commit()`. It adds an `Episode`, calls `rollback()` instead, then opens a **second, independent** session and confirms the episode is genuinely absent from the database, not just uncommitted in the first session's memory.

## Why This Matters

Model classes are convenient for code, but `create_all()` (handy in tests) can't safely evolve a schema already holding real data — only migrations can. This session proves the full chain works end-to-end: model → migration → real table → connected session → verified rollback behavior. That's the foundation every future feature (uploads, transcription, AI cuts) will write through.