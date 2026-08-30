"""Database engine + session helpers (SQLite via SQLModel)."""
from __future__ import annotations

from collections.abc import Iterator

from sqlmodel import Session, SQLModel, create_engine

from .config import get_settings

_settings = get_settings()

_connect_args = (
    {"check_same_thread": False}
    if _settings.database_url.startswith("sqlite")
    else {}
)

engine = create_engine(_settings.database_url, echo=False, connect_args=_connect_args)


def init_db() -> None:
    """Create tables. Import models first so they register on the metadata."""
    from . import models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    _lightweight_migrate()


# Columns added after the first release. SQLite can ADD COLUMN cheaply; this keeps
# an existing bharatfarms.db working without a migration tool.
_ADDED_COLUMNS = {
    "plot": [("agro_polygon_id", "VARCHAR")],
    "plotanalysis": [
        ("soil", "JSON"),
        ("accumulated", "JSON"),
        ("ndvi_source", "VARCHAR DEFAULT ''"),
    ],
}


def _lightweight_migrate() -> None:
    from sqlalchemy import text

    with engine.begin() as conn:
        for table, cols in _ADDED_COLUMNS.items():
            try:
                existing = {row[1] for row in conn.exec_driver_sql(f'PRAGMA table_info("{table}")')}
            except Exception:  # noqa: BLE001 - non-sqlite or table missing
                continue
            for name, ddl in cols:
                if name not in existing:
                    try:
                        conn.exec_driver_sql(f'ALTER TABLE "{table}" ADD COLUMN {name} {ddl}')
                    except Exception:  # noqa: BLE001
                        pass


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
