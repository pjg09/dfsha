#!/usr/bin/env bash
# E4 (ADR 0046): 1, 2, 4 y 8 clientes a la vez, cada uno con su conexión y su token, desde client-1.
# Sobre archivos distintos: tasa agregada de put y get (128 MiB por cliente; con 8 son 1 GiB de copias en el
# disco de client-1). Sobre el mismo bloque: latencia hasta confirmar y conflictos.
set -euo pipefail
cd "$(dirname "$0")/.."
for clients in 1 2 4 8; do
  bench/ejecutar.sh e4 concurrent --condition "$clients-distintos" --clients "$clients" --mode distinct --sizes 128 --reps 5
done
for clients in 2 4 8; do
  bench/ejecutar.sh e4 concurrent --condition "$clients-mismo-bloque" --clients "$clients" --mode same --sizes 128 --reps 5
done
