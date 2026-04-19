from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Mapping

from app.core.config import settings
from app.db.field_descriptions import FIELD_DESCRIPTIONS

SCHEMA_PATH = Path(__file__).with_name("schema.sql")
MANAGED_TABLES = ("towers", "geology_records")
AUTO_MANAGED_FIELDS = {"created_at", "updated_at"}


def get_database_path() -> Path:
    return settings.database_path


def connect_database() -> sqlite3.Connection:
    database_path = get_database_path()
    database_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = NORMAL")
    return connection


def initialize_database() -> None:
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")

    with connect_database() as connection:
        legacy_tables = _move_outdated_managed_tables(connection)
        connection.execute("DROP TABLE IF EXISTS schema_field_descriptions")
        connection.executescript(schema_sql)
        _copy_legacy_table_data(connection, legacy_tables)
        _upsert_field_descriptions(connection)


def get_schema_descriptions() -> dict[str, Any]:
    with connect_database() as connection:
        rows = connection.execute(
            """
            SELECT table_name, field_name, display_name, data_type, description, is_required, is_primary_key
            FROM schema_field_descriptions
            WHERE table_name IN ('towers', 'geology_records')
            ORDER BY table_name, display_order, field_name
            """
        ).fetchall()

    tables: dict[str, Any] = {}
    for row in rows:
        table_name = row["table_name"]
        tables.setdefault(table_name, {"fields": []})
        tables[table_name]["fields"].append(
            {
                "name": row["field_name"],
                "display_name": row["display_name"],
                "type": row["data_type"],
                "description": row["description"],
                "required": bool(row["is_required"]),
                "primary_key": bool(row["is_primary_key"]),
            }
        )

    return {"database_path": str(get_database_path()), "tables": tables}


def insert_database_record(table_name: str, values: Mapping[str, Any]) -> dict[str, Any]:
    if table_name not in MANAGED_TABLES:
        raise ValueError(f"Unsupported database table: {table_name}")

    fields = [field for field in FIELD_DESCRIPTIONS if field.table_name == table_name]
    writable_fields = [field for field in fields if field.field_name not in AUTO_MANAGED_FIELDS]
    writable_names = {field.field_name for field in writable_fields}
    unexpected_names = sorted(set(values) - writable_names - AUTO_MANAGED_FIELDS)
    if unexpected_names:
        raise ValueError(f"Unsupported fields for {table_name}: {', '.join(unexpected_names)}")

    payload: dict[str, Any] = {}
    for field in writable_fields:
        raw_value = values.get(field.field_name)
        if raw_value == "":
            raw_value = None

        if raw_value is None:
            if field.is_required:
                raise ValueError(f"Field is required: {field.field_name}")
            continue

        payload[field.field_name] = _coerce_record_value(field.data_type, raw_value)

    if not payload:
        raise ValueError("At least one field value is required")

    columns_sql = ", ".join(f'"{column}"' for column in payload)
    placeholders_sql = ", ".join("?" for _ in payload)

    with connect_database() as connection:
        cursor = connection.execute(
            f'INSERT INTO "{table_name}" ({columns_sql}) VALUES ({placeholders_sql})',
            list(payload.values()),
        )
        rowid = cursor.lastrowid

    return {"table_name": table_name, "rowid": rowid, "record": payload}


def list_database_records(table_name: str, limit: int = 20) -> dict[str, Any]:
    if table_name not in MANAGED_TABLES:
        raise ValueError(f"Unsupported database table: {table_name}")

    safe_limit = max(1, min(limit, 100))
    with connect_database() as connection:
        rows = connection.execute(
            f'SELECT rowid AS rowid, * FROM "{table_name}" ORDER BY rowid DESC LIMIT ?',
            (safe_limit,),
        ).fetchall()

    return {
        "table_name": table_name,
        "records": [dict(row) for row in rows],
    }


def delete_database_record(table_name: str, rowid: int) -> dict[str, Any]:
    if table_name not in MANAGED_TABLES:
        raise ValueError(f"Unsupported database table: {table_name}")

    if rowid < 1:
        raise ValueError("rowid must be a positive integer")

    with connect_database() as connection:
        cursor = connection.execute(f'DELETE FROM "{table_name}" WHERE rowid = ?', (rowid,))

    if cursor.rowcount == 0:
        raise LookupError(f"Record not found in {table_name}: rowid={rowid}")

    return {"table_name": table_name, "rowid": rowid}


def _upsert_field_descriptions(connection: sqlite3.Connection) -> None:
    connection.executemany(
        """
        INSERT INTO schema_field_descriptions (
            table_name,
            field_name,
            display_name,
            data_type,
            description,
            is_required,
            is_primary_key,
            display_order
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(table_name, field_name) DO UPDATE SET
            display_name = excluded.display_name,
            data_type = excluded.data_type,
            description = excluded.description,
            is_required = excluded.is_required,
            is_primary_key = excluded.is_primary_key,
            display_order = excluded.display_order
        """,
        [
            (
                field.table_name,
                field.field_name,
                field.display_name,
                field.data_type,
                field.description,
                int(field.is_required),
                int(field.is_primary_key),
                field.display_order,
            )
            for field in FIELD_DESCRIPTIONS
        ],
    )


def _move_outdated_managed_tables(connection: sqlite3.Connection) -> dict[str, tuple[str, list[str]]]:
    expected_columns = _expected_managed_columns()
    legacy_tables: dict[str, tuple[str, list[str]]] = {}

    connection.execute("PRAGMA foreign_keys = OFF")
    for table_name in MANAGED_TABLES:
        existing_columns = _get_table_columns(connection, table_name)
        if not existing_columns or existing_columns == expected_columns[table_name]:
            continue

        legacy_table_name = f"__legacy_{table_name}"
        connection.execute(f'DROP TABLE IF EXISTS "{legacy_table_name}"')
        connection.execute(f'ALTER TABLE "{table_name}" RENAME TO "{legacy_table_name}"')
        legacy_tables[table_name] = (legacy_table_name, existing_columns)

    return legacy_tables


def _copy_legacy_table_data(connection: sqlite3.Connection, legacy_tables: dict[str, tuple[str, list[str]]]) -> None:
    expected_columns = _expected_managed_columns()

    for table_name, (legacy_table_name, existing_columns) in legacy_tables.items():
        copy_columns = [column for column in expected_columns[table_name] if column in existing_columns]
        if copy_columns:
            columns_sql = ", ".join(f'"{column}"' for column in copy_columns)
            connection.execute(
                f'INSERT INTO "{table_name}" ({columns_sql}) SELECT {columns_sql} FROM "{legacy_table_name}"'
            )

        connection.execute(f'DROP TABLE IF EXISTS "{legacy_table_name}"')

    connection.execute("PRAGMA foreign_keys = ON")


def _get_table_columns(connection: sqlite3.Connection, table_name: str) -> list[str]:
    rows = connection.execute(f'PRAGMA table_info("{table_name}")').fetchall()
    return [row["name"] for row in rows]


def _expected_managed_columns() -> dict[str, list[str]]:
    columns: dict[str, list[str]] = {table_name: [] for table_name in MANAGED_TABLES}
    for field in sorted(FIELD_DESCRIPTIONS, key=lambda item: (item.table_name, item.display_order)):
        if field.table_name in columns:
            columns[field.table_name].append(field.field_name)
    return columns


def _coerce_record_value(data_type: str, value: Any) -> Any:
    if data_type == "REAL":
        if isinstance(value, bool):
            raise ValueError("Boolean values cannot be saved into REAL fields")
        try:
            return float(value)
        except (TypeError, ValueError) as error:
            raise ValueError(f"Invalid REAL value: {value}") from error

    if data_type == "INTEGER":
        if isinstance(value, bool):
            raise ValueError("Boolean values cannot be saved into INTEGER fields")
        try:
            return int(value)
        except (TypeError, ValueError) as error:
            raise ValueError(f"Invalid INTEGER value: {value}") from error

    return str(value)
