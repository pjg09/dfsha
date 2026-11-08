#!/usr/bin/env bash
# Replicación y fallos (§5.2): caída de un nodo de datos; lecturas, escrituras y re-replicación (fase I §9.2,
# §9.3 y Tabla 29), y borrado de las réplicas de más cuando vuelve. Se ejecuta desde la raíz del repositorio.
# Respecto al de 2026-11-07: un bloque que la recolección de basura borra de todos los nodos ya no cuenta como
# falto de réplicas (antes el contador no llegaba nunca a 0), y el nodo caído vuelve si el script se corta.
set -uo pipefail
cd "$(dirname "$0")/../.."
run=deploy/aws/run.sh
VICTIM=datanode-3
NODES=(datanode-1 datanode-2 datanode-3 datanode-4 datanode-5)
tmp=$(mktemp -d)
# Si el script se corta, el nodo caído vuelve
trap '$run ssh "$VICTIM" "sudo docker start $VICTIM >/dev/null" 2>/dev/null || true' EXIT
step() { printf '\n## %s\n' "$*"; }
now() { date -u +%T; }
blocks_of() { $run ssh "$1" "sudo find /srv/dfsha/data/blocks -type f ! -name '*.meta' -printf '%f\n'"; }
check() {  # check <nodo excluido o vacío> <archivo con los block_id conocidos>: réplicas por bloque
  local skip=$1 known=$2 all=$tmp/all.txt line=""
  : > "$all"
  for host in "${NODES[@]}"; do
    [[ $host == "$skip" ]] && { line+="$host=caído "; continue; }
    blocks_of "$host" > "$tmp/$host.txt"; cat "$tmp/$host.txt" >> "$all"; line+="$host=$(wc -l < "$tmp/$host.txt") "
  done
  sort -u "$all" "$known" -o "$known"
  # Bloques en disco con menos de 3 réplicas en los nodos contados, y con más de 3. Los que ya no están en ningún
  # nodo no cuentan como faltos de réplicas: con un solo nodo caído y R = 3, solo la recolección de basura puede
  # borrar todas las réplicas de un bloque, y entonces ya no pertenece a nada vivo (§9.3)
  local under over gone
  under=$(sort "$all" | uniq -c | awk '$1 < 3' | wc -l)
  over=$(sort "$all" | uniq -c | awk '$1 > 3' | wc -l)
  gone=$(comm -23 "$known" <(sort -u "$all") | wc -l)
  echo "$line| bloques=$(sort -u "$all" | wc -l) con menos de 3 réplicas=$under con más de 3=$over borrados por la recolección=$gone"
}
poll() {  # poll <nodo excluido> <segundos desde>: cuenta cada 5 s hasta que exista el archivo stop
  local skip=$1 since=$2
  while [[ ! -f $tmp/stop ]]; do
    echo "[$(now)] +$(( $(date +%s) - since )) s: $(check "$skip" "$tmp/known.txt")"
    sleep 5
  done
}

step "Versión desplegada y estado inicial ($(now))"
$run ssh client-1 "sudo docker ps --format '{{.Image}}' | sed 's/^.*amazonaws.com\//    /'"
$run dfsha pedro ls /
: > "$tmp/known.txt"
check "" "$tmp/known.txt"

step "Caída de $VICTIM: docker stop --time 0"
$run ssh "$VICTIM" "sudo docker stop --time 0 $VICTIM >/dev/null && echo \"[\$(date -u +%T)] $VICTIM parado\""
stopped=$(date +%s)
poll "$VICTIM" "$stopped" > "$tmp/poll.log" 2>&1 &
poller=$!

step "Lecturas y escrituras durante la caída, antes de que se declare caído ($(now))"
$run dfsha pedro get /grande.bin /data/grande-durante.bin
$run ssh client-1 "sudo docker exec client-1 sha256sum /data/grande.bin /data/grande-durante.bin; sudo rm -f /srv/dfsha/client/grande-durante.bin"
$run ssh client-1 "sudo docker exec client-1 sh -c 'head -c 67108864 /dev/urandom > /data/durante.bin'"
$run dfsha pedro put /data/durante.bin /durante-la-caida.bin

step "Re-replicación: réplicas en los cuatro nodos vivos, contadas cada 5 s desde la caída"
until grep -q "con menos de 3 réplicas=0 " "$tmp/poll.log" && (( $(date +%s) - stopped > 40 )); do sleep 5; done
touch "$tmp/stop"; wait "$poller"; rm -f "$tmp/stop"
cat "$tmp/poll.log"
first_ok=$(grep -m1 "con menos de 3 réplicas=0 " "$tmp/poll.log" | sed -E 's/^\[[^]]*\] \+([0-9]+) s.*/\1/')
echo "Todos los bloques vuelven a tener 3 réplicas sin $VICTIM a los $first_ok s de la caída"

step "Órdenes de re-replicación del líder"
for host in metadata-1 metadata-2 metadata-3; do
  $run ssh "$host" "sudo docker logs --since 5m $host 2>&1 | grep 'Re-replicación' | sed -E 's/^([^ ]+) INFO ([^ ]+) [^:]+: /\1 \2: /'" > "$tmp/orders.txt"
  [[ -s $tmp/orders.txt ]] && { head -2 "$tmp/orders.txt"; echo "  ..."; tail -1 "$tmp/orders.txt"; echo "  $host: $(wc -l < "$tmp/orders.txt") órdenes"; }
done

step "$VICTIM vuelve con sus bloques: sobran réplicas"
$run ssh "$VICTIM" "sudo docker start $VICTIM >/dev/null && echo \"[\$(date -u +%T)] $VICTIM arrancado\""
returned=$(date +%s)
poll "" "$returned" > "$tmp/poll.log" 2>&1 &
poller=$!
until grep -q "con menos de 3 réplicas=0 con más de 3=0" "$tmp/poll.log" && (( $(date +%s) - returned > 20 )); do sleep 5; done
touch "$tmp/stop"; wait "$poller"
cat "$tmp/poll.log"
for host in metadata-1 metadata-2 metadata-3; do
  n=$($run ssh "$host" "sudo docker logs --since 3m $host 2>&1 | grep -c 'de más o corrupta'"); [[ $n -gt 0 ]] && echo "$host: $n réplicas de más borradas"
done

step "Lectura final ($(now))"
$run dfsha pedro get /grande.bin /data/grande-final.bin
$run ssh client-1 "sudo docker exec client-1 sha256sum /data/grande.bin /data/grande-final.bin; sudo rm -f /srv/dfsha/client/grande-final.bin /srv/dfsha/client/durante.bin"
rm -rf "$tmp"
