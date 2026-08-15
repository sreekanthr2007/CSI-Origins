"""Database connection management for SQLite."""
import os
import sqlite3
import pathlib
import logging
import contextlib
from typing import Optional, Generator

logger = logging.getLogger("mule-detection-database")


def get_db_path() -> str:
    """Return the absolute path to the SQLite database file."""
    custom_path = os.getenv("DATABASE_PATH")
    if custom_path:
        return os.path.abspath(custom_path)
    
    # Resolve backend/data/mule_detection.db relative to this file
    base_dir = pathlib.Path(__file__).resolve().parent.parent.parent
    data_dir = base_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return str(data_dir / "mule_detection.db")


def get_db_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Return a SQLite connection configured with Row factory and enforced Foreign Keys."""
    target_path = db_path if db_path is not None else get_db_path()
    
    # Ensure parent directory exists
    parent_dir = pathlib.Path(target_path).parent
    parent_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(target_path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    logger.debug(f"Connected to database at {target_path}")
    return conn


def close_connection(conn: Optional[sqlite3.Connection]) -> None:
    """Safely close a database connection if open."""
    if conn:
        try:
            conn.close()
            logger.debug("Database connection closed successfully")
        except Exception as e:
            logger.warning(f"Error while closing database connection: {e}")


def init_db(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Initialize database directory, establish connection, and create all schema tables."""
    from backend.app.database.schema import create_tables
    
    target_path = db_path if db_path is not None else get_db_path()
    logger.info(f"Initializing SQLite database at: {target_path}")
    conn = get_db_connection(target_path)
    create_tables(conn)
    return conn


@contextlib.contextmanager
def get_db(db_path: Optional[str] = None) -> Generator[sqlite3.Connection, None, None]:
    """Context manager for obtaining database connections with guaranteed closing."""
    conn = get_db_connection(db_path)
    try:
        yield conn
    finally:
        close_connection(conn)
