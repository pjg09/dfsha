#!/usr/bin/env bash
# Despliegue de DFSha en el AWS Academy Learner Lab (fase I §3.6; ADR 0026, 0035, 0037, 0040 y 0043).
#
# Uso: deploy/aws/deploy.sh <orden>
#   images   construye las imágenes de la versión actual y las envía a ECR (etiquetas inmutables)
#   up       crea los grupos de seguridad, los volúmenes EBS y las 9 instancias (o arranca las paradas)
#   install  configura cada instancia (o solo los hosts indicados) por SSH y arranca sus contenedores; con
#            DFSHA_EXTRA_ENV="DFSHA_WRITE_QUORUM=3 ..." añade esas variables a todos los contenedores
#   status   estado de las instancias y de los contenedores
#   backup   guarda en S3 una instantánea de etcd (copia de seguridad de los metadatos, ADR 0035)
#   restore  restaura en los tres servidores de metadatos una instantánea de S3 (la última o la indicada)
#   all      images, up e install: levanta el clúster desde cero con una sola orden
#   down     termina las instancias y borra volúmenes y grupos de seguridad (las imágenes de ECR se quedan)
#
# Requisitos: credenciales de la sesión del lab en ~/.aws, ~/.ssh/labsuser.pem, Docker y uv, y los secretos
# en deploy/aws/secrets (uv run python -m dfsha.common.pki deploy/aws/secrets <hosts>). Ninguna IP se escribe
# en el repositorio: se consultan a AWS en cada ejecución (RNF7).
set -euo pipefail
cd "$(dirname "$0")/../.."

REGION=us-east-1
ZONE=us-east-1a
KEY_NAME=vockey
SSH_KEY="$HOME/.ssh/labsuser.pem"
SECRETS=deploy/aws/secrets
ETCD_IMAGE="gcr.io/etcd-development/etcd:v3.7.3@sha256:0d27b9478551f431f82d1e0ddb6c87ad07ebae8b904c637f3a99213349523910"
AMI_PARAMETER=/aws/service/canonical/ubuntu/server/26.04/stable/current/amd64/hvm/ebs-gp3/ami-id
METADATA_HOSTS=(metadata-1 metadata-2 metadata-3)
DATANODE_HOSTS=(datanode-1 datanode-2 datanode-3 datanode-4 datanode-5)
CLIENT_HOSTS=(client-1)
ALL_HOSTS=("${METADATA_HOSTS[@]}" "${DATANODE_HOSTS[@]}" "${CLIENT_HOSTS[@]}")
MAX_INSTANCES=9  # tope del Learner Lab: las que pasan de 9 se terminan (§3.6)
SSH_OPTIONS=(-i "$SSH_KEY" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 -o BatchMode=yes)
export AWS_DEFAULT_REGION=$REGION

log() { printf '[%s] %s\n' "$(date -u +%H:%M:%S)" "$*" >&2; }
role_of() { echo "${1%-*}"; }
instance_type() { [[ $(role_of "$1") == metadata ]] && echo t3.small || echo t3.micro; }
volume_size() { case $(role_of "$1") in metadata) echo 4 ;; datanode) echo 10 ;; *) echo 0 ;; esac; }
version_tag() { scripts/get-version.sh --image; }
registry() { echo "$(aws sts get-caller-identity --query Account --output text).dkr.ecr.$REGION.amazonaws.com"; }

instance_id() {
  aws ec2 describe-instances \
    --filters "Name=tag:Name,Values=dfsha-$1" "Name=instance-state-name,Values=pending,running,stopping,stopped" \
    --query 'Reservations[].Instances[].InstanceId' --output text
}
instance_field() {  # instance_field <host> <campo de la consulta JMESPath>
  aws ec2 describe-instances --instance-ids "$(instance_id "$1")" --query "Reservations[0].Instances[0].$2" --output text
}

# ----- images ------------------------------------------------------------------------------------
cmd_images() {
  local tag version reg
  tag=$(version_tag); version=$(scripts/get-version.sh); reg=$(registry)
  aws ecr get-login-password | docker login --username AWS --password-stdin "$reg" >/dev/null
  for role in metadata datanode client; do
    aws ecr describe-repositories --repository-names "dfsha-$role" >/dev/null 2>&1 ||
      aws ecr create-repository --repository-name "dfsha-$role" --image-tag-mutability IMMUTABLE \
        --tags Key=project,Value=dfsha >/dev/null
    if aws ecr describe-images --repository-name "dfsha-$role" --image-ids "imageTag=$tag" >/dev/null 2>&1; then
      log "dfsha-$role:$tag ya está en ECR"
      continue
    fi
    log "Construyendo dfsha-$role:$tag"
    docker build -q --target "$role" --build-arg "DFSHA_VERSION=$version" -t "$reg/dfsha-$role:$tag" . >/dev/null
    docker push -q "$reg/dfsha-$role:$tag" >/dev/null
    log "dfsha-$role:$tag enviada a ECR"
  done
}

# ----- up ----------------------------------------------------------------------------------------
security_group_id() {
  aws ec2 describe-security-groups --filters "Name=group-name,Values=$1" --query 'SecurityGroups[0].GroupId' --output text
}
ensure_security_groups() {
  local vpc admin_ip
  vpc=$(aws ec2 describe-vpcs --filters Name=isDefault,Values=true --query 'Vpcs[0].VpcId' --output text)
  admin_ip=$(curl -s https://checkip.amazonaws.com)
  for role in metadata datanode client; do
    [[ $(security_group_id "dfsha-sg-$role") != None ]] && continue
    aws ec2 create-security-group --group-name "dfsha-sg-$role" --description "DFSha $role" --vpc-id "$vpc" \
      --tag-specifications "ResourceType=security-group,Tags=[{Key=project,Value=dfsha}]" >/dev/null
    log "Grupo de seguridad dfsha-sg-$role creado"
  done
  local metadata datanode client
  metadata=$(security_group_id dfsha-sg-metadata); datanode=$(security_group_id dfsha-sg-datanode)
  client=$(security_group_id dfsha-sg-client)
  allow() {  # allow <grupo> <puerto o rango> <origen: grupo o CIDR>
    local from=${2%-*} to=${2#*-} source
    if [[ $3 == sg-* ]]; then source="UserIdGroupPairs=[{GroupId=$3}]"; else source="IpRanges=[{CidrIp=$3}]"; fi
    aws ec2 authorize-security-group-ingress --group-id "$1" \
      --ip-permissions "IpProtocol=tcp,FromPort=$from,ToPort=$to,$source" >/dev/null 2>&1 || true
  }
  # Tabla 10 de la fase I: los puertos del clúster solo entre los grupos del proyecto; SSH solo desde quien administra
  allow "$metadata" 50051-50051 "$client"; allow "$metadata" 50051-50051 "$datanode"
  allow "$metadata" 2379-2380 "$metadata"
  allow "$datanode" 50052-50052 "$client"; allow "$datanode" 50052-50052 "$datanode"
  for group in "$metadata" "$datanode" "$client"; do allow "$group" 22-22 "$admin_ip/32"; done
}

cmd_up() {
  ensure_security_groups
  local ami subnet running missing=()
  for host in "${ALL_HOSTS[@]}"; do [[ -z $(instance_id "$host") ]] && missing+=("$host"); done
  running=$(aws ec2 describe-instances --filters Name=instance-state-name,Values=pending,running \
    --query 'length(Reservations[].Instances[])' --output text)
  if (( running + ${#missing[@]} > MAX_INSTANCES )); then
    log "ERROR: hay $running instancias en marcha y faltan ${#missing[@]}: se pasaría del tope de $MAX_INSTANCES"
    exit 1
  fi
  ami=$(aws ssm get-parameter --name "$AMI_PARAMETER" --query Parameter.Value --output text)
  subnet=$(aws ec2 describe-subnets --filters Name=default-for-az,Values=true "Name=availability-zone,Values=$ZONE" \
    --query 'Subnets[0].SubnetId' --output text)
  for host in "${missing[@]}"; do
    local group id
    group=$(security_group_id "dfsha-sg-$(role_of "$host")")
    id=$(aws ec2 run-instances --image-id "$ami" --instance-type "$(instance_type "$host")" --key-name "$KEY_NAME" \
      --subnet-id "$subnet" --security-group-ids "$group" --iam-instance-profile Name=LabInstanceProfile \
      --metadata-options HttpTokens=required \
      --block-device-mappings 'DeviceName=/dev/sda1,Ebs={VolumeSize=8,VolumeType=gp3,Encrypted=true,DeleteOnTermination=true}' \
      --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=dfsha-$host},{Key=project,Value=dfsha}]" \
      --query 'Instances[0].InstanceId' --output text)
    log "Instancia dfsha-$host: $id"
  done
  local stopped
  stopped=$(aws ec2 describe-instances --filters Name=tag:project,Values=dfsha Name=instance-state-name,Values=stopped \
    --query 'Reservations[].Instances[].InstanceId' --output text)
  [[ -n $stopped ]] && aws ec2 start-instances --instance-ids $stopped >/dev/null && log "Arrancadas: $stopped"
  for host in "${ALL_HOSTS[@]}"; do aws ec2 wait instance-running --instance-ids "$(instance_id "$host")"; done
  for host in "${METADATA_HOSTS[@]}" "${DATANODE_HOSTS[@]}"; do ensure_volume "$host"; done
  log "Instancias en marcha"
}

ensure_volume() {  # volumen EBS de datos, cifrado con aws/ebs (ADR 0026 y 0035)
  local host=$1 volume
  volume=$(aws ec2 describe-volumes --filters "Name=tag:Name,Values=dfsha-$host-data" --query 'Volumes[0].VolumeId' --output text)
  if [[ $volume == None ]]; then
    volume=$(aws ec2 create-volume --availability-zone "$ZONE" --size "$(volume_size "$host")" --volume-type gp3 \
      --encrypted --tag-specifications "ResourceType=volume,Tags=[{Key=Name,Value=dfsha-$host-data},{Key=project,Value=dfsha}]" \
      --query VolumeId --output text)
    aws ec2 wait volume-available --volume-ids "$volume"
    log "Volumen dfsha-$host-data: $volume"
  fi
  local attached
  attached=$(aws ec2 describe-volumes --volume-ids "$volume" --query 'Volumes[0].Attachments[0].InstanceId' --output text)
  if [[ $attached == None ]]; then
    aws ec2 attach-volume --volume-id "$volume" --instance-id "$(instance_id "$host")" --device /dev/sdf >/dev/null
    aws ec2 wait volume-in-use --volume-ids "$volume"
  fi
}

# ----- install -----------------------------------------------------------------------------------
hosts_file() {
  local each  # sin local, el bucle pisaría la variable host de quien llama
  for each in "${ALL_HOSTS[@]}"; do printf '%s %s\n' "$(instance_field "$each" PrivateIpAddress)" "$each"; done
}

extra_env() {  # pares CLAVE=valor de DFSHA_EXTRA_ENV (experimentos de la etapa 10), como entradas de environment
  local pair
  for pair in ${DFSHA_EXTRA_ENV:-}; do printf ', %s: "%s"' "${pair%%=*}" "${pair#*=}"; done
}

compose_for() {  # compose.yaml del rol, con red del host (ADR 0040)
  local host=$1 role tag reg
  role=$(role_of "$host"); tag=$(version_tag); reg=$(registry)
  local metadata_addrs="metadata-1:50051,metadata-2:50051,metadata-3:50051"
  echo "services:"
  if [[ $role == metadata ]]; then
    local cluster="metadata-1=https://metadata-1:2380,metadata-2=https://metadata-2:2380,metadata-3=https://metadata-3:2380"
    local etcd_addrs="$host:2379"
    for other in "${METADATA_HOSTS[@]}"; do [[ $other != "$host" ]] && etcd_addrs+=",$other:2379"; done
    cat <<EOF
  etcd:
    image: $ETCD_IMAGE
    container_name: etcd
    network_mode: host
    restart: always
    command:
      - "etcd"
      - "--name=$host"
      - "--data-dir=/data"
      - "--listen-client-urls=https://[::]:2379"
      - "--advertise-client-urls=https://$host:2379"
      - "--listen-peer-urls=https://[::]:2380"
      - "--initial-advertise-peer-urls=https://$host:2380"
      - "--initial-cluster=$cluster"
      - "--initial-cluster-state=new"
      - "--cert-file=/run/secrets/dfsha/cert.pem"
      - "--key-file=/run/secrets/dfsha/key.pem"
      - "--trusted-ca-file=/run/secrets/dfsha/ca.pem"
      - "--client-cert-auth"
      - "--peer-cert-file=/run/secrets/dfsha/cert.pem"
      - "--peer-key-file=/run/secrets/dfsha/key.pem"
      - "--peer-trusted-ca-file=/run/secrets/dfsha/ca.pem"
      - "--peer-client-cert-auth"
      - "--auto-compaction-mode=periodic"
      - "--auto-compaction-retention=1h"
    volumes: [/srv/dfsha/data/etcd:/data, /srv/dfsha/secrets:/run/secrets/dfsha:ro]
  metadata:
    image: $reg/dfsha-metadata:$tag
    container_name: $host
    network_mode: host
    restart: always
    depends_on: [etcd]
    environment: {DFSHA_METADATA_ADDR: "$host:50051", DFSHA_ETCD_ADDRS: "$etcd_addrs"$(extra_env)}
    volumes: [/srv/dfsha/secrets:/run/secrets/dfsha:ro]
EOF
  elif [[ $role == datanode ]]; then
    cat <<EOF
  datanode:
    image: $reg/dfsha-datanode:$tag
    container_name: $host
    network_mode: host
    restart: always
    environment: {DFSHA_NODE_ID: "$host", DFSHA_DATANODE_ADDR: "$host:50052", DFSHA_METADATA_ADDRS: "$metadata_addrs"$(extra_env)}
    volumes: [/srv/dfsha/data:/data, /srv/dfsha/secrets:/run/secrets/dfsha:ro]
EOF
  else
    cat <<EOF
  client:
    image: $reg/dfsha-client:$tag
    container_name: $host
    network_mode: host
    restart: always
    environment: {DFSHA_METADATA_ADDRS: "$metadata_addrs"$(extra_env)}
    volumes: [/srv/dfsha/client:/data, /srv/dfsha/secrets:/run/secrets/dfsha:ro]
EOF
  fi
}

# Se ejecuta en cada instancia como root. Argumentos: <host> <id del volumen o vacío> <registro>
read -r -d '' REMOTE_SETUP <<'REMOTE' || true
set -euo pipefail
host=$1 volume=$2 registry=$3 role=${1%-*}
hostnamectl set-hostname "$host"
# cloud-init restablece el nombre en cada arranque si no se le pide conservarlo
echo 'preserve_hostname: true' > /etc/cloud/cloud.cfg.d/99-dfsha.cfg
# /etc/hosts con los nombres <rol>-<n> del clúster (ADR 0021); lo nuevo sustituye al bloque anterior
sed -i '/# dfsha-inicio/,/# dfsha-fin/d' /etc/hosts
{ echo "# dfsha-inicio"; cat /tmp/dfsha-hosts; echo "# dfsha-fin"; } >> /etc/hosts
if ! command -v docker >/dev/null; then
  apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq docker.io docker-compose-v2 >/dev/null
  systemctl enable --now docker >/dev/null 2>&1
fi
chronyc tracking | grep -q "Leap status     : Normal" || { echo "chrony no está sincronizado"; exit 1; }  # ADR 0033
mkdir -p /srv/dfsha/data
if [[ -n $volume ]]; then
  device=/dev/$(lsblk -dno NAME,SERIAL | awk -v serial="${volume/-/}" '$2 == serial {print $1}')
  blkid "$device" >/dev/null 2>&1 || mkfs.ext4 -q "$device"
  uuid=$(blkid -s UUID -o value "$device")
  grep -q "$uuid" /etc/fstab || echo "UUID=$uuid /srv/dfsha/data ext4 defaults,nofail 0 2" >> /etc/fstab
  mountpoint -q /srv/dfsha/data || mount /srv/dfsha/data
  # Arranque en frío (§9.6): sin el volumen montado, Docker no arranca. Así etcd y el nodo de datos nunca
  # arrancan sobre un directorio vacío del disco raíz
  mkdir -p /etc/systemd/system/docker.service.d
  printf '[Unit]\nRequiresMountsFor=/srv/dfsha/data\n' > /etc/systemd/system/docker.service.d/dfsha-volumen.conf
  systemctl daemon-reload
fi
if [[ $role == metadata ]]; then
  mkdir -p /srv/dfsha/data/etcd && chmod 0700 /srv/dfsha/data/etcd
elif [[ $role == datanode ]]; then
  # Marca del node_id: sin ella el nodo no arranca (fase I §3.4)
  [[ -f /srv/dfsha/data/dfsha-node-id ]] || echo "$host" > /srv/dfsha/data/dfsha-node-id
  chown -R 10001:10001 /srv/dfsha/data
else
  mkdir -p /srv/dfsha/client && chown 10001:10001 /srv/dfsha/client
fi
# Secretos de este host, con dueño el usuario de las imágenes y solo lectura (ADR 0043)
# Se cambia el contenido y no el directorio: un contenedor en marcha seguiría viendo el directorio borrado
mkdir -p /srv/dfsha/secrets && find /srv/dfsha/secrets -mindepth 1 -delete
cp -a /tmp/dfsha-secrets/. /srv/dfsha/secrets/ && rm -rf /tmp/dfsha-secrets
chown -R 10001:10001 /srv/dfsha/secrets && chmod 0500 /srv/dfsha/secrets && chmod 0400 /srv/dfsha/secrets/*
mv /tmp/dfsha-compose.yaml /srv/dfsha/compose.yaml
# La contraseña de ECR llega desde la máquina de administración y caduca a las 12 h; las imágenes quedan en caché
docker login --username AWS --password-stdin "$registry" < /tmp/dfsha-ecr-password >/dev/null 2>&1
rm -f /tmp/dfsha-ecr-password
docker compose -f /srv/dfsha/compose.yaml up -d --quiet-pull --remove-orphans 2>&1 | tail -1
REMOTE

install_host() {
  local host=$1 ip volume="" tmp
  ip=$(instance_field "$host" PublicIpAddress)
  [[ $(role_of "$host") != client ]] &&
    volume=$(aws ec2 describe-volumes --filters "Name=tag:Name,Values=dfsha-$host-data" --query 'Volumes[0].VolumeId' --output text)
  tmp=$(mktemp -d)
  hosts_file > "$tmp/hosts"; compose_for "$host" > "$tmp/compose.yaml"
  aws ecr get-login-password > "$tmp/ecr-password"
  until ssh "${SSH_OPTIONS[@]}" "ubuntu@$ip" true 2>/dev/null; do sleep 3; done
  ssh "${SSH_OPTIONS[@]}" "ubuntu@$ip" 'rm -rf /tmp/dfsha-secrets'
  scp -q "${SSH_OPTIONS[@]}" -r "$SECRETS/$host" "ubuntu@$ip:/tmp/dfsha-secrets"
  scp -q "${SSH_OPTIONS[@]}" "$tmp/hosts" "ubuntu@$ip:/tmp/dfsha-hosts"
  scp -q "${SSH_OPTIONS[@]}" "$tmp/compose.yaml" "ubuntu@$ip:/tmp/dfsha-compose.yaml"
  scp -q "${SSH_OPTIONS[@]}" "$tmp/ecr-password" "ubuntu@$ip:/tmp/dfsha-ecr-password"
  rm -rf "$tmp"
  ssh "${SSH_OPTIONS[@]}" "ubuntu@$ip" "sudo bash -s -- $host '$volume' $(registry)" <<< "$REMOTE_SETUP" 2>&1 |
    grep -vE 'outdated|up-to-date|need to be restarted|^$' | sed "s/^/[$host] /"
  log "$host instalado"
}

cmd_install() {
  [[ -d $SECRETS ]] || { log "ERROR: faltan los secretos en $SECRETS (python -m dfsha.common.pki)"; exit 1; }
  local pids=() hosts=("$@")
  (( ${#hosts[@]} > 0 )) || hosts=("${ALL_HOSTS[@]}")
  for host in "${hosts[@]}"; do install_host "$host" & pids+=($!); done
  local failed=0
  for pid in "${pids[@]}"; do wait "$pid" || failed=1; done
  (( failed == 0 )) || { log "ERROR: alguna instancia no se instaló"; exit 1; }
  log "Clúster instalado"
}

cmd_status() {
  aws ec2 describe-instances --filters Name=tag:project,Values=dfsha \
    --query 'Reservations[].Instances[].[Tags[?Key==`Name`]|[0].Value,InstanceType,State.Name]' --output text | sort
  for host in "${ALL_HOSTS[@]}"; do
    local ip; ip=$(instance_field "$host" PublicIpAddress 2>/dev/null) || continue
    [[ $ip == None ]] && continue
    printf '%s: ' "$host"
    ssh "${SSH_OPTIONS[@]}" "ubuntu@$ip" "sudo docker ps --format '{{.Names}} {{.Status}}' | tr '\n' ';'" 2>/dev/null || echo "sin SSH"
    echo
  done
}

backup_bucket() { echo "dfsha-copias-$(aws sts get-caller-identity --query Account --output text | tail -c 7)"; }

cmd_backup() {  # instantánea de etcd en S3 (ADR 0035): se hace al final de cada sesión de trabajo
  local bucket ip snapshot
  bucket=$(backup_bucket)
  if ! aws s3api head-bucket --bucket "$bucket" >/dev/null 2>&1; then
    aws s3api create-bucket --bucket "$bucket" >/dev/null
    aws s3api put-public-access-block --bucket "$bucket" --public-access-block-configuration \
      BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
    aws s3api put-bucket-encryption --bucket "$bucket" --server-side-encryption-configuration \
      '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
    aws s3api put-bucket-tagging --bucket "$bucket" --tagging 'TagSet=[{Key=project,Value=dfsha}]'
  fi
  ip=$(instance_field metadata-1 PublicIpAddress)
  snapshot="etcd-$(date -u +%Y%m%dT%H%M%SZ).db"
  ssh "${SSH_OPTIONS[@]}" "ubuntu@$ip" "sudo docker exec etcd etcdctl --endpoints=https://metadata-1:2379 \
    --cacert=/run/secrets/dfsha/ca.pem --cert=/run/secrets/dfsha/cert.pem --key=/run/secrets/dfsha/key.pem \
    snapshot save /data/$snapshot >/dev/null 2>&1 && sudo cat /srv/dfsha/data/etcd/$snapshot && sudo rm /srv/dfsha/data/etcd/$snapshot" |
    aws s3 cp - "s3://$bucket/$snapshot" --only-show-errors
  log "Copia de seguridad en s3://$bucket/$snapshot"
}

cmd_restore() {  # restauración manual de la copia de seguridad (ADR 0035; fase I §4.2)
  local bucket snapshot tmp cluster="" host ip
  bucket=$(backup_bucket)
  snapshot=${1:-$(aws s3 ls "s3://$bucket/" | awk '{print $4}' | sort | tail -1)}
  [[ -n $snapshot ]] || { log "ERROR: no hay ninguna copia en s3://$bucket"; exit 1; }
  tmp=$(mktemp -d)
  aws s3 cp "s3://$bucket/$snapshot" "$tmp/snapshot.db" --only-show-errors
  for host in "${METADATA_HOSTS[@]}"; do cluster+="${cluster:+,}$host=https://$host:2380"; done
  for host in "${METADATA_HOSTS[@]}"; do
    ssh "${SSH_OPTIONS[@]}" "ubuntu@$(instance_field "$host" PublicIpAddress)" \
      "sudo docker compose -f /srv/dfsha/compose.yaml stop 2>&1 | tail -1" | sed "s/^/[$host] /"
  done
  for host in "${METADATA_HOSTS[@]}"; do
    ip=$(instance_field "$host" PublicIpAddress)
    scp -q "${SSH_OPTIONS[@]}" "$tmp/snapshot.db" "ubuntu@$ip:/tmp/dfsha-snapshot.db"
    # El directorio anterior se aparta, no se borra. --bump-revision evita que las revisiones retrocedan: la época
    # del líder es una revisión, y los nodos de datos descartan épocas menores que la mayor que ya vieron.
    ssh "${SSH_OPTIONS[@]}" "ubuntu@$ip" "sudo bash -c 'set -e
      mv /srv/dfsha/data/etcd /srv/dfsha/data/etcd-anterior-\$(date -u +%Y%m%dT%H%M%SZ)
      docker run --rm --entrypoint etcdutl -v /srv/dfsha/data:/data -v /tmp/dfsha-snapshot.db:/snapshot.db:ro \
        $ETCD_IMAGE snapshot restore /snapshot.db --name $host --data-dir /data/etcd --initial-cluster $cluster \
        --initial-advertise-peer-urls https://$host:2380 --bump-revision 1000000000 --mark-compacted >/dev/null 2>&1
      chmod 0700 /srv/dfsha/data/etcd && rm /tmp/dfsha-snapshot.db'"
    log "$host restaurado desde $snapshot"
  done
  rm -rf "$tmp"
  for host in "${METADATA_HOSTS[@]}"; do
    ssh "${SSH_OPTIONS[@]}" "ubuntu@$(instance_field "$host" PublicIpAddress)" \
      "sudo docker compose -f /srv/dfsha/compose.yaml up -d 2>&1 | tail -1" | sed "s/^/[$host] /" &
  done
  wait
  log "Servidores de metadatos arrancados con la copia $snapshot"
}

cmd_down() {
  local ids
  ids=$(aws ec2 describe-instances --filters Name=tag:project,Values=dfsha \
    Name=instance-state-name,Values=pending,running,stopping,stopped --query 'Reservations[].Instances[].InstanceId' --output text)
  if [[ -n $ids ]]; then
    aws ec2 terminate-instances --instance-ids $ids >/dev/null
    aws ec2 wait instance-terminated --instance-ids $ids
    log "Instancias terminadas"
  fi
  for volume in $(aws ec2 describe-volumes --filters Name=tag:project,Values=dfsha --query 'Volumes[].VolumeId' --output text); do
    aws ec2 delete-volume --volume-id "$volume" && log "Volumen $volume borrado"
  done
  # Dos pasadas: un grupo no se puede borrar mientras las reglas de otro lo citan
  for pass in 1 2; do
    for role in metadata datanode client; do
      local group; group=$(security_group_id "dfsha-sg-$role")
      [[ $group != None ]] && aws ec2 delete-security-group --group-id "$group" >/dev/null 2>&1 && log "dfsha-sg-$role borrado"
    done
  done
  return 0
}

case ${1:-} in
  images) cmd_images ;;
  up) cmd_up ;;
  install) shift; cmd_install "$@" ;;
  status) cmd_status ;;
  backup) cmd_backup ;;
  restore) shift; cmd_restore "$@" ;;
  all) cmd_images; cmd_up; cmd_install ;;
  down) cmd_down ;;
  *) sed -n '2,15p' "$0"; exit 2 ;;
esac
