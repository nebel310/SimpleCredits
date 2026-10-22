from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rawdata.constants import DEFAULT_OUTPUT, TABLE_ORDER
from rawdata.exporters import (
    write_csv,
    write_json,
    write_manifest,
    write_schema,
    write_sqlite,
)
from rawdata.generator import generate_all, validate


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate the synthetic SimpleCredits raw data database."
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--companies", type=int, default=120)
    parser.add_argument("--months", type=int, default=12)
    parser.add_argument("--no-csv", action="store_true")
    parser.add_argument("--no-json", action="store_true")
    parser.add_argument("--no-documents", action="store_true")
    return parser


def write_documents(output_dir: Path, document_texts: dict[str, str]) -> int:
    directory = output_dir / "documents"
    if directory.exists():
        shutil.rmtree(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for relative_path, text in document_texts.items():
        path = output_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return len(document_texts)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_dir: Path = args.out
    output_dir.mkdir(parents=True, exist_ok=True)

    print(
        f"generating companies={args.companies} months={args.months} seed={args.seed}",
        flush=True,
    )
    tables, document_texts = generate_all(args.seed, args.companies, args.months)

    errors = validate(tables)
    if errors:
        print("validation failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    write_schema(output_dir)
    write_sqlite(output_dir, tables)
    if not args.no_csv:
        write_csv(output_dir, tables)
    if not args.no_json:
        write_json(output_dir, tables)
    if not args.no_documents:
        write_documents(output_dir, document_texts)
    write_manifest(output_dir, tables, args.seed, args.companies, args.months)

    counts = {table: len(tables.get(table, [])) for table in TABLE_ORDER}
    width = max(len(table) for table in TABLE_ORDER)
    print(f"\noutput: {output_dir}", flush=True)
    for table in TABLE_ORDER:
        print(f"  {table:<{width}} {counts[table]:>9,}")
    print(f"  {'TOTAL':<{width}} {sum(counts.values()):>9,}")
    if not args.no_documents:
        print(f"  documents files: {len(document_texts):,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
