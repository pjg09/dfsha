#!/usr/bin/env bash
# Escenario 2 (fase I §11.2): una réplica está desconectada durante una escritura. Se ejecuta desde la raíz
# del repositorio con el clúster en marcha y el usuario pedro creado.
set -uo pipefail
cd "$(dirname "$0")/../.."
here=$(dirname "$0")
run=deploy/aws/run.sh
OFF=datanode-5
step() { printf '\n## %s\n' "$*"; }
now() { date -u +%T; }
locations() {
  $run ssh client-1 "sudo docker exec -i -e DFSHA_USERNAME=pedro client-1 sh -c \
    'read -r DFSHA_PASSWORD; export DFSHA_PASSWORD; script=\$(cat); exec python -c \"\$script\" /escenario-2.bin'" \
    < <(cat deploy/aws/secrets/pedro-password; cat "$here/ubicaciones.py")
}

step "Versión desplegada y preparación ($(now))"
$run ssh client-1 "sudo docker ps --format '{{.Image}}' | sed 's/^.*amazonaws.com\//    /'"
$run ssh client-1 "sudo docker exec client-1 sh -c 'head -c 134217728 /dev/urandom > /data/escenario-2.bin && sha256sum /data/escenario-2.bin'"

step "$OFF se desconecta justo antes de la escritura: el líder aún lo cuenta como vivo (9 s sin latido)"
$run ssh "$OFF" "sudo docker stop --time 0 $OFF >/dev/null && echo \"[\$(date -u +%T)] $OFF parado\""
since=$(date -u +%Y-%m-%dT%H:%M:%SZ)
$run dfsha pedro -v put /data/escenario-2.bin /escenario-2.bin 2>&1 | sed -E 's/^([^ ]+) [A-Z]+ client [^:]+: /[\1] cliente: /'

step "Las primarias reenviaron a $OFF y no pudo guardar: siguieron con W = 2"
for host in datanode-1 datanode-2 datanode-3 datanode-4; do
  $run ssh "$host" "sudo docker logs --since $since $host 2>&1 | grep 'no guardó' | sed -E 's/^([^ ]+) WARNING ([^ ]+) [^:]+: /[\1] \2: /' | cut -c1-150"
done

step "Ubicaciones de la versión nueva ($(now)): solo las réplicas que avisaron, nunca $OFF"
locations

step "Lectura de la versión nueva (G2)"
$run dfsha pedro get /escenario-2.bin /data/escenario-2-copia.bin
$run ssh client-1 "sudo docker exec client-1 sha256sum /data/escenario-2.bin /data/escenario-2-copia.bin; sudo rm -f /srv/dfsha/client/escenario-2-copia.bin"

step "A los 30 s, $OFF se declara caído y los bloques con 2 réplicas se re-replican"
sleep 45
locations

step "$OFF vuelve ($(now)): no tiene nada de la versión nueva"
$run ssh "$OFF" "sudo docker start $OFF >/dev/null && echo \"[\$(date -u +%T)] $OFF arrancado\""
sleep 25
$run ssh "$OFF" "sudo docker logs --since $since $OFF 2>&1 | grep -E 'Dado de alta|Informe de bloques|área temporal' | sed -E 's/^([^ ]+) INFO ([^ ]+) [^:]+: /[\1] \2: /'"
locations
$run ssh client-1 "sudo rm -f /srv/dfsha/client/escenario-2.bin"
