import re
import shutil
from pathlib import Path

import grpc_tools


BACKEND_ROOT = Path(__file__).resolve().parent.parent
PROTO_ROOT = BACKEND_ROOT.parent / "proto"
OUTPUT_DIR = BACKEND_ROOT / "grpc" / "generated"
WELL_KNOWN_PROTO_DIR = Path(grpc_tools.__file__).parent / "_proto"


_GENERATED_IMPORT_RE = re.compile(
    r"^from (\w+(?:\.\w+)*) import (\w+_pb2) as (\w+)$",
    re.MULTILINE,
)


def clean_output():
    """Удаляет каталог с прежними сгенерированными стабами"""
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)


def _is_well_known(module_path):
    """Проверяет относится ли модуль к well-known google protobuf"""
    return module_path.startswith("google.")


def patch_grpc_imports():
    """Заменяет абсолютные импорты пакета в grpc-модулях на относительные"""
    for path in OUTPUT_DIR.rglob("*_pb2_grpc.py"):
        text = path.read_text(encoding="utf-8")

        def replace(match):
            module_path, mod_name, alias = match.groups()
            if _is_well_known(module_path):
                return match.group(0)
            return f"from . import {mod_name} as {alias}"

        patched = _GENERATED_IMPORT_RE.sub(replace, text)
        if patched != text:
            path.write_text(patched, encoding="utf-8")


def write_package_inits():
    """Создаёт __init__.py в каждом каталоге сгенерированного дерева"""
    for path in OUTPUT_DIR.rglob("*"):
        if path.is_dir() and not (path / "__init__.py").exists():
            (path / "__init__.py").write_text("")


def generate():
    """Компилирует все proto-файлы из корневого каталога proto в backend grpc generated"""
    from grpc_tools import protoc

    clean_output()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    proto_files = list(PROTO_ROOT.rglob("*.proto"))
    if not proto_files:
        raise SystemExit(f"Не найдено ни одного .proto в {PROTO_ROOT}")

    if not WELL_KNOWN_PROTO_DIR.exists():
        raise SystemExit(f"Не найден каталог с well-known proto: {WELL_KNOWN_PROTO_DIR}")

    args = [
        "protoc",
        f"-I{PROTO_ROOT}",
        f"-I{WELL_KNOWN_PROTO_DIR}",
        f"--python_out={OUTPUT_DIR}",
        f"--grpc_python_out={OUTPUT_DIR}",
        *[str(p) for p in proto_files],
    ]

    exit_code = protoc.main(args)
    if exit_code != 0:
        raise SystemExit(f"protoc завершился с кодом {exit_code}")

    write_package_inits()
    patch_grpc_imports()

    print(f"Сгенерировано {len(proto_files)} proto-файлов в {OUTPUT_DIR}")


if __name__ == "__main__":
    generate()