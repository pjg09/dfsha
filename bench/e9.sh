#!/usr/bin/env bash
# E9 (ADR 0046): arranque en frío. Se paran las 9 instancias con la API de EC2 y se vuelven a arrancar, como al
# terminar y empezar una sesión del Learner Lab. Se mide hasta que los contenedores vuelven solos y hasta el fin
# del modo seguro, si sale por la condición o por el tope, y cuántas re-replicaciones y borrados lanza el líder
# (deben ser 0). Al final se comprueba que los datos se leen.
set -euo pipefail
cd "$(dirname "$0")/.."
run=deploy/aws/run.sh
export AWS_DEFAULT_REGION=us-east-1
REPS=${REPS:-5}
out=bench/resultados/$(date -u +%F)-e9.csv
version=$($run ssh client-1 "sudo docker ps --format '{{.Image}}'" | sed 's/^.*://')
[[ -f $out ]] || echo "version,repeticion,hora_arranque_utc,instancias_en_marcha_s,contenedores_s,lider_elegido_s,fin_modo_seguro_s,salida_modo_seguro,ordenes_rereplicacion,borrados_de_mas,lectura_ok" > "$out"
seconds() { date -u -d "$1" +%s.%N; }
since() { echo "$(seconds "$1") - $(seconds "$started")" | bc; }
ids=$(aws ec2 describe-instances --filters Name=tag:project,Values=dfsha Name=instance-state-name,Values=running \
  --query 'Reservations[].Instances[].InstanceId' --output text)
# Si algo falla a mitad, las instancias no se quedan paradas
trap 'aws ec2 start-instances --instance-ids $ids >/dev/null 2>&1 || true' EXIT
for rep in $(seq 1 "$REPS"); do
  echo "[$(date -u +%T)] repetición $rep: parando las 9 instancias" >&2
  aws ec2 stop-instances --instance-ids $ids >/dev/null
  aws ec2 wait instance-stopped --instance-ids $ids
  started=$(date -u +%FT%T.%3NZ)
  aws ec2 start-instances --instance-ids $ids >/dev/null
  aws ec2 wait instance-running --instance-ids $ids
  running=$(date -u +%FT%T.%3NZ)
  echo "[$(date -u +%T)] instancias en marcha; esperando al fin del modo seguro" >&2
  log=""
  for _ in $(seq 1 60); do
    sleep 5
    log=$(for host in metadata-1 metadata-2 metadata-3; do $run ssh "$host" "sudo docker logs --since $started $host 2>&1" 2>/dev/null || true; done)
    grep -q "Fin del modo seguro" <<< "$log" && break
  done
  sleep 20  # margen para ver si el líder lanza re-replicaciones o borrados tras salir del modo seguro
  log=$(for host in metadata-1 metadata-2 metadata-3; do $run ssh "$host" "sudo docker logs --since $started $host 2>&1" || true; done)
  containers=$(for host in metadata-1 metadata-2 metadata-3 datanode-1 datanode-2 datanode-3 datanode-4 datanode-5 client-1; do
    $run ssh "$host" "sudo docker ps --format '{{.Names}}' | xargs -r sudo docker inspect -f '{{.State.StartedAt}}'" || true; done | sort | tail -1)
  # Con pipefail, un grep sin coincidencias terminaría el script con las instancias a medio arrancar
  elected=$( (grep "Elegido líder" <<< "$log" || true) | sort | tail -1 | cut -d' ' -f1)
  safe=$( (grep "Fin del modo seguro" <<< "$log" || true) | sort | tail -1)
  exit_reason=$(grep -q "por tiempo" <<< "$safe" && echo tope || echo condicion)
  orders=$(grep -c "Re-replicación del bloque" <<< "$log" || true)
  extra=$(grep -c "de más o corrupta" <<< "$log" || true)
  read_ok=$($run dfsha pedro get /bench/e6.bin /data/e9-copia.bin >/dev/null 2>&1 && echo si || echo no)
  $run ssh client-1 "sudo rm -f /srv/dfsha/client/e9-copia.bin"
  row="$version,$rep,$started,$(since "$running"),$(since "${containers%.*}Z"),$(since "$elected"),$(since "$(cut -d' ' -f1 <<< "$safe")"),$exit_reason,$orders,$extra,$read_ok"
  echo "$row" >> "$out"
  echo "[$(date -u +%T)] $row" >&2
done
