"""SQL Schema definitions and table management for Cross-Bank Mule Detection."""
import sqlite3
import logging
from typing import Optional
from backend.app.database.connection import get_db_connection

logger = logging.getLogger("mule-detection-database")

SCHEMA_STATEMENTS = [
    # 1. Banks Table
    """
    CREATE TABLE IF NOT EXISTS banks (
        id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
        bank_name TEXT NOT NULL,
        ifsc_prefix TEXT NOT NULL UNIQUE,
        public_key_fingerprint TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_active INTEGER DEFAULT 1
    );
    """,

    # 2. Graph Snapshots Table
    """
    CREATE TABLE IF NOT EXISTS graph_snapshots (
        id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
        snapshot_time TIMESTAMP NOT NULL,
        node_count INTEGER NOT NULL,
        edge_count INTEGER NOT NULL,
        serialized_graph TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,

    # 3. Components Table
    """
    CREATE TABLE IF NOT EXISTS components (
        id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
        detection_time TIMESTAMP NOT NULL,
        risk_score DECIMAL(5,4) NOT NULL,
        hashed_nodes TEXT NOT NULL,
        bank_ids TEXT NOT NULL,
        feature_vector TEXT NOT NULL,
        shap_explanation TEXT,
        status TEXT DEFAULT 'active',
        alert_id TEXT,
        FOREIGN KEY (alert_id) REFERENCES alerts(id)
    );
    """,

    # 4. Alerts Table
    """
    CREATE TABLE IF NOT EXISTS alerts (
        id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
        component_id TEXT NOT NULL,
        severity TEXT NOT NULL,
        dispatch_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        dispatched_to TEXT NOT NULL,
        resolution_status TEXT DEFAULT 'pending',
        resolved_at TIMESTAMP,
        resolution_notes TEXT,
        FOREIGN KEY (component_id) REFERENCES components(id)
    );
    """,

    # 5. Hashed Edges Table
    """
    CREATE TABLE IF NOT EXISTS hashed_edges (
        id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
        sender_hash TEXT NOT NULL,
        receiver_hash TEXT NOT NULL,
        amount DECIMAL(15,2) NOT NULL,
        timestamp TIMESTAMP NOT NULL,
        bank_id TEXT NOT NULL,
        local_risk_score DECIMAL(5,4),
        is_interbank INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (bank_id) REFERENCES banks(id)
    );
    """,

    # 6. Investigations Table (Flow B)
    """
    CREATE TABLE IF NOT EXISTS investigations (
        id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
        component_id TEXT NOT NULL,
        investigation_salt TEXT NOT NULL,
        started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP,
        depth_reached INTEGER DEFAULT 0,
        banks_queried TEXT,
        traversal_path TEXT,
        status TEXT DEFAULT 'active',
        closed_by TEXT,
        FOREIGN KEY (component_id) REFERENCES components(id)
    );
    """,

    # 7. STR Reports Table (FIU-IND Compliance)
    """
    CREATE TABLE IF NOT EXISTS str_reports (
        id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
        alert_id TEXT NOT NULL,
        bank_id TEXT NOT NULL,
        report_payload TEXT NOT NULL,
        generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        filed_status TEXT DEFAULT 'draft',
        FOREIGN KEY (alert_id) REFERENCES alerts(id),
        FOREIGN KEY (bank_id) REFERENCES banks(id)
    );
    """,

    # Performance Indexes
    "CREATE INDEX IF NOT EXISTS idx_hashed_edges_sender_hash ON hashed_edges(sender_hash);",
    "CREATE INDEX IF NOT EXISTS idx_hashed_edges_receiver_hash ON hashed_edges(receiver_hash);",
    "CREATE INDEX IF NOT EXISTS idx_hashed_edges_timestamp ON hashed_edges(timestamp);",
    "CREATE INDEX IF NOT EXISTS idx_hashed_edges_bank_id ON hashed_edges(bank_id);",
    "CREATE INDEX IF NOT EXISTS idx_components_status ON components(status);",
    "CREATE INDEX IF NOT EXISTS idx_components_risk_score ON components(risk_score);",
    "CREATE INDEX IF NOT EXISTS idx_alerts_resolution_status ON alerts(resolution_status);",
    "CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity);",
    "CREATE INDEX IF NOT EXISTS idx_investigations_component_id ON investigations(component_id);",
    "CREATE INDEX IF NOT EXISTS idx_str_reports_alert_id ON str_reports(alert_id);",
    "CREATE INDEX IF NOT EXISTS idx_str_reports_bank_id ON str_reports(bank_id);"
]

TABLE_NAMES = [
    "banks",
    "graph_snapshots",
    "components",
    "alerts",
    "hashed_edges",
    "investigations",
    "str_reports"
]


def create_tables(conn: Optional[sqlite3.Connection] = None) -> None:
    """Execute all CREATE TABLE and CREATE INDEX statements in order."""
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        with conn:
            for statement in SCHEMA_STATEMENTS:
                conn.execute(statement)
        logger.info("Database schema tables and indexes successfully verified/created")
    finally:
        if should_close:
            conn.close()


def drop_tables(conn: Optional[sqlite3.Connection] = None) -> None:
    """Drop all tables in reverse dependency order for testing/resetting."""
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    drop_order = [
        "str_reports",
        "investigations",
        "hashed_edges",
        "alerts",
        "components",
        "graph_snapshots",
        "banks"
    ]

    try:
        with conn:
            conn.execute("PRAGMA foreign_keys = OFF;")
            for table in drop_order:
                conn.execute(f"DROP TABLE IF EXISTS {table};")
            conn.execute("PRAGMA foreign_keys = ON;")
        logger.info("All database tables dropped cleanly")
    finally:
        if should_close:
            conn.close()


def table_exists(table_name: str, conn: Optional[sqlite3.Connection] = None) -> bool:
    """Check if a specific table exists in the database."""
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?;",
            (table_name,)
        )
        return cursor.fetchone() is not None
    finally:
        if should_close:
            conn.close()
