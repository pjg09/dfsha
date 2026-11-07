#!/usr/bin/env bash
# Acceso RF3 (§5.2): read() y write() con la semántica declarada en la fase I §7.
# Se ejecuta desde la raíz del repositorio con el clúster en marcha y el usuario pedro creado.
set -uo pipefail
cd "$(dirname "$0")/../.."
here=$(dirname "$0")
run=deploy/aws/run.sh
step() { printf '\n## %s\n' "$*"; }

step "Versión desplegada"
$run ssh client-1 "sudo docker ps --format '{{.Image}}' | sed 's/^.*amazonaws.com\//    /'"

step "Los cuatro modos de escritura y las garantías G2-G4 con la biblioteca (rf3.py, en client-1)"
# La contraseña entra por la entrada estándar del contenedor, seguida del script
$run ssh client-1 "sudo docker exec -i -e DFSHA_USERNAME=pedro client-1 sh -c \
  'read -r DFSHA_PASSWORD; export DFSHA_PASSWORD; script=\$(cat); exec python -c \"\$script\"'" \
  < <(cat deploy/aws/secrets/pedro-password; cat "$here/rf3.py")

step "Las mismas primitivas desde la línea de órdenes"
$run ssh client-1 "sudo docker exec client-1 sh -c 'printf \"hola mundo\" > /data/texto.txt'"
$run dfsha pedro put /data/texto.txt /texto.txt
echo '$ dfsha read /texto.txt 0 100'; $run dfsha pedro read /texto.txt 0 100; echo
echo '$ dfsha write /texto.txt 5 =MUNDO'; $run dfsha pedro write /texto.txt 5 =MUNDO
echo '$ dfsha append /texto.txt "= desde AWS"'; $run dfsha pedro append /texto.txt "= desde AWS"
echo '$ dfsha read /texto.txt 0 100'; $run dfsha pedro read /texto.txt 0 100; echo
echo '$ dfsha read /texto.txt 5 5'; $run dfsha pedro read /texto.txt 5 5; echo
echo '$ dfsha stat /texto.txt'; $run dfsha pedro stat /texto.txt
