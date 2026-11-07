#!/usr/bin/env bash
# Concurrencia (§5.2): escenario 1 de la fase I §11.1 con procesos reales en client-1.
# Se ejecuta desde la raíz del repositorio con el clúster en marcha y el usuario pedro creado.
set -uo pipefail
cd "$(dirname "$0")/../.."
here=$(dirname "$0")
run=deploy/aws/run.sh
B=16777216
BLOCK3=$((3 * B))
step() { printf '\n## %s\n' "$*"; }
in_client() {  # in_client <orden>: orden dentro del contenedor, con la contraseña de pedro por la entrada estándar
  $run ssh client-1 "sudo docker exec -i -e DFSHA_USERNAME=pedro client-1 sh -c \
    'read -r DFSHA_PASSWORD; export DFSHA_PASSWORD; $1'"
}
session() {  # session <nombre> <orden o "sleep N">...: un proceso dfsha shell con sus órdenes, cada una con su hora
  local name=$1; shift
  {
    cat deploy/aws/secrets/pedro-password
    for command in "$@"; do
      if [[ $command == sleep\ * ]]; then sleep "${command#sleep }"; continue; fi
      printf '[%s] %s envía: %s\n' "$(date -u +%T)" "$name" "$command" >&2
      echo "$command"
    done
  } | in_client "exec dfsha shell" 2>&1 | sed -e 's/dfsha:\/> //g' -e "/^DFSha. Órdenes/d" -e '/^$/d' -e "s/^/[$name] /"
}
show() { $run dfsha pedro read /datos.bin "$1" "$2"; echo; }

step "Versión desplegada"
$run ssh client-1 "sudo docker ps --format '{{.Image}}' | sed 's/^.*amazonaws.com\//    /'"

step "Preparación: /datos.bin con 4 bloques de 16 MiB"
$run ssh client-1 "sudo docker exec client-1 sh -c 'head -c $((4 * B)) /dev/urandom > /data/datos.bin'"
$run dfsha pedro rm /datos.bin >/dev/null 2>&1 || true
$run dfsha pedro put /data/datos.bin /datos.bin

step "A. P1 y P2 modifican el bloque 3 a la vez (pasos 1 a 4)"
session P1 "open /datos.bin w" "write $BLOCK3 =P1-cambia-el-bloque-3" "sleep 12" "close" > /tmp/dfsha-p1.log 2>&1 &
sleep 4
session P2 "open /datos.bin w" "write $BLOCK3 =P2-cambia-el-bloque-3" "sleep 12" \
  "write $BLOCK3 =P2-cambia-el-bloque-3" "close" \
  "open /datos.bin w" "read $BLOCK3 21" "write $((BLOCK3 + 21)) =+P2" "close" > /tmp/dfsha-p2.log 2>&1
wait
cat /tmp/dfsha-p1.log /tmp/dfsha-p2.log | sed 's/^/  /'
echo "Bloque 3 al final:"; show $BLOCK3 24

step "B. P1 y P2 modifican bloques distintos a la vez: los dos confirman"
session P1 "open /datos.bin w" "write 0 =P1-bloque-0" "sleep 8" "close" > /tmp/dfsha-p1.log 2>&1 &
sleep 3
session P2 "open /datos.bin w" "write $BLOCK3 =P2-bloque-3" "close" > /tmp/dfsha-p2.log 2>&1
wait
cat /tmp/dfsha-p1.log /tmp/dfsha-p2.log | sed 's/^/  /'
echo "Bloque 0:"; show 0 11
echo "Bloque 3:"; show $BLOCK3 11
$run dfsha pedro stat /datos.bin

step "C. P1 muere con el arrendamiento: kill -9 y P2 escribe cuando caduca (30 s como máximo)"
session P1 "open /datos.bin w" "write $BLOCK3 =P1-va-a-morir" "sleep 45" "close" > /tmp/dfsha-p1.log 2>&1 &
sleep 6
$run ssh client-1 "sudo pkill -9 -f 'bin/dfsh[a] shell' && echo \"[\$(date -u +%T)] kill -9 al proceso de P1\""
killed=$(date +%s)
attempt=0
until $run dfsha pedro write /datos.bin $BLOCK3 =P2-tras-la-muerte 2>&1 | sed "s/^/  [$(date -u +%T)] P2: /" | tee /tmp/dfsha-p2.log | grep -q "versión"; do
  cat /tmp/dfsha-p2.log; attempt=$((attempt + 1)); sleep 3
done
cat /tmp/dfsha-p2.log
echo "P2 escribe $(( $(date +%s) - killed )) s después de la muerte de P1, tras $attempt intentos rechazados"
wait 2>/dev/null
sed 's/^/  /' /tmp/dfsha-p1.log
echo "Bloque 3:"; show $BLOCK3 17

step "D. P1 reaparece después de que su arrendamiento caducara (reaparece.py, en client-1)"
in_client 'script=$(cat); exec python -c "$script"' < <(cat deploy/aws/secrets/pedro-password; cat "$here/reaparece.py")
echo "Bloque 3 (no cambia):"; show $BLOCK3 17
rm -f /tmp/dfsha-p1.log /tmp/dfsha-p2.log
