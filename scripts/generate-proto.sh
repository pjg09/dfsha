#!/usr/bin/env bash
# Genera el código Python de proto/: los contratos de DFSha en dfsha/v1/ (ADR 0038) y el subconjunto de
# la API de etcd en dfsha/etcd/ (ADR 0041).
# Uso: uv run scripts/generate-proto.sh
set -euo pipefail
cd "$(dirname "$0")/.."

python -m grpc_tools.protoc \
  --proto_path=proto \
  --python_out=. \
  --pyi_out=. \
  --grpc_python_out=. \
  proto/dfsha/v1/*.proto \
  proto/dfsha/etcd/*.proto

# Paquetes Python del código generado
for package in v1 etcd; do
  printf '"""Código generado a partir de proto/dfsha/%s/ con scripts/generate-proto.sh. No se edita a mano."""\n' \
    "$package" > "dfsha/$package/__init__.py"
done
