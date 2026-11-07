#!/usr/bin/env bash
# Seguridad (§5.2): acceso autorizado y denegado, TLS en el canal y bloques cifrados en disco.
# Se ejecuta desde la raíz del repositorio con el clúster en marcha y los usuarios admin y pedro creados.
set -uo pipefail
cd "$(dirname "$0")/../.."
here=$(dirname "$0")
run=deploy/aws/run.sh
datanodes=(datanode-1 datanode-2 datanode-3 datanode-4 datanode-5)
export AWS_DEFAULT_REGION=us-east-1
step() { printf '\n## %s\n' "$*"; }
client() { $run ssh client-1 "sudo docker exec client-1 sh -c '$1'"; }

step "Grupos de seguridad (Tabla 10): puertos del clúster solo entre grupos del proyecto; SSH solo desde la máquina de administración"
for group in metadata datanode client; do
  echo "dfsha-sg-$group:"
  aws ec2 describe-security-groups --filters "Name=group-name,Values=dfsha-sg-$group" --output json \
    --query 'SecurityGroups[0].IpPermissions[]' | python3 "$here/grupos.py"
done

step "Volúmenes EBS del proyecto: todos cifrados"
aws ec2 describe-volumes --filters Name=tag:project,Values=dfsha --output text \
  --query 'Volumes[].[Tags[?Key==`Name`]|[0].Value,Size,VolumeType,Encrypted]' | sort
echo "Discos raíz de las instancias:"
aws ec2 describe-volumes --filters Name=attachment.device,Values=/dev/sda1 --output text \
  --query 'Volumes[].Encrypted' | tr '\t' '\n' | sort | uniq -c

step "Secretos de cada host (solo nombres y permisos): los nodos de datos y el cliente no tienen la clave de envoltura"
for host in metadata-1 datanode-1 client-1; do
  echo "$host:"; $run ssh "$host" "sudo ls -l /srv/dfsha/secrets | tail -n +2 | awk '{print \"    \" \$1, \$3, \$NF}'"
done

step "TLS con el certificado de client-1 hacia metadata-1:50051"
$run ssh client-1 'sudo openssl s_client -connect metadata-1:50051 -servername metadata-1 -alpn h2 \
  -CAfile /srv/dfsha/secrets/ca.pem -cert /srv/dfsha/secrets/cert.pem -key /srv/dfsha/secrets/key.pem </dev/null 2>&1 |
  grep -E "^(subject|issuer|Protocol|ALPN protocol|Verify return code)|^New, "'

step "TLS sin certificado de cliente hacia metadata-1:50051: el servidor cierra la conexión"
$run ssh client-1 'sleep 2 | sudo openssl s_client -connect metadata-1:50051 -servername metadata-1 -alpn h2 \
  -CAfile /srv/dfsha/secrets/ca.pem 2>&1 | grep -iE "alert|error"'

step "Llamadas que tienen que rechazarse (sondas.py, desde client-1)"
block_id=$($run ssh datanode-1 "sudo find /srv/dfsha/data/blocks -type f ! -name '*.meta' | head -1 | xargs basename")
echo "réplica usada: $block_id"
$run ssh client-1 "sudo docker exec -i client-1 python - $block_id" < "$here/sondas.py"

step "Acceso autorizado: pedro ve su archivo"
$run dfsha pedro ls /

step "Aislamiento entre usuarios: admin no ve el archivo de pedro"
$run dfsha admin ls /; echo "(fin del listado de admin)"
$run dfsha admin get /grande.bin /data/robado.bin; echo "código de salida: $?"

step "Solo un administrador crea usuarios"
NEW_PASSWORD_FILE=deploy/aws/secrets/pedro-password $run dfsha pedro useradd intruso; echo "código de salida: $?"

step "Contraseña incorrecta y bloqueo tras 5 fallos seguidos (bloqueo.py, desde client-1, un solo proceso)"
# La contraseña viaja como argumento dentro del contenedor, nunca por la línea de órdenes de ssh ni en esta salida
$run ssh client-1 "sudo docker exec -i client-1 sh -c 'read -r password; script=\$(cat); exec python -c \"\$script\" pedro \"\$password\"'" \
  < <(cat deploy/aws/secrets/pedro-password; cat "$here/bloqueo.py")

step "Bloques cifrados en disco: una marca de texto que se carga no aparece en ninguna réplica"
$run dfsha pedro rm /marca.txt >/dev/null 2>&1 || true  # por si se repite la prueba
client 'python3 -c "import sys; sys.stdout.write(\"MARCA-DFSHA-EN-CLARO \" * 50000)" > /data/marca.txt; ls -l /data/marca.txt'
printf 'veces que aparece la marca en el archivo original: '; client 'grep -o MARCA-DFSHA-EN-CLARO /data/marca.txt | wc -l'
$run dfsha pedro put /data/marca.txt /marca.txt
for host in "${datanodes[@]}"; do
  printf '%s: %s réplicas; réplicas que contienen la marca: ' "$host" \
    "$($run ssh "$host" "sudo find /srv/dfsha/data/blocks -type f ! -name '*.meta' | wc -l")"
  $run ssh "$host" "sudo grep -rl --exclude='*.meta' MARCA-DFSHA-EN-CLARO /srv/dfsha/data/blocks | wc -l"
done
$run dfsha pedro get /marca.txt /data/marca-recuperada.txt
client 'sha256sum /data/marca.txt /data/marca-recuperada.txt'
