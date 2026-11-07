#!/usr/bin/env bash
# E6 (ADR 0046): caída de un nodo de datos. Dos variantes: «parada» (docker stop: el proceso muere y las
# conexiones se rechazan) y «congelado» (docker pause: el kernel acepta conexiones pero nadie responde). En cada
# repetición cae un nodo distinto mientras client-1 lee /bench/e6.bin sin parar; del registro del líder salen el
# tiempo de detección («declarado caído») y el de re-replicación («vuelven a tener 3 réplicas»).
set -euo pipefail
cd "$(dirname "$0")/.."
run=deploy/aws/run.sh
REPS=${REPS:-5}
reads=bench/resultados/$(date -u +%F)-e6-lecturas.csv
times=bench/resultados/$(date -u +%F)-e6.csv
version=$($run ssh client-1 "sudo docker ps --format '{{.Image}}'" | sed 's/^.*://')
[[ -f $reads ]] || echo "version,variante,repeticion,hora_inicio_utc,duracion_s,resultado" > "$reads"
[[ -f $times ]] || echo "version,variante,repeticion,nodo,hora_caida_utc,hora_declarado_caido_utc,deteccion_s,hora_fin_rereplicacion_utc,rereplicacion_s" > "$times"
leader_log() {  # leader_log <desde>: líneas del registro de los tres servidores de metadatos (solo el líder las escribe)
  for host in metadata-1 metadata-2 metadata-3; do
    $run ssh "$host" "sudo docker logs --since $1 $host 2>&1 | grep -E 'declarado caído|vuelven a tener|vuelve a enviar'" || true
  done
}
seconds() { date -u -d "$1" +%s.%N; }
reader() {
  $run ssh client-1 "sudo docker exec -i -e DFSHA_USERNAME=pedro client-1 sh -c \
    'read -r DFSHA_PASSWORD; export DFSHA_PASSWORD; script=\$(cat); exec python -c \"\$script\" $*'" \
    < <(cat deploy/aws/secrets/pedro-password; cat bench/e6.py)
}
$run ssh client-1 "sudo docker exec client-1 sh -c 'head -c 268435456 /dev/urandom > /data/e6.bin'"
$run dfsha pedro rm /bench/e6.bin >/dev/null 2>&1 || true
$run dfsha pedro put /data/e6.bin /bench/e6.bin >&2
$run ssh client-1 "sudo rm -f /srv/dfsha/client/e6.bin"
for variant in parada congelado; do
  for rep in $(seq 1 "$REPS"); do
    node=datanode-$rep
    since=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    reader 100 "$variant" "$rep" | sed "s/^/$version,/" >> "$reads" &
    pid=$!
    sleep 10
    if [[ $variant == parada ]]; then action="stop --time 0"; else action=pause; fi
    trap "$run ssh $node 'sudo docker unpause $node 2>/dev/null; sudo docker start $node >/dev/null'" EXIT  # si algo falla, el nodo vuelve
    down=$($run ssh "$node" "sudo docker $action $node >/dev/null && date -u +%FT%T.%3NZ")
    echo "[$(date -u +%T)] $variant $rep: $node caído a las $down" >&2
    declared="" finished=""
    for _ in $(seq 1 36); do
      sleep 5
      lines=$(leader_log "$since")
      # Mientras la línea no existe, grep falla: con pipefail, sin «|| true» terminaría el script
      declared=$( (grep "$node declarado caído" <<< "$lines" || true) | head -1 | cut -d' ' -f1)
      [[ -n $declared ]] && finished=$( (grep "vuelven a tener" <<< "$lines" || true) | awk -v d="$declared" '$1 > d' | head -1 | cut -d' ' -f1)
      [[ -n $declared && -n $finished ]] && break
    done
    wait "$pid"
    if [[ $variant == parada ]]; then action=start; else action=unpause; fi
    $run ssh "$node" "sudo docker $action $node >/dev/null"
    trap - EXIT
    detection=$(echo "$(seconds "$declared") - $(seconds "$down")" | bc)
    rereplication=$( [[ -n $finished ]] && echo "$(seconds "$finished") - $(seconds "$declared")" | bc || echo "")
    echo "$version,$variant,$rep,$node,$down,$declared,$detection,$finished,$rereplication" >> "$times"
    echo "[$(date -u +%T)] $variant $rep: detección $detection s, re-replicación ${rereplication:-?} s" >&2
    sleep 40  # el nodo vuelve, se borran sus réplicas de más y el clúster se estabiliza
  done
done
