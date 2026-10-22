from __future__ import annotations

from pathlib import Path

import grpc_tools
from grpc_tools import protoc

ML_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ML_ROOT.parent
PROTO_ROOT = REPO_ROOT / "proto"
OUTPUT_ROOT = ML_ROOT / "src"
PROTO_FILE = PROTO_ROOT / "simplecredits" / "scoring" / "v1" / "scoring.proto"
PROTO_INCLUDE = Path(grpc_tools.__file__).resolve().parent / "_proto"


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    arguments = [
        "protoc",
        f"-I{PROTO_ROOT}",
        f"-I{PROTO_INCLUDE}",
        f"--python_out={OUTPUT_ROOT}",
        f"--grpc_python_out={OUTPUT_ROOT}",
        str(PROTO_FILE),
    ]
    exit_code = protoc.main(arguments)
    if exit_code != 0:
        raise SystemExit(f"protoc failed with exit code {exit_code}")

    generated_package = OUTPUT_ROOT / "simplecredits" / "scoring" / "v1"
    for directory in [generated_package.parent, generated_package]:
        directory.mkdir(parents=True, exist_ok=True)
        init_file = directory / "__init__.py"
        if not init_file.exists():
            init_file.write_text("", encoding="utf-8")
    print(f"generated python stubs in {generated_package}")


if __name__ == "__main__":
    main()
