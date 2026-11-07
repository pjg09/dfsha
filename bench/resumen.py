"""Mediana y percentil 95 de cada punto de un CSV de bench/resultados (ADR 0028).

Uso: python bench/resumen.py bench/resultados/AAAA-MM-DD-<experimento>.csv
El p95 es el de rango más cercano: con 5 repeticiones coincide con el máximo.
"""

import csv
import math
import statistics
import sys
from collections import defaultdict


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(fraction * len(ordered)) - 1)]


rows = list(csv.DictReader(open(sys.argv[1], encoding="utf-8")))
groups: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
for row in rows:
    groups[(row["condicion"], row["operacion"], row["tamano_mib"])].append(row)
print("| Condición | Operación | Tamaño (MiB) | n | Latencia mediana (ms) | Latencia p95 (ms) | Tasa mediana (MB/s) | Hash |")
print("|---|---|---|---|---|---|---|---|")
for (condition, operation, size), group in sorted(groups.items(), key=lambda item: (item[0][0], item[0][1], int(item[0][2]))):
    latencies = [float(row["latencia_ms"]) for row in group]
    rates = [float(row["tasa_mb_s"]) for row in group]
    hashes = "ok" if all(row["hash_ok"] == "True" for row in group) else "FALLO"
    print(
        f"| {condition} | {operation} | {size} | {len(group)} | {statistics.median(latencies):.0f} | "
        f"{percentile(latencies, 0.95):.0f} | {statistics.median(rates):.1f} | {hashes} |"
    )
