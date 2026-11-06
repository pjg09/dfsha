#!/usr/bin/env bash
# Versión de DFSha calculada desde Git, con la misma regla que hatch-vcs (ADR 0038):
#   en una etiqueta vX.Y.Z      -> X.Y.Z
#   N commits después de vX.Y.Z -> X.Y.(Z+1).devN+g<hash>
# Uso: scripts/get-version.sh            # versión de Python (PEP 440)
#      scripts/get-version.sh --image    # etiqueta de imagen Docker (sin «+», que Docker no admite)
set -euo pipefail
cd "$(dirname "$0")/.."

description=$(git describe --tags --long --match 'v[0-9]*')   # v0.2.0-12-gabc1234
if [[ ! $description =~ ^v([0-9]+)\.([0-9]+)\.([0-9]+)-([0-9]+)-g([0-9a-f]+)$ ]]; then
  echo "No se reconoce la descripción de Git: $description" >&2
  exit 1
fi
major=${BASH_REMATCH[1]} minor=${BASH_REMATCH[2]} patch=${BASH_REMATCH[3]}
distance=${BASH_REMATCH[4]} commit=${BASH_REMATCH[5]}

if [[ $distance == 0 ]]; then
  version="$major.$minor.$patch"
else
  version="$major.$minor.$((patch + 1)).dev$distance+g$commit"
fi

if [[ ${1:-} == --image ]]; then
  echo "${version//+/-}"
else
  echo "$version"
fi
