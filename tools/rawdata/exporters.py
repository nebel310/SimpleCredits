from __future__ import annotations

import csv
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from rawdata.constants import JSON_FIELDS, SCHEMA_VERSION, TABLE_ORDER
from rawdata.identifiers import iso_dt
from rawdata.schema import schema_sql, table_columns


def _json_value(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _sql_value(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool):
        return int(value)
    return value


def write_schema(output_dir: Path) -> Path:
    path = output_dir / "schema.sql"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(schema_sql(), encoding="utf-8")
    return path


def write_sqlite(output_dir: Path, tables: dict[str, list[dict]]) -> Path:
    path = output_dir / "simplecredits_raw.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    connection = sqlite3.connect(path)
    try:
        connection.executescript(schema_sql())
        for table in TABLE_ORDER:
            rows = tables.get(table, [])
            if not rows:
                continue
            columns = table_columns(table)
            placeholders = ", ".join("?" for _ in columns)
            column_sql = ", ".join(f'"{column}"' for column in columns)
            values = [
                tuple(_sql_value(row.get(column)) for column in columns)
                for row in rows
            ]
            connection.executemany(
                f'INSERT INTO "{table}" ({column_sql}) VALUES ({placeholders})',
                values,
            )
        connection.commit()
        connection.execute("VACUUM")
    finally:
        connection.close()
    return path


def write_csv(output_dir: Path, tables: dict[str, list[dict]]) -> Path:
    directory = output_dir / "csv"
    directory.mkdir(parents=True, exist_ok=True)
    for table in TABLE_ORDER:
        rows = tables.get(table, [])
        path = directory / f"{table}.csv"
        columns = table_columns(table)
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                serialized = {}
                for column in columns:
                    value = row.get(column)
                    if isinstance(value, (dict, list)):
                        value = json.dumps(value, ensure_ascii=False)
                    elif isinstance(value, bool):
                        value = int(value)
                    serialized[column] = value
                writer.writerow(serialized)
    return directory


def write_json(output_dir: Path, tables: dict[str, list[dict]]) -> Path:
    directory = output_dir / "json"
    directory.mkdir(parents=True, exist_ok=True)
    for table in TABLE_ORDER:
        rows = tables.get(table, [])
        path = directory / f"{table}.json"
        json_fields = set(JSON_FIELDS.get(table, []))
        payload = []
        for row in rows:
            item = {}
            for column in table_columns(table):
                value = row.get(column)
                item[column] = _json_value(value) if column in json_fields else value
            payload.append(item)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return directory


def write_manifest(
    output_dir: Path,
    tables: dict[str, list[dict]],
    seed: int,
    n_companies: int,
    months: int,
) -> Path:
    counts = {table: len(tables.get(table, [])) for table in TABLE_ORDER}
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": iso_dt(datetime.now(timezone.utc)),
        "synthetic": True,
        "seed": seed,
        "n_companies": n_companies,
        "months": months,
        "database": "simplecredits_raw.db",
        "schema": "schema.sql",
        "csv_dir": "csv",
        "json_dir": "json",
        "documents_dir": "documents",
        "counts": counts,
        "total_rows": sum(counts.values()),
        "notes": [
            "All data is synthetic and generated for the SimpleCredits prototype.",
            "INN, OGRN, KPP, accounts, VIN and cadastral numbers are generated values.",
            "External integrations are emulated and must be replaced by mocks in the product.",
            "JSON columns are stored as JSON strings in SQLite and CSV, parsed in JSON exports.",
        ],
    }
    path = output_dir / "manifest.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
