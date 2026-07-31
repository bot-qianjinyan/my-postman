from __future__ import annotations

from sqlalchemy import inspect, text

from app.database import Base, engine


def ensure_schema() -> None:
    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    with engine.begin() as conn:
        if "collections" in tables:
            cols = {c["name"] for c in inspector.get_columns("collections")}
            if "description" not in cols:
                conn.execute(text("ALTER TABLE collections ADD COLUMN description TEXT DEFAULT ''"))

        if "requests" in tables:
            cols = {c["name"] for c in inspector.get_columns("requests")}
            alters = {
                "description": "TEXT DEFAULT ''",
                "protocol": "VARCHAR(32) DEFAULT 'http'",
                "pre_request_script": "TEXT DEFAULT ''",
                "test_script": "TEXT DEFAULT ''",
                "graphql_query": "TEXT DEFAULT ''",
                "graphql_variables": "TEXT DEFAULT '{}'",
                "grpc_service": "VARCHAR(255) DEFAULT ''",
                "grpc_method": "VARCHAR(255) DEFAULT ''",
                "grpc_message": "TEXT DEFAULT '{}'",
                "ws_messages_json": "TEXT DEFAULT '[]'",
                "sort_order": "INTEGER DEFAULT 0",
            }
            for name, ddl in alters.items():
                if name not in cols:
                    conn.execute(text(f"ALTER TABLE requests ADD COLUMN {name} {ddl}"))

        if "request_history" in tables:
            cols = {c["name"] for c in inspector.get_columns("request_history")}
            if "assertions_json" not in cols:
                conn.execute(
                    text("ALTER TABLE request_history ADD COLUMN assertions_json TEXT DEFAULT '[]'")
                )
            if "source" not in cols:
                conn.execute(
                    text("ALTER TABLE request_history ADD COLUMN source VARCHAR(32) DEFAULT 'manual'")
                )
