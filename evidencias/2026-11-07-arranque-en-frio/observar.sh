#!/usr/bin/env bash
# Arranque en frío (§9.6): cómo se levantó solo el clúster cuando el Learner Lab arrancó las instancias.
# Solo observa: no reinicia ni cambia nada. Se ejecuta desde la raíz del repositorio.
set -uo pipefail
cd "$(dirname "$0")/../.."
run=deploy/aws/run.sh
export AWS_DEFAULT_REGION=us-east-1
step() { printf '\n## %s\n' "$*"; }

step "Arranque de las instancias (lo hace el Learner Lab al empezar la sesión)"
aws ec2 describe-instances --filters Name=tag:project,Values=dfsha --output text \
  --query 'Reservations[].Instances[].[Tags[?Key==`Name`]|[0].Value,State.Name,LaunchTime]' | sort
echo "ahora: $(date -u +%FT%T)"

step "Cada host: arranque del sistema, volumen montado y contenedores (hora de arranque y reinicios)"
for host in metadata-1 metadata-2 metadata-3 datanode-1 datanode-2 datanode-3 datanode-4 datanode-5 client-1; do
  echo "$host:"
  $run ssh "$host" "echo \"  sistema en marcha desde: \$(uptime -s)\"; findmnt -no SOURCE,TARGET /srv/dfsha/data 2>/dev/null | sed 's/^/  volumen: /'; \
    sudo docker ps -a --format '{{.Names}}' | while read -r c; do sudo docker inspect -f \"  {{.Name}} {{.Config.Image}} {{.State.Status}} desde {{.State.StartedAt}} reinicios={{.RestartCount}}\" \$c; done | sed 's|/||; s| [^ ]*amazonaws.com/| |'"
done

step "Elección del líder y alta de los nodos de datos tras el arranque"
for host in metadata-1 metadata-2 metadata-3; do
  $run ssh "$host" "sudo docker logs --since 2026-11-07T16:50:00Z $host 2>&1 | grep -E 'escuchando|Elegido|Primer|nodos de datos registrados' | head -4"
done
for host in datanode-1 datanode-2 datanode-3 datanode-4 datanode-5; do
  $run ssh "$host" "sudo docker logs --since 2026-11-07T16:50:00Z $host 2>&1 | grep -E 'Dado de alta|Informe de bloques' | head -2"
done

step "Los datos sobreviven a la parada: archivos, réplicas y hash"
$run dfsha pedro ls /
$run ssh client-1 "df -h / | tail -1"
$run dfsha pedro get /grande.bin /data/grande-tras-arranque.bin
$run ssh client-1 "sudo docker exec client-1 sha256sum /data/grande.bin /data/grande-tras-arranque.bin; sudo rm -f /srv/dfsha/client/grande-tras-arranque.bin"
echo '$ dfsha read /texto.txt 0 100'; $run dfsha pedro read /texto.txt 0 100; echo
