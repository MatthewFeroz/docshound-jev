import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from app.config import get_settings

DATABASE_FILENAME = "docshound.db"


@contextmanager
def database_connection(
    path: Path,
    *,
    timeout: float = 5,
    write_ahead_log: bool = False,
) -> Iterator[sqlite3.Connection]:
    """Yield a transactional SQLite connection and always close its handle."""
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=timeout)
    connection.row_factory = sqlite3.Row
    try:
        if write_ahead_log:
            connection.execute("PRAGMA journal_mode=WAL")
        yield connection
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()


def resolve_database_path(
    *,
    configured_path: str | None = None,
    backend_root: Path | None = None,
) -> Path:
    """Reuse existing state when upgrading the former single-app layout."""
    if configured_path:
        return Path(configured_path).expanduser().resolve()

    root = backend_root or Path(__file__).resolve().parent.parent
    backend_database = root / "data" / DATABASE_FILENAME
    legacy_database = root.parent / "data" / DATABASE_FILENAME
    if not backend_database.is_file() and legacy_database.is_file():
        return legacy_database
    return backend_database


DB_PATH = resolve_database_path(
    configured_path=get_settings().docshound_db_path,
)
