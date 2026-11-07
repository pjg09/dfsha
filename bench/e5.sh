#!/usr/bin/env bash
# E5 (ADR 0046): tamaño de bloque de 4, 16 y 64 MiB. Para cada tamaño se reinstala el clúster con
# DFSHA_BLOCK_SIZE_BYTES (el líder lo fija al crear cada archivo; los nodos de datos limitan con él el tamaño
# máximo que aceptan), se mide put y get de 256 MiB y 1 GiB y la modificación parcial de 4 KiB en un archivo de
# 256 MiB. Al final se vuelve a 16 MiB.
set -euo pipefail
cd "$(dirname "$0")/.."
VERSION=${DFSHA_IMAGE_TAG:-0.13.0}
BASE_ENV="DFSHA_GRACE_PERIOD_S=60 DFSHA_BLOCK_REPORT_INTERVAL_S=60"
now() { date -u +%T; }
reinstall() {
  echo "[$(now)] reinstalación con: $1" >&2
  DFSHA_IMAGE_TAG=$VERSION DFSHA_EXTRA_ENV="$1" deploy/aws/deploy.sh install 2>&1 | grep -E "Clúster|ERROR" >&2
  sleep 30
  deploy/aws/run.sh ssh metadata-1 "sudo docker exec metadata-1 env | grep BLOCK_SIZE || echo 'BLOCK_SIZE_BYTES por defecto (16 MiB)'" >&2
}
for size_mib in 4 16 64; do
  reinstall "$BASE_ENV DFSHA_BLOCK_SIZE_BYTES=$((size_mib * 1024 * 1024))"
  bench/ejecutar.sh e5 transfer --condition "bloque-${size_mib}mib" --sizes 256,1024 --reps 5
  bench/ejecutar.sh e5 partial --condition "bloque-${size_mib}mib" --sizes 256 --reps 5
done
reinstall "$BASE_ENV"
