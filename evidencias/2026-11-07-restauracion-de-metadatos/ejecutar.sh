#!/usr/bin/env bash
# Restauración de los metadatos desde la copia de S3 (ADR 0035, fase I §4.2 y fila de L11 de la §11.3).
# Se ejecuta desde la raíz del repositorio con el clúster en marcha y pedro con /grande.bin cargado.
set -uo pipefail
cd "$(dirname "$0")/../.."
run=deploy/aws/run.sh
step() { printf '\n## %s\n' "$*"; }
leader_logs() {
  for host in metadata-1 metadata-2 metadata-3; do
    $run ssh "$host" "sudo docker logs --since $1 $host 2>&1 | grep -E 'Elegido líder|Primer administrador'" || true
  done
}

step "Estado antes de la copia"
$run dfsha pedro ls /
leader_logs 24h

step "Copia de seguridad en S3"
deploy/aws/deploy.sh backup 2>&1
snapshot=$(aws s3 ls "s3://dfsha-copias-$(aws sts get-caller-identity --query Account --output text | tail -c 7)/" \
  | awk '{print $4}' | sort | tail -1)
echo "copia usada: $snapshot"

step "Archivo creado después de la copia: se perderá al restaurar (L11)"
$run ssh client-1 "sudo docker exec client-1 sh -c 'echo creado después de la copia > /data/despues.txt'"
$run dfsha pedro put /data/despues.txt /despues-de-la-copia.txt
$run dfsha pedro ls /

step "Pérdida de los datos de etcd de los tres servidores de metadatos y restauración"
echo "inicio: $(date -u +%T)"
since=$(date -u +%Y-%m-%dT%H:%M:%SZ)
deploy/aws/deploy.sh restore "$snapshot" 2>&1
echo "fin de la restauración: $(date -u +%T)"
$run ssh metadata-1 "sudo ls /srv/dfsha/data | sed 's/^/    /'"

step "Elección tras la restauración: la época es mayor que 10^9 por --bump-revision"
sleep 20
leader_logs "$since"

step "Los nodos de datos aceptan al nuevo líder"
for host in datanode-1 datanode-2 datanode-3 datanode-4 datanode-5; do
  printf '%s: ' "$host"
  $run ssh "$host" "sudo docker logs --since $since $host 2>&1 | grep -E 'Informe de bloques|Dado de alta|Error del líder' | tail -2 | cut -c1-160"
done

step "Estado después de la restauración"
$run dfsha pedro ls /
$run dfsha pedro get /grande.bin /data/restaurado.bin
$run ssh client-1 "sudo docker exec client-1 sha256sum /data/grande.bin /data/restaurado.bin"
