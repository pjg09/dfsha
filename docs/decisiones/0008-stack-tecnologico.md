# 0008 · Python 3.12, gRPC y Docker sobre varias instancias EC2

- **Estado:** Aceptada
- **Fecha:** 2026-10-23
- **Requisitos relacionados:** §5.1 (AWS Academy, nativo o con Docker), §7 (herramientas sugeridas, cuya elección hay que justificar); C26–C30

## Contexto
§7 sugiere Linux, Docker, FastAPI/Flask, gRPC y, cuando proceda, RabbitMQ/Kafka, y pide justificar la
elección. El sistema se despliega en varias instancias EC2 del Learner Lab (§5.1), con instancias pequeñas
(C28). Las convenciones ya dan por hecho Python (PEP 8, pytest, pyright).

## Opciones consideradas
1. **Python 3.12.** Es el lenguaje de los labs del curso y tiene `grpcio` y `cryptography` maduras. Es
   el más lento de los tres en CPU.
2. **Go.** Mejor rendimiento y concurrencia nativa, pero no se usó en el curso y cuesta más tiempo de desarrollo.
3. **Java.** Es el ecosistema de Hadoop, pero la JVM es pesada para los 908 MiB de una t3.micro.

## Decisión
- **Lenguaje:** Python 3.12 para todos los roles.
- **Comunicación:** `grpcio` y `protobuf`. El análisis de protocolos está en el ADR 0019.
- **Contenedores:** Docker Engine y Docker Compose, sobre instancias EC2 con Ubuntu LTS. El despliegue está en el ADR 0027.
- **Librerías:** se añaden las que hagan falta, cada una en su commit `build` (por ejemplo, `cryptography`
  para el cifrado y la implementación de Raft del ADR 0014).

## Consecuencias
- Hay un solo lenguaje para el cliente y los servidores, con tipos comprobados por pyright.
- **Límite:** el rendimiento de Python con streaming gRPC y cifrado no se ha medido. Lo dirán los experimentos (ADR 0028).
- **Pendiente:** fijar las versiones exactas de las dependencias al crear `pyproject.toml`.
