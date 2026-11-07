#!/usr/bin/env bash
# Carga y recuperación (§5.2): put y get de un archivo de 1 GiB en el clúster de AWS.
# Se ejecuta desde la raíz del repositorio con el clúster en marcha: evidencias/<este directorio>/ejecutar.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
run=deploy/aws/run.sh
datanodes=(datanode-1 datanode-2 datanode-3 datanode-4 datanode-5)
step() { printf '\n## %s\n' "$*"; }
client() { $run ssh client-1 "sudo docker exec client-1 sh -c '$1'"; }

step "Versión desplegada"
for host in metadata-1 datanode-1 client-1; do
  $run ssh "$host" "sudo docker ps --format '{{.Names}} {{.Image}}' | grep -v etcd | sed 's/^.*amazonaws.com\//    /'"
done

step "Réplicas en cada nodo de datos antes de la carga"
for host in "${datanodes[@]}"; do
  printf '%s: ' "$host"; $run ssh "$host" "sudo find /srv/dfsha/data/blocks -type f ! -name '*.meta' 2>/dev/null | wc -l"
done

step "Archivo de 1 GiB con contenido aleatorio en client-1"
client 'rm -f /data/grande.bin /data/recuperado.bin; head -c 1073741824 /dev/urandom > /data/grande.bin; ls -l /data/grande.bin'
client 'sha256sum /data/grande.bin'

step "put /data/grande.bin /grande.bin"
start=$(date +%s.%N); $run dfsha pedro put /data/grande.bin /grande.bin; end=$(date +%s.%N)
python3 -c "import sys; t=float(sys.argv[2])-float(sys.argv[1]); print(f'tiempo: {t:.1f} s ({1073741824/t/1e6:.0f} MB/s)')" "$start" "$end"

step "stat /grande.bin y ls /"
$run dfsha pedro stat /grande.bin
$run dfsha pedro ls /

step "Réplicas en cada nodo de datos después de la carga (64 bloques x 3 réplicas = 192)"
total=0
for host in "${datanodes[@]}"; do
  line=$($run ssh "$host" "n=\$(sudo find /srv/dfsha/data/blocks -type f ! -name '*.meta' | wc -l); \
    b=\$(sudo find /srv/dfsha/data/blocks -type f ! -name '*.meta' -printf '%s\n' | awk '{s+=\$1} END {print s+0}'); echo \$n \$b")
  printf '%s: %s réplicas, %s bytes\n' "$host" ${line}
  total=$((total + ${line%% *}))
done
echo "total: $total réplicas"

step "Tamaño de una réplica en disco (16 MiB + 28 bytes de nonce y etiqueta de AES-GCM)"
$run ssh datanode-1 "sudo find /srv/dfsha/data/blocks -type f ! -name '*.meta' -printf '%s\n' | sort | uniq -c"

step "get /grande.bin /data/recuperado.bin"
start=$(date +%s.%N); $run dfsha pedro get /grande.bin /data/recuperado.bin; end=$(date +%s.%N)
python3 -c "import sys; t=float(sys.argv[2])-float(sys.argv[1]); print(f'tiempo: {t:.1f} s ({1073741824/t/1e6:.0f} MB/s)')" "$start" "$end"

step "Comparación de hashes"
client 'sha256sum /data/grande.bin /data/recuperado.bin'
client 'cmp /data/grande.bin /data/recuperado.bin && echo "cmp: idénticos"'

step "Pico de memoria (VmHWM) del proceso de cada nodo de datos desde que arrancó"
for host in "${datanodes[@]}"; do
  printf '%s: ' "$host"
  $run ssh "$host" "pid=\$(pgrep -xf 'python -m dfsha.datanode'); grep VmHWM /proc/\$pid/status | tr -s ' '; free -m | awk '/Mem:/ {print \"    memoria disponible del host: \" \$7 \" MiB\"}'"
done

