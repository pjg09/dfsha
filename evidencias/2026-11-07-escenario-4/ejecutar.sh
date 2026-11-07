#!/usr/bin/env bash
# Escenario 4 (fase I §11.4): el cliente desconoce la ubicación física de los bloques.
# Se ejecuta desde la raíz del repositorio con el clúster en marcha y el usuario pedro creado.
set -uo pipefail
cd "$(dirname "$0")/../.."
here=$(dirname "$0")
run=deploy/aws/run.sh
step() { printf '\n## %s\n' "$*"; }

step "Versión desplegada y configuración del cliente: solo los servidores de metadatos"
$run ssh client-1 "sudo docker ps --format '{{.Image}}' | sed 's/^.*amazonaws.com\//    /'"
$run ssh client-1 "sudo docker exec client-1 env | grep '^DFSHA_' | sort"
grep -n "DFSHA_METADATA_ADDRS\|metadata_addrs=" deploy/aws/deploy.sh | head -3

step "Descubrimiento (descubrimiento.py, en client-1)"
# Los servidores de metadatos en orden inverso: el primero que pregunta puede no ser el líder
$run ssh client-1 "sudo docker exec -i -e DFSHA_USERNAME=pedro \
  -e DFSHA_METADATA_ADDRS=metadata-3:50051,metadata-2:50051,metadata-1:50051 client-1 sh -c \
  'read -r DFSHA_PASSWORD; export DFSHA_PASSWORD; script=\$(cat); exec python -c \"\$script\"'" \
  < <(cat deploy/aws/secrets/pedro-password; cat "$here/descubrimiento.py")

step "4. El nombre se resuelve con /etc/hosts, que genera deploy.sh con las IP privadas"
$run ssh client-1 "sed -n '/# dfsha-inicio/,/# dfsha-fin/p' /etc/hosts; echo; sudo docker exec client-1 getent hosts datanode-2"
