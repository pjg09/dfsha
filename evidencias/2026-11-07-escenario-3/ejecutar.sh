#!/usr/bin/env bash
# Escenario 3 (fase I §11.3): un nodo de datos falla después de recibir parte de un bloque. Se ejecuta desde
# la raíz del repositorio con el clúster en marcha y el usuario pedro creado.
set -uo pipefail
cd "$(dirname "$0")/../.."
run=deploy/aws/run.sh
VICTIM=datanode-4
tmp=$(mktemp -d)
step() { printf '\n## %s\n' "$*"; }
now() { date -u +%T; }

step "Versión desplegada y preparación ($(now))"
$run ssh client-1 "sudo docker ps --format '{{.Image}}' | sed 's/^.*amazonaws.com\//    /'; df -h / | tail -1"
$run ssh client-1 "sudo docker exec client-1 sh -c 'head -c 1073741824 /dev/urandom > /data/escenario-3.bin && sha256sum /data/escenario-3.bin'"
$run dfsha pedro rm /escenario-3.bin >/dev/null 2>&1 || true

step "Carga de 1 GiB; a los 3 s cae $VICTIM mientras recibe bloques"
since=$(date -u +%Y-%m-%dT%H:%M:%SZ)
# Otro proceso pregunta por el archivo cada segundo mientras dura la carga (G4: nunca se ve a medias)
# Cada consulta tarda unos 3 s (SSH, contenedor y autenticación): se anotan la hora de inicio y la de respuesta
( for _ in $(seq 1 12); do
    asked=$(now); answer=$($run dfsha pedro stat /escenario-3.bin 2>&1 | head -2 | tr '\n' ' ')
    printf '[%s → %s] observador: %s\n' "$asked" "$(now)" "$answer"
  done ) > "$tmp/observer.log" 2>&1 &
observer=$!
$run dfsha pedro -v put /data/escenario-3.bin /escenario-3.bin > "$tmp/put.log" 2>&1 &
put=$!
sleep 3
$run ssh "$VICTIM" "sudo docker stop --time 0 $VICTIM >/dev/null && echo \"[\$(date -u +%T)] $VICTIM parado\""
wait "$put"; echo "la carga termina (el cliente recibe la confirmación) a las $(now)"
sed -E 's/^([^ ]+) [A-Z]+ client [^:]+: /[\1] cliente: /' "$tmp/put.log" | cut -c1-200
wait "$observer"
step "Lo que vio el otro proceso durante la carga"
cat "$tmp/observer.log" | cut -c1-160

step "Área temporal de $VICTIM mientras está caído: lo recibido a medias, sin renombrar"
$run ssh "$VICTIM" "sudo ls -la /srv/dfsha/data/staging | tail -n +4 | awk '{print \"  \" \$5, \$9}'"

step "Recuperación: el archivo cargado es idéntico"
$run dfsha pedro get /escenario-3.bin /data/escenario-3-copia.bin
$run ssh client-1 "sudo docker exec client-1 sha256sum /data/escenario-3.bin /data/escenario-3-copia.bin; sudo rm -f /srv/dfsha/client/escenario-3-copia.bin /srv/dfsha/client/escenario-3.bin"

step "$VICTIM vuelve ($(now)): descarta su área temporal al arrancar"
$run ssh "$VICTIM" "sudo docker start $VICTIM >/dev/null && echo \"[\$(date -u +%T)] $VICTIM arrancado\""
sleep 15
$run ssh "$VICTIM" "sudo docker logs --since $since $VICTIM 2>&1 | grep -E 'área temporal|Dado de alta|Informe de bloques|borrado por orden' | sed -E 's/^([^ ]+) INFO ([^ ]+) [^:]+: /[\1] \2: /' | head -8"
$run ssh "$VICTIM" "echo \"  archivos en el área temporal: \$(sudo ls /srv/dfsha/data/staging | wc -l)\""
rm -rf "$tmp"
