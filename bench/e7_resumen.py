"""Resumen de E7 (ADR 0046): servicio de metadatos durante la caída del líder, repetición a repetición.

Uso: python bench/e7_resumen.py bench/resultados/AAAA-MM-DD-e7-<variante>  (sin extensión: lee el .csv de la
sonda y el -lider.txt con la hora de cada caída y las líneas del nuevo líder). Todas las horas son UTC del mismo
día, de relojes sincronizados con chrony.
"""

import csv
import re
import statistics
import sys
from datetime import datetime

base = sys.argv[1]


def seconds(clock: str) -> float:
    moment = datetime.strptime(clock[:12].ljust(12, "0"), "%H:%M:%S.%f")
    return moment.hour * 3600 + moment.minute * 60 + moment.second + moment.microsecond / 1e6


probes = list(csv.DictReader(open(f"{base}.csv", encoding="utf-8")))
leader_lines = open(f"{base}-lider.txt", encoding="utf-8").read().splitlines()
crashes: dict[str, float] = {}
events: list[tuple[float, str]] = []
for line in leader_lines:
    if match := re.match(r"\[(\d\d:\d\d:\d\d\.\d+)\] repetición (\d+): metadata", line):
        crashes[match.group(2)] = seconds(match.group(1))
    elif match := re.search(r"T(\d\d:\d\d:\d\d\.\d+)Z .*(Elegido líder|Fin del modo seguro)", line):
        events.append((seconds(match.group(1)), match.group(2)))

print("| Rep. | Sin servicio para el cliente (s) | Elección (s) | Modo seguro (s) | Rechazos `SAFE_MODE_ACTIVE` | Otros fallos | mkdir mediano fuera de la caída (ms) |")
print("|---|---|---|---|---|---|---|")
totals: dict[str, list[float]] = {"sin": [], "eleccion": [], "seguro": [], "mkdir": []}
for rep, crash in sorted(crashes.items()):
    rows = [row for row in probes if row["repeticion"] == rep]
    after = [row for row in rows if seconds(row["hora_utc"]) > crash]
    first_ok = next((seconds(row["hora_utc"]) for row in after if row["resultado"] == "ok"), None)
    # La hora de la caída es cuando «docker stop» devuelve el control: un líder que renuncia al recibir SIGTERM deja
    # elegir al siguiente unos milisegundos antes, así que se busca desde 2 s antes y hasta 60 s después
    elected = next((t for t, kind in events if kind == "Elegido líder" and crash - 2 <= t <= crash + 60), None)
    safe_end = next((t for t, kind in events if kind == "Fin del modo seguro" and elected and t >= elected), None)
    window = [row for row in after if first_ok is None or seconds(row["hora_utc"]) <= first_ok]
    rejected = sum(row["resultado"] == "SAFE_MODE_ACTIVE" for row in window)
    other = sum(row["resultado"] not in ("ok", "SAFE_MODE_ACTIVE") for row in window)
    normal = [float(row["latencia_ms"]) for row in rows if row["resultado"] == "ok" and not crash - 1 <= seconds(row["hora_utc"]) <= (first_ok or crash) + 1]
    unavailable = first_ok - crash if first_ok else float("nan")
    election = elected - crash if elected else float("nan")
    safe = safe_end - elected if safe_end and elected else float("nan")
    totals["sin"].append(unavailable)
    totals["eleccion"].append(election)
    totals["seguro"].append(safe)
    totals["mkdir"].append(statistics.median(normal))
    print(f"| {rep} | {unavailable:.2f} | {election:.2f} | {safe:.2f} | {rejected} | {other} | {statistics.median(normal):.1f} |")
print(
    f"| **mediana** | **{statistics.median(totals['sin']):.2f}** | **{statistics.median(totals['eleccion']):.2f}** | "
    f"**{statistics.median(totals['seguro']):.2f}** | | | **{statistics.median(totals['mkdir']):.1f}** |"
)
