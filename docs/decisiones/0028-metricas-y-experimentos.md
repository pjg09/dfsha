# 0028 · Métricas y experimentos

- **Estado:** Aceptada
- **Fecha:** 2026-10-23
- **Requisitos relacionados:** §4.1 (métricas y experimentos), §5.1, §5.2 (rendimiento con al menos dos condiciones); C10, C16, C19, C20, C21

## Contexto
La fase I tiene que definir métricas y experimentos y justificar los compromisos técnicos. §5.2 pide medir
latencia y tasa de transferencia en al menos dos condiciones. Varias decisiones de diseño tienen parámetros
que conviene sostener con datos.

## Opciones consideradas
1. **Medir solo el mínimo de §5.2:** dos condiciones de latencia y tasa de transferencia.
2. **Un experimento por cada decisión que haya que defender con datos.**

## Decisión
Opción 2:

| Exp. | Variable | Métrica | Sostiene |
|---|---|---|---|
| E1 | Tamaño del archivo (16 MiB, 256 MiB, 1 GiB) | `latency_ms` de `put` y `get` | Línea base |
| E2 | Número de nodos de datos (3, 4 y 5) | `throughput_mb_s` de `get` y `put` | Escalabilidad (RNF1, ADR 0015) |
| E3 | W = 2 frente a W = 3 | `latency_ms` de la escritura de un bloque | ADR 0012 (C10) |
| E4 | Clientes concurrentes (1, 2, 4 y 8), sobre archivos distintos y sobre el mismo | Tasa de transferencia agregada y número de conflictos | ADR 0011 (RNF5) |
| E5 | Tamaño de bloque (4, 16 y 64 MiB) | Tasa de transferencia y latencia de la modificación parcial | ADR 0016 (C19) |
| E6 | Caída de un nodo de datos | Tiempo de detección, tiempo de re-replicación y lecturas fallidas durante la caída | ADR 0018 (C16) |
| E7 | Caída del líder de metadatos | Tiempo sin servicio de metadatos, separando la elección del modo seguro; escrituras rechazadas con `SAFE_MODE_ACTIVE` | ADR 0014 y 0031 |
| E8 | Con y sin cifrado en reposo y TLS | Coste en tasa de transferencia | ADR 0023 y 0024 |
| E9 | Arranque en frío: parar las 9 instancias y arrancarlas, también tras el fin de sesión del lab | Tiempo hasta que los contenedores vuelven solos y hasta salir del modo seguro; si sale por la condición o por el tope; re-replicaciones y borrados lanzados (deben ser 0) | ADR 0031 (C27) |

**Método:**
- Al menos 5 repeticiones por punto, informando la mediana y el p95.
- Unidades en MB/s, es decir, megabytes (C21).
- Archivos de contenido aleatorio.
- Tiempos medidos en el cliente.
- Resultados en `bench/resultados/AAAA-MM-DD-<experimento>.csv`.
- Se anota el modo de créditos de CPU de las instancias t3, porque agotar los créditos falsea las mediciones.

## Consecuencias
- **Se gana:** cada parámetro de diseño tiene una medición que lo sostiene o que obliga a cambiarlo (ADR 0006).
- **Se pierde:** horas de laboratorio y crédito.
- **Límite:** con instancias pequeñas y una sola zona, los números absolutos no se pueden extrapolar a
  producción. Lo que vale son las comparaciones entre condiciones.
