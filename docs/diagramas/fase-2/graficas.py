"""Gráficas de resultados del informe de la fase II, a partir de los CSV de bench/resultados/.

Se ejecuta desde la raíz del repositorio, sin añadir matplotlib a las dependencias del proyecto:

    uv run --no-project --with matplotlib==3.10.3 python docs/diagramas/fase-2/graficas.py

Escribe los PNG en docs/diagramas/fase-2/. Paleta validada con la guía de visualización: azul y naranja
para carga y recuperación (o para los dos tramos de una recuperación), y aqua solo con valor rotulado.
"""

import csv
import statistics
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "bench" / "resultados"
OUT = Path(__file__).resolve().parent

BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK_2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
WIDTH_IN = 7.5  # ancho de la página útil; alto/ancho siempre ≤ 1,38
DPI = 300

plt.rcParams.update({
    "font.family": "Liberation Sans",
    "font.size": 10.5,
    "axes.edgecolor": INK_2,
    "axes.labelcolor": INK,
    "axes.titlesize": 11.5,
    "axes.titleweight": "bold",
    "axes.titlelocation": "left",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "xtick.color": INK_2,
    "ytick.color": INK_2,
    "legend.frameon": False,
    "figure.facecolor": "white",
    "savefig.facecolor": "white",
})


def rows(name: str) -> list[dict[str, str]]:
    with open(RESULTS / name, newline="") as f:
        return list(csv.DictReader(f))


def median(values: list[float]) -> float:
    return statistics.median(values)


def rate(data: list[dict[str, str]], condition: str, operation: str, size: str | None = None) -> float:
    return median([
        float(r["tasa_mb_s"]) for r in data
        if r["condicion"] == condition and r["operacion"] == operation and (size is None or r["tamano_mib"] == size)
    ])  # fmt: skip


def grid(ax, axis: str = "y") -> None:
    ax.grid(axis=axis, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def label_bars(ax, bars, fmt: str = "{:.0f}", inside: bool = False) -> None:
    for bar in bars:
        height = bar.get_height()
        y = height - 4 if inside else height + 2
        ax.text(bar.get_x() + bar.get_width() / 2, y, fmt.format(height).replace(".", ","),
                ha="center", va="top" if inside else "bottom", fontsize=9, color=INK)  # fmt: skip


def save(fig, name: str) -> None:
    fig.savefig(OUT / name, dpi=DPI, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)


def fig_tasa() -> None:
    """E2 (un cliente, 3 a 5 nodos) y E4 (1 a 8 clientes en el mismo host): el techo es el cliente."""
    e2, e4 = rows("2026-11-07-e2.csv"), rows("2026-11-07-e4.csv")
    fig, (a, b) = plt.subplots(1, 2, figsize=(WIDTH_IN, 3.6), sharey=True, gridspec_kw={"wspace": 0.12})
    nodes = ["3", "4", "5"]
    x = range(len(nodes))
    w = 0.36
    bars_put = a.bar([i - w / 2 - 0.01 for i in x], [rate(e2, f"{n}-nodos", "put", "1024") for n in nodes], w, color=BLUE, label="put")
    bars_get = a.bar([i + w / 2 + 0.01 for i in x], [rate(e2, f"{n}-nodos", "get", "1024") for n in nodes], w, color=ORANGE, label="get")
    label_bars(a, bars_put)
    label_bars(a, bars_get)
    a.set_xticks(list(x), [f"{n} nodos" for n in nodes])
    a.set_title("E2 · un cliente, archivo de 1 GiB")
    a.set_ylabel("Tasa de transferencia mediana (MB/s)")
    grid(a)

    clients = ["1", "2", "4", "8"]
    x = range(len(clients))
    bars_put = b.bar([i - w / 2 - 0.01 for i in x], [rate(e4, f"{c}-distintos", "put-agregada") for c in clients], w, color=BLUE, label="put")
    bars_get = b.bar([i + w / 2 + 0.01 for i in x], [rate(e4, f"{c}-distintos", "get-agregada") for c in clients], w, color=ORANGE, label="get")
    label_bars(b, bars_put)
    label_bars(b, bars_get)
    b.set_xticks(list(x), [f"{c} {'cliente' if c == '1' else 'clientes'}" for c in clients])
    b.set_title("E4 · tasa agregada, todos en client-1")
    grid(b)
    b.legend(loc="upper left", ncols=2, bbox_to_anchor=(0, 1.0))
    a.set_ylim(0, 165)
    save(fig, "05-tasa-de-transferencia.png")


def fig_bloque() -> None:
    """E5: tasa con archivos de 1 GiB y latencia de una modificación parcial de 4 KiB, por tamaño de bloque."""
    e5 = rows("2026-11-07-e5.csv")
    sizes = ["4", "16", "64"]
    fig, (a, b) = plt.subplots(1, 2, figsize=(WIDTH_IN, 3.5), gridspec_kw={"wspace": 0.32})
    x = range(len(sizes))
    w = 0.36
    bars_put = a.bar([i - w / 2 - 0.01 for i in x], [rate(e5, f"bloque-{s}mib", "put", "1024") for s in sizes], w, color=BLUE, label="put")
    bars_get = a.bar([i + w / 2 + 0.01 for i in x], [rate(e5, f"bloque-{s}mib", "get", "1024") for s in sizes], w, color=ORANGE, label="get")
    label_bars(a, bars_put)
    label_bars(a, bars_get)
    a.set_xticks(list(x), [f"{s} MiB" for s in sizes])
    a.set_xlabel("Tamaño de bloque")
    a.set_ylabel("Tasa de transferencia mediana (MB/s)")
    a.set_title("Archivo de 1 GiB")
    a.set_ylim(0, 165)
    a.legend(loc="upper right", ncols=2)
    grid(a)

    latencies = [median([float(r["latencia_ms"]) for r in e5 if r["condicion"] == f"bloque-{s}mib" and r["operacion"] == "parcial-4kib"]) for s in sizes]
    bars = b.bar(list(x), latencies, 0.5, color=AQUA)
    for bar in bars:
        b.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 30, f"{bar.get_height():,.0f} ms".replace(",", " "),
               ha="center", va="bottom", fontsize=9, color=INK)  # fmt: skip
    b.set_xticks(list(x), [f"{s} MiB" for s in sizes])
    b.set_xlabel("Tamaño de bloque")
    b.set_ylabel("Latencia mediana (ms)")
    b.set_title("Modificación parcial de 4 KiB")
    b.set_ylim(0, 2100)
    grid(b)
    save(fig, "06-tamano-de-bloque.png")


def fig_lecturas_congelado() -> None:
    """E6 con un nodo congelado: duración de cada lectura de 256 MiB, antes y después del vigilante (ADR 0047)."""
    reads = [r for r in rows("2026-11-07-e6-lecturas.csv") if r["variante"] == "congelado"]
    versions = [("0.13.0", "v0.13.0\nsin vigilante", ORANGE), ("0.13.1", "v0.13.1\ncon vigilante (10 s)", BLUE)]
    fig, ax = plt.subplots(figsize=(WIDTH_IN, 3.4))
    def decimal(value: float, digits: int) -> str:
        return f"{value:.{digits}f}".replace(".", ",")

    for i, (version, _, color) in enumerate(versions):
        values = [float(r["duracion_s"]) for r in reads if r["version"] == version]  # en el orden en que se hicieron
        ys = [i - 0.18 + ((j * 7) % 13) / 12 * 0.36 for j in range(len(values))]  # dispersión fija, sin azar
        ax.scatter(values, ys, s=22, color=color, edgecolors="white", linewidths=0.6, zorder=3)
        summary = f"mediana {decimal(median(values), 2)} s · máximo {decimal(max(values), 1)} s · {len(values)} lecturas"
        ax.text(1.6, i + 0.3, summary, va="bottom", fontsize=9, color=INK)
    ax.set_xscale("log")
    ax.set_xlim(1.5, 500)
    ax.set_xticks([2, 5, 10, 30, 120, 360], ["2", "5", "10", "30", "120", "360"])
    ax.set_yticks([0, 1], [v[1] for v in versions])
    ax.set_ylim(-0.6, 1.6)
    ax.set_xlabel("Duración de cada lectura (s, escala logarítmica)")
    grid(ax, "x")
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    save(fig, "07-lecturas-con-nodo-congelado.png")


def fig_recuperacion() -> None:
    """Tiempos de recuperación ante fallos (medianas por tramo): E6, E7 en sus dos variantes y E9."""
    e6 = [r for r in rows("2026-11-07-e6.csv") if r["version"] == "0.13.0" and r["variante"] == "parada"]
    e9 = rows("2026-11-07-e9.csv")
    # E7: medianas de bench/resultados/2026-11-07-e7.md, que calcula bench/e7_resumen.py con el registro del líder
    scenarios = [
        ("E9 · arranque en frío\nde las 9 instancias", median([float(r["lider_elegido_s"]) for r in e9]),
         median([float(r["fin_modo_seguro_s"]) - float(r["lider_elegido_s"]) for r in e9]), "arranque y elección", "modo seguro"),
        ("E6 · caída de un\nnodo de datos", median([float(r["deteccion_s"]) for r in e6]),
         median([float(r["rereplicacion_s"]) for r in e6]), "detección", "re-replicación"),
        ("E7 · líder de metadatos\ncongelado", 5.33, 1.58, "elección", "modo seguro"),
        ("E7 · líder parado\n(relevo ordenado)", 0.13, 0.76, "elección", "modo seguro"),
    ]
    fig, ax = plt.subplots(figsize=(WIDTH_IN, 3.6))
    for i, (_, first, second, _, _) in enumerate(scenarios):
        y = len(scenarios) - 1 - i
        ax.barh(y, first, 0.55, color=BLUE, edgecolor="white", linewidth=1.5)
        ax.barh(y, second, 0.55, left=first, color=ORANGE, edgecolor="white", linewidth=1.5)
        ax.text(first + second + 0.6, y, f"{first:.1f} + {second:.1f} s".replace(".", ","), va="center", fontsize=9, color=INK)
    ax.set_yticks(range(len(scenarios)), [s[0] for s in reversed(scenarios)])
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.set_xlim(0, 52)
    ax.set_xlabel("Segundos desde el fallo o el arranque (mediana de cada tramo)")
    grid(ax, "x")
    handles = [plt.Rectangle((0, 0), 1, 1, color=BLUE), plt.Rectangle((0, 0), 1, 1, color=ORANGE)]
    ax.legend(handles, ["1.er tramo: detección, elección o arranque", "2.º tramo: re-replicación o modo seguro"],
              loc="lower right", fontsize=9)  # fmt: skip
    save(fig, "09-tiempos-de-recuperacion.png")


def fig_seguridad() -> None:
    """E8: tasa de cada pieza de la seguridad frente al techo de un cliente (E1)."""
    e8 = rows("2026-11-07-e8.csv")
    e1 = rows("2026-11-08-e1.csv")
    pieces = [
        ("AES-256-GCM, cifrar", "cpu-client-1", "aes-gcm-cifrar"),
        ("AES-256-GCM, descifrar", "cpu-client-1", "aes-gcm-descifrar"),
        ("gRPC sin TLS, envío", "grpc-client-1-a-datanode-2", "grpc-envio-plain"),
        ("gRPC sin TLS, recepción", "grpc-client-1-a-datanode-2", "grpc-recepcion-plain"),
        ("gRPC con TLS mutuo, envío", "grpc-client-1-a-datanode-2", "grpc-envio-tls"),
        ("gRPC con TLS mutuo, recepción", "grpc-client-1-a-datanode-2", "grpc-recepcion-tls"),
        ("SHA-256", "cpu-client-1", "sha256"),
    ]
    values = [rate(e8, condition, operation) for _, condition, operation in pieces]
    ceiling = median([rate(e1, "base", "put", "1024"), rate(e1, "base", "get", "1024")])
    fig, ax = plt.subplots(figsize=(WIDTH_IN, 3.7))
    ys = list(range(len(pieces)))[::-1]
    ax.barh(ys, values, 0.55, color=BLUE)
    for y, v in zip(ys, values):
        ax.text(v + 20, y, f"{v:,.0f}".replace(",", " "), va="center", fontsize=9, color=INK)
    ax.axvline(ceiling, color=INK_2, linewidth=1.2, linestyle="--")
    ax.text(ceiling + 15, len(pieces) - 0.45, f"techo de un cliente en E1: ~{ceiling:.0f} MB/s", fontsize=9, color=INK_2, va="bottom")
    ax.set_yticks(ys, [p[0] for p in pieces])
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.set_xlim(0, 1750)
    ax.set_ylim(-0.6, len(pieces) - 0.1)
    ax.set_xlabel("Tasa mediana de cada pieza por separado (MB/s)")
    grid(ax, "x")
    save(fig, "08-coste-de-la-seguridad.png")


if __name__ == "__main__":
    fig_tasa()
    fig_bloque()
    fig_lecturas_congelado()
    fig_recuperacion()
    fig_seguridad()
    for png in sorted(OUT.glob("0[5-9]-*.png")):
        print(png.name)
