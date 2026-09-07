# Edlo Database Layer

## Purpose

This proves that Edlo has a real, persistent data layer: Python model definitions turned into actual database tables, connected through a cached engine and session factory, with schema changes tracked as versioned migrations rather than ad-hoc edits.

## Flow

1. Model classes in `edlo/models.py` (`Episode`, `AudioFile`, `PlanStep`, `StageTransition`) inherit from the shared `Base` in `edlo/db.py` — this is Python's representation of each table's shape.
2. `Base.metadata` collects every model's table definition once those classes are imported. It carries an explicit naming convention so indexes, unique constraints, checks, foreign keys and primary keys get predictable, generated names instead of database-assigned ones.
3. Alembic compares `Base.metadata` against the live database and generates a migration script — the versioned, reviewable record of the actual schema change.
4. `alembic upgrade head` executes that script, turning the model definitions into real tables in the database.
5. At runtime, `get_engine()` builds the engine from `Settings.database_url`, branching on dialect: SQLite gets `check_same_thread=False`, other databases get real pool sizing and recycling. `get_sessionmaker()` wraps it in a session factory. Both are `lru_cache`'d, so the app shares one engine and one connection pool for its lifetime.
6. Calling the session factory opens a session — the unit of work through which Edlo stores and queries episodes, their audio files, ordered plan steps, and stage transition history.

## Test

`test_rollback_does_not_persist` verifies that a session's `add()` is only staged in memory — nothing is durable until `commit()`. It adds an `Episode`, calls `rollback()` instead, then opens a **second, independent** session and confirms the episode is genuinely absent from the database, not just uncommitted in the first session's memory.

The test runs against a temp database built by a fixture rather than the development database, so it depends on neither the working directory nor whatever data happens to sit in `edlo.db`.

## Why This Matters

Model classes are convenient for code, but `create_all()` (handy in tests, where the schema is disposable) can't safely evolve a schema already holding real data — only migrations can. This proves the full chain: model → migration → real table → pooled engine → session → verified rollback behavior. That's the foundation every future feature (uploads, transcription, AI cuts) will write through.