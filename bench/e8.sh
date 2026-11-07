#!/usr/bin/env bash
# E8 por componentes (ADR 0046): AES-256-GCM y SHA-256 en la CPU de client-1, y una transferencia gRPC con TLS
# mutuo y sin TLS entre client-1 y datanode-2, fuera de DFSha. El servidor de prueba escucha en el puerto
# 50099 de datanode-2, que solo se abre a dfsha-sg-client mientras dura el experimento: la regla se revoca al
# salir, también si algo falla.
set -euo pipefail
cd "$(dirname "$0")/.."
run=deploy/aws/run.sh
export AWS_DEFAULT_REGION=us-east-1
PORT=50099 SERVER=datanode-2 SIZE_MIB=256 REPS=5
out=bench/resultados/$(date -u +%F)-e8.csv
group() { aws ec2 describe-security-groups --filters "Name=group-name,Values=$1" --query 'SecurityGroups[0].GroupId' --output text; }
datanode_group=$(group dfsha-sg-datanode) client_group=$(group dfsha-sg-client)
rule="IpProtocol=tcp,FromPort=$PORT,ToPort=$PORT,UserIdGroupPairs=[{GroupId=$client_group}]"
stop_server() { $run ssh "$SERVER" "sudo docker rm -f e8-servidor >/dev/null 2>&1 || true"; }
cleanup() {
  stop_server
  aws ec2 revoke-security-group-ingress --group-id "$datanode_group" --ip-permissions "$rule" >/dev/null 2>&1 &&
    echo "[$(date -u +%T)] regla temporal del puerto $PORT revocada" >&2
}
trap cleanup EXIT

client_id=$(aws ec2 describe-instances --filters Name=tag:Name,Values=dfsha-client-1 Name=instance-state-name,Values=running \
  --query 'Reservations[0].Instances[0].InstanceId' --output text)
instance_type=$(aws ec2 describe-instances --instance-ids "$client_id" --query 'Reservations[0].Instances[0].InstanceType' --output text)
credits=$(aws ec2 describe-instance-credit-specifications --instance-ids "$client_id" --query 'InstanceCreditSpecifications[0].CpuCredits' --output text)
version=$($run ssh client-1 "sudo docker ps --format '{{.Image}}'" | sed 's/^.*://')
prefix="$(date -u +%FT%TZ),e8,$version,$instance_type,$credits"
[[ -f $out ]] || echo "fecha_utc,experimento,version,cliente,creditos_cpu,condicion,repeticion,operacion,tamano_mib,latencia_ms,tasa_mb_s,hash_ok" > "$out"
in_client() { $run ssh client-1 "sudo docker exec -i client-1 sh -c 'script=\$(cat); exec python -c \"\$script\" $*'" < bench/e8.py; }

echo "[$(date -u +%T)] cifrado y hash en la CPU de client-1 ($instance_type)" >&2
in_client crypto cpu-client-1 $REPS | sed "s/^/$prefix,/" >> "$out"

aws ec2 authorize-security-group-ingress --group-id "$datanode_group" --ip-permissions "$rule" >/dev/null
echo "[$(date -u +%T)] regla temporal: $PORT/tcp de dfsha-sg-client a dfsha-sg-datanode" >&2
image=$($run ssh "$SERVER" "sudo docker inspect -f '{{.Config.Image}}' $SERVER")
for security in tls plain; do
  stop_server
  $run ssh "$SERVER" "cat > /tmp/e8.py && sudo docker run -d --rm --name e8-servidor --network host \
    -v /srv/dfsha/secrets:/run/secrets/dfsha:ro -v /tmp/e8.py:/e8.py:ro --entrypoint python $image /e8.py server $PORT $security >/dev/null" < bench/e8.py
  sleep 5
  echo "[$(date -u +%T)] transferencia gRPC $security, $SIZE_MIB MiB" >&2
  in_client client "$SERVER:$PORT" $security grpc-client-1-a-$SERVER $SIZE_MIB $REPS | sed "s/^/$prefix,/" >> "$out"
done
