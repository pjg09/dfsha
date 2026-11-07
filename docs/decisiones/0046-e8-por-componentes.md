# 0046 · Métricas y experimentos, con E8 medido por componentes

- **Estado:** Aceptada
- **Fecha:** 2026-11-07
- **Requisitos relacionados:** §4.1 (métricas y experimentos), §5.2 (rendimiento); C10, C16, C19, C20, C21; sustituye al ADR 0028

## Contexto
El ADR 0028 define E8 como «con y sin cifrado en reposo y TLS», con el coste en tasa de transferencia. Medirlo de extremo a extremo exige que el sistema pueda funcionar sin cifrado en el cliente y sin TLS en todos los nodos, y el código no tiene ese modo: la seguridad no se puede apagar (ADR 0043). Añadirlo solo para un experimento pondría en el código de producción un modo inseguro que una configuración equivocada podría activar.

Además, E1 y E2 muestran que un solo cliente se queda en unos 130 MB/s con independencia del número de nodos de datos. E8 tiene que ayudar a explicar ese límite, y para eso sirve más saber cuánto cuesta cada pieza que una sola cifra de extremo a extremo.

## Opciones consideradas
1. **De extremo a extremo:** variables solo para experimentos que desactiven el cifrado y el TLS, y repetir E1 sin ellos.
2. **Por componentes:** medir en las mismas instancias del clúster lo que cuesta cada pieza de la seguridad, sin tocar el sistema, y compararlo con E1.

## Decisión
Opción 2, elegida por Pedro el 2026-11-07. Se mantiene todo el ADR 0028 salvo la fila de E8:

| Exp. | Variable | Métrica | Sostiene |
|---|---|---|---|
| E1 | Tamaño del archivo (16 MiB, 256 MiB, 1 GiB) | `latency_ms` de `put` y `get` | Línea base |
| E2 | Número de nodos de datos (3, 4 y 5) | `throughput_mb_s` de `get` y `put` | Escalabilidad (RNF1, ADR 0015) |
| E3 | W = 2 frente a W = 3 | `latency_ms` de la escritura de un bloque | ADR 0012 (C10) |
| E4 | Clientes concurrentes (1, 2, 4 y 8), sobre archivos distintos y sobre el mismo | Tasa de transferencia agregada y número de conflictos | ADR 0011 (RNF5) |
| E5 | Tamaño de bloque (4, 16 y 64 MiB) | Tasa de transferencia y latencia de la modificación parcial | ADR 0016 (C19) |
| E6 | Caída de un nodo de datos | Tiempo de detección, tiempo de re-replicación y lecturas fallidas durante la caída | ADR 0018 (C16) |
| E7 | Caída del líder de metadatos | Tiempo sin servicio de metadatos, separando la elección del modo seguro; escrituras rechazadas con `SAFE_MODE_ACTIVE` | ADR 0014 y 0031 |
| **E8** | **Coste de cada pieza de la seguridad:** cifrado y descifrado AES-256-GCM y SHA-256 en la CPU del cliente; una transferencia gRPC con TLS mutuo y sin TLS entre `client-1` y un nodo de datos, fuera de DFSha | **MB/s de cada pieza, y su peso estimado en la tasa de E1** | **ADR 0023 y 0024** |
| E9 | Arranque en frío: parar las 9 instancias y arrancarlas, también tras el fin de sesión del lab | Tiempo hasta que los contenedores vuelven solos y hasta salir del modo seguro; si sale por la condición o por el tope; re-replicaciones y borrados lanzados (deben ser 0) | ADR 0031 (C27) |

**Método:** el del ADR 0028, sin cambios:
- Al menos 5 repeticiones por punto, informando la mediana y el p95.
- Unidades en MB/s, es decir, megabytes (C21).
- Archivos de contenido aleatorio.
- Tiempos medidos en el cliente.
- Resultados en `bench/resultados/AAAA-MM-DD-<experimento>.csv`.
- Se anota el modo de créditos de CPU de las instancias t3.

## Consecuencias
- **Se gana:**
  - El sistema no gana ningún modo inseguro.
  - E8 dice dónde se va el tiempo (cifrado, hash o TLS), que es lo que hace falta para explicar el límite del cliente que mostraron E1 y E2.
- **Se pierde:** E8 no da una tasa de extremo a extremo sin seguridad. El coste total es una estimación a partir de las piezas, no una medición directa.
- **Límite:** la transferencia gRPC de prueba no pasa por el código de DFSha (reenvío, avisos, metadatos), así que solo aísla el coste de TLS en el canal.
