#!/usr/bin/env bash
# Utilidades para operar el clúster de AWS desde la máquina de administración.
#   deploy/aws/run.sh ssh <host> <orden>         ejecuta una orden en una instancia
#   deploy/aws/run.sh dfsha <usuario> <args...>  ejecuta la CLI en client-1 como ese usuario
# La contraseña de cada usuario se lee de deploy/aws/secrets/<usuario>-password (admin: admin-password),
# o del archivo de PASSWORD_FILE si está definida,
# y entra por la entrada estándar, así que no aparece en la línea de órdenes de ninguna máquina.
set -euo pipefail
cd "$(dirname "$0")/../.."
export AWS_DEFAULT_REGION=us-east-1

ssh_host() {
  local host=$1 ip; shift
  ip=$(aws ec2 describe-instances --filters "Name=tag:Name,Values=dfsha-$host" Name=instance-state-name,Values=running \
    --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)
  ssh -i "$HOME/.ssh/labsuser.pem" -o StrictHostKeyChecking=accept-new -o BatchMode=yes -o LogLevel=ERROR "ubuntu@$ip" "$@"
}

case ${1:-} in
  ssh) shift; ssh_host "$@" ;;
  dfsha)
    user=$2; shift 2
    password_file=${PASSWORD_FILE:-deploy/aws/secrets/$user-password}
    [[ $user == admin && -z ${PASSWORD_FILE:-} ]] && password_file=deploy/aws/secrets/admin-password
    # %q protege los argumentos al pasar por ssh y por sh -c
    ssh_host client-1 "sudo docker exec -i -e DFSHA_USERNAME=$user -e DFSHA_NEW_PASSWORD client-1 \
      sh -c 'read -r DFSHA_PASSWORD; read -r DFSHA_NEW_PASSWORD; export DFSHA_PASSWORD DFSHA_NEW_PASSWORD; \
      exec dfsha $(printf '%q ' "$@")'" \
      < <(printf '%s\n' "$(cat "$password_file")" "$(cat "${NEW_PASSWORD_FILE:-/dev/null}")")  # una línea cada una
    ;;
  *) sed -n '2,6p' "$0"; exit 2 ;;
esac
