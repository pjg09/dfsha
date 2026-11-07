# Imágenes de DFSha, una por rol (ADR 0040): docker build --target datanode -t dfsha-datanode:<versión> .
# La versión llega como argumento porque la imagen no lleva el historial de Git (ADR 0038).

FROM ghcr.io/astral-sh/uv:0.12.5@sha256:e85be844203885286c60ffad8a858d48afb6c5a5c237ca0e67f12e74b8f174b1 AS uv

FROM python:3.12.16-slim-trixie@sha256:4840d514c583a4d3d8cad3940e68dee6f0f6f3635c12fcd0a3d74c21a5b93a54 AS base
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PYTHONUNBUFFERED=1 \
    # Menos arenas de malloc: con 8 escrituras simultáneas, la mediana del pico de memoria de un
    # nodo de datos baja de 257 a 167 MiB sin perder tasa de transferencia (docs/fase-2/notas.md)
    MALLOC_ARENA_MAX=2
WORKDIR /app

# Dependencias primero, para que la capa se reutilice mientras no cambie uv.lock
COPY pyproject.toml uv.lock README.md .python-version ./
RUN uv sync --locked --no-dev --no-install-project

ARG DFSHA_VERSION=0.0.0
COPY dfsha ./dfsha
RUN SETUPTOOLS_SCM_PRETEND_VERSION=${DFSHA_VERSION} uv sync --locked --no-dev --no-editable \
    && rm /usr/local/bin/uv

# Usuario sin privilegios; /data es del usuario para que un volumen Docker nuevo herede el permiso
RUN useradd --system --uid 10001 --no-create-home dfsha \
    && mkdir /data && chown dfsha:dfsha /data
USER dfsha
ENV PATH=/app/.venv/bin:$PATH

FROM base AS datanode
ENTRYPOINT ["python", "-m", "dfsha.datanode"]

FROM base AS metadata
ENTRYPOINT ["python", "-m", "dfsha.metadata"]

# El cliente queda en marcha para usarlo con: docker exec client-1 dfsha <orden>
FROM base AS client
WORKDIR /data
CMD ["sleep", "infinity"]

