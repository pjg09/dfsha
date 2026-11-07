#!/usr/bin/env bash
# E2 (ADR 0028): tasa de transferencia con 3, 4 y 5 nodos de datos. Para cambiar el número de nodos se paran
# o se arrancan datanode-4 y datanode-5, y antes de medir se espera a que el líder termine de re-replicar o
# de borrar réplicas de más: ningún punto se mide con ese tráfico de fondo.
set -euo pipefail
cd "$(dirname "$0")/.."
run=deploy/aws/run.sh
now() { date -u +%T; }
leader_orders() {  # órdenes de re-replicación y de borrado registradas por el líder (solo él las registra)
  local total=0
  for host in metadata-1 metadata-2 metadata-3; do
    total=$((total + $($run ssh "$host" "sudo docker logs $host 2>&1 | grep -cE 'Re-replicación|de más o corrupta'" || true)))
  done
  echo "$total"
}
settle() {  # espera a que pasen al menos $1 s y las órdenes del líder dejen de crecer durante 20 s
  local since=$(date +%s) previous=-1 stable=0
  while true; do
    sleep 10
    local current; current=$(leader_orders)
    echo "[$(now)] órdenes del líder hasta ahora: $current" >&2
    if (( current == previous )); then stable=$((stable + 1)); else stable=0; fi
    previous=$current
    (( $(date +%s) - since >= $1 && stable >= 2 )) && return
  done
}
measure() { bench/ejecutar.sh e2 transfer --condition "$1-nodos" --sizes 256,1024 --reps 5; }

echo "[$(now)] 3 nodos: se paran datanode-4 y datanode-5" >&2
for host in datanode-4 datanode-5; do $run ssh "$host" "sudo docker stop --time 0 $host >/dev/null"; done
settle 45   # caídos a los 30 s y re-replicación terminada
measure 3
echo "[$(now)] 4 nodos: vuelve datanode-4" >&2
$run ssh datanode-4 "sudo docker start datanode-4 >/dev/null"
settle 20
measure 4
echo "[$(now)] 5 nodos: vuelve datanode-5" >&2
$run ssh datanode-5 "sudo docker start datanode-5 >/dev/null"
settle 20
measure 5
