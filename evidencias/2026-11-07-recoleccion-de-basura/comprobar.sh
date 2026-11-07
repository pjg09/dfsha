#!/usr/bin/env bash
# Después de la recolección de basura: réplicas en disco frente a las esperadas por los metadatos, y lectura
# de todos los archivos vivos. Se ejecuta desde la raíz del repositorio con el clúster en marcha.
set -uo pipefail
cd "$(dirname "$0")/../.."
run=deploy/aws/run.sh
step() { printf '\n## %s\n' "$*"; }

step "Réplicas en disco de cada nodo de datos ($(date -u +%T))"
total=0
for host in datanode-1 datanode-2 datanode-3 datanode-4 datanode-5; do
  count=$($run ssh "$host" "sudo find /srv/dfsha/data/blocks -type f ! -name '*.meta' | wc -l")
  echo "$host: $count"; total=$((total + count))
done
echo "total: $total"

step "Réplicas esperadas según los metadatos: bloques de la versión vigente de cada archivo × 3"
expected=0
for path in /grande.bin /datos.bin /rf3.bin /texto.txt; do
  blocks=$($run dfsha pedro stat "$path" | awk '/^bloques:/ {print $2}')
  echo "$path: $blocks bloques"; expected=$((expected + blocks * 3))
done
$run dfsha pedro ls /
echo "esperadas: $expected"

step "Los archivos vivos se leen enteros"
$run ssh client-1 "df -h / | tail -1"
$run dfsha pedro get /grande.bin /data/grande-tras-gc.bin
$run ssh client-1 "sudo docker exec client-1 sha256sum /data/grande.bin /data/grande-tras-gc.bin"
for path in /datos.bin /rf3.bin; do $run dfsha pedro get "$path" "/data/tras-gc-$(basename "$path")"; done
echo '$ dfsha read /texto.txt 0 100'; $run dfsha pedro read /texto.txt 0 100; echo
# Las copias ocupan el disco raíz de client-1 (8 GiB): se borran al terminar
$run ssh client-1 "sudo rm -f /srv/dfsha/client/grande-tras-gc.bin /srv/dfsha/client/tras-gc-*"
