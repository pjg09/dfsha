#!/usr/bin/env bash
# Genera el código Python de los contratos gRPC de proto/ en dfsha/v1/ (ADR 0038).
# Uso: uv run scripts/generate-proto.sh
set -euo pipefail
cd "$(dirname "$0")/.."

python -m grpc_tools.protoc \
  --proto_path=proto \
  --python_out=. \
  --pyi_out=. \
  --grpc_python_out=. \
  proto/dfsha/v1/*.proto

# Paquete Python del código generado
cat > dfsha/v1/__init__.py <<'PY'
"""Código generado a partir de proto/dfsha/v1/ con scripts/generate-proto.sh. No se edita a mano."""
PY
