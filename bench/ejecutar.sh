#!/usr/bin/env bash
# Lanza un experimento en client-1 y guarda sus mediciones en bench/resultados/AAAA-MM-DD-<experimento>.csv
# (ADR 0028). Uso: bench/ejecutar.sh <experimento> <orden de dfsha_bench.py> [opciones...]
#   bench/ejecutar.sh e1 transfer --condition base --sizes 16,256,1024 --reps 5
# Cada fila lleva la fecha, la versión, el tipo de instancia del cliente y su modo de créditos de CPU (§12.3).
set -euo pipefail
cd "$(dirname "$0")/.."
experiment=$1; shift
run=deploy/aws/run.sh
export AWS_DEFAULT_REGION=us-east-1
out=bench/resultados/$(date -u +%F)-$experiment.csv
client_id=$(aws ec2 describe-instances --filters Name=tag:Name,Values=dfsha-client-1 Name=instance-state-name,Values=running \
  --query 'Reservations[0].Instances[0].InstanceId' --output text)
instance_type=$(aws ec2 describe-instances --instance-ids "$client_id" --query 'Reservations[0].Instances[0].InstanceType' --output text)
credits=$(aws ec2 describe-instance-credit-specifications --instance-ids "$client_id" --query 'InstanceCreditSpecifications[0].CpuCredits' --output text)
version=$($run ssh client-1 "sudo docker ps --format '{{.Image}}'" | sed 's/^.*://')
now=$(date -u +%FT%TZ)
last_column=hash_ok
[[ $1 == concurrent ]] && last_column=conflictos  # en E4, la última columna cuenta conflictos
[[ -f $out ]] || echo "fecha_utc,experimento,version,cliente,creditos_cpu,condicion,repeticion,operacion,tamano_mib,latencia_ms,tasa_mb_s,$last_column" > "$out"
echo "$experiment: versión $version, client-1 $instance_type ($credits), resultados en $out" >&2
$run ssh client-1 "sudo docker exec -i -e DFSHA_USERNAME=pedro client-1 sh -c \
  'read -r DFSHA_PASSWORD; export DFSHA_PASSWORD; script=\$(cat); exec python -c \"\$script\" $(printf '%q ' "$@")'" \
  < <(cat deploy/aws/secrets/pedro-password; cat bench/dfsha_bench.py) |
  sed "s/^/$now,$experiment,$version,$instance_type,$credits,/" >> "$out"
