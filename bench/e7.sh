#!/usr/bin/env bash
# E7 (ADR 0046): caída del líder de metadatos. En cada repetición, una sonda en client-1 hace un mkdir cada
# 0,1 s durante 70 s; a los 15 s cae el servidor de metadatos líder junto con su miembro de etcd, y al terminar
# se recupera. Del registro del nuevo líder salen la hora de la elección y la del fin del modo seguro.
# VARIANT=parada: docker stop (SIGTERM: el líder renuncia antes de morir, un relevo ordenado).
# VARIANT=congelado: docker pause (el líder deja de renovar su clave sin renunciar, como una instancia colgada).
set -euo pipefail
cd "$(dirname "$0")/.."
run=deploy/aws/run.sh
REPS=${REPS:-5}
VARIANT=${VARIANT:-parada}
out=bench/resultados/$(date -u +%F)-e7-$VARIANT.csv
log=bench/resultados/$(date -u +%F)-e7-$VARIANT-lider.txt
if [[ $VARIANT == parada ]]; then down="stop --time 0" up=start; else down=pause up=unpause; fi
version=$($run ssh client-1 "sudo docker ps --format '{{.Image}}'" | sed 's/^.*://')
[[ -f $out ]] || echo "version,repeticion,hora_utc,latencia_ms,resultado,servidor" > "$out"
probe() {  # probe <modo> <argumentos>: e7.py en client-1, con la contraseña de pedro por la entrada estándar
  $run ssh client-1 "sudo docker exec -i -e DFSHA_USERNAME=pedro client-1 sh -c \
    'read -r DFSHA_PASSWORD; export DFSHA_PASSWORD; script=\$(cat); exec python -c \"\$script\" $*'" \
    < <(cat deploy/aws/secrets/pedro-password; cat bench/e7.py)
}
for rep in $(seq "${FIRST_REP:-1}" "$REPS"); do  # FIRST_REP: para completar una serie cortada
  leader=$(probe leader | cut -d: -f1)
  echo "[$(date -u +%T)] repetición $rep: líder $leader" >&2
  probe probe 70 "$rep" | sed "s/^/$version,/" >> "$out" &
  prober=$!
  sleep 15
  $run ssh "$leader" "sudo docker $down $leader etcd >/dev/null && echo \"[\$(date -u +%T.%3N)] repetición $rep: $leader y su etcd caídos ($VARIANT)\"" | tee -a "$log" >&2
  stopped=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  wait "$prober"
  for host in metadata-1 metadata-2 metadata-3; do
    [[ $host == "$leader" ]] && continue
    $run ssh "$host" "sudo docker logs --since $stopped $host 2>&1 | grep -E 'Elegido líder|modo seguro' | sed 's/^/  /'" | tee -a "$log" >&2
  done
  $run ssh "$leader" "sudo docker $up etcd $leader >/dev/null && echo \"[\$(date -u +%T)] $leader y su etcd recuperados\"" >&2
  sleep 30  # el miembro vuelve a etcd y los nodos de datos se estabilizan
done
