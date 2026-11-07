#!/usr/bin/env bash
# E3 (ADR 0046): latencia de escritura de un bloque con W = 2 y con W = 3. Para W = 3 se reinstala el
# clúster con DFSHA_WRITE_QUORUM=3 (lo leen el líder y los nodos de datos) y al final se vuelve a W = 2.
set -euo pipefail
cd "$(dirname "$0")/.."
VERSION=${DFSHA_IMAGE_TAG:-0.12.1}
BASE_ENV="DFSHA_GRACE_PERIOD_S=60 DFSHA_BLOCK_REPORT_INTERVAL_S=60"
now() { date -u +%T; }
reinstall() {  # reinstall <variables extra>: todos los hosts con la misma versión, y espera al modo seguro
  echo "[$(now)] reinstalación con: $1" >&2
  DFSHA_IMAGE_TAG=$VERSION DFSHA_EXTRA_ENV="$1" deploy/aws/deploy.sh install 2>&1 | grep -E "Clúster|ERROR" >&2
  sleep 30
  deploy/aws/run.sh ssh datanode-1 "sudo docker exec datanode-1 env | grep -E 'WRITE_QUORUM' || echo 'WRITE_QUORUM por defecto (2)'" >&2
}

bench/ejecutar.sh e3 blocks --condition w2 --count 16 --reps 5
reinstall "$BASE_ENV DFSHA_WRITE_QUORUM=3"
bench/ejecutar.sh e3 blocks --condition w3 --count 16 --reps 5
reinstall "$BASE_ENV"
