# 0039 · Raft con etcd en los servidores de metadatos

- **Estado:** Aceptada
- **Fecha:** 2026-11-06
- **Requisitos relacionados:** RNF2, RNF4; completa el ADR 0014; ADR 0010 (G2), 0031 y 0035; fase I §3.3, §4.2 y §14

## Contexto
El ADR 0014 fija Raft en tres servidores de metadatos con una implementación existente, y deja la
elección entre etcd y PySyncObj para después de probarlas. La fase I exige dos cosas de esa
implementación: que escriba cada entrada en disco antes de confirmarla (§4.2, §14) y que las lecturas del
líder sean linealizables (G2, ADR 0010).

Se probaron el 2026-11-06 con tres nodos en Docker Compose en la máquina de desarrollo: PySyncObj 0.3.17
con su journal en archivo, y etcd v3.7.3 con sus valores por defecto. El cliente escribe valores de
100 bytes. El disco es un SSD local, así que los números absolutos no valen para EBS; sirve la comparación.

| Criterio | PySyncObj 0.3.17 | etcd v3.7.3 |
|---|---|---|
| Entrada en disco antes de confirmar | **No.** 200 escrituras confirmadas y ninguna llamada a `fsync`, `fdatasync` ni `msync` en el líder (`strace`). El journal se escribe en memoria mapeada y nunca se sincroniza | **Sí.** 301 escrituras y 301 `fsync` del WAL, tanto en el líder como en un seguidor (métrica `etcd_disk_wal_fsync_duration_seconds_count`) |
| Lecturas linealizables | **No.** Lee su estado local, y su propio código advierte que puede haber dos líderes a la vez: un líder aislado tarda hasta 30 s (`leaderFallbackTimeout`) en dejar de serlo | **Sí**, por defecto |
| Latencia de escritura secuencial (mediana / p95) | 1,09 / 1,25 ms sin lotes, sin tocar el disco; 101 / 101 ms con los lotes, que vienen activados por defecto | 1,27 / 1,63 ms, con `fsync` |
| Hueco sin escrituras al caer el líder (3 rondas, plazo del cliente de 1 s) | 0,97–2,05 s | 2,07 s |
| Nodo caído que vuelve | Se pone al día | Se pone al día |
| Memoria por nodo | ~13 MiB | 18–30 MiB |
| Cliente de Python | Es una librería del propio proceso | `etcd-sdk-python` 0.0.7 (síncrono) y `aetcd` 1.0.0 (asyncio) funcionan con grpcio 1.85.1 y protobuf 7.36.2; una transacción condicional rechaza la escritura que parte de una versión vieja. El cliente clásico `etcd3` no se actualiza desde 2020 |

El hueco al caer el líder depende sobre todo del plazo del cliente: los dos sistemas recuperan las
escrituras en menos de 2 s con sus tiempos de elección por defecto.

El análisis de Jepsen de etcd 3.4.3 (2020-01-30) confirma que sus lecturas, escrituras y transacciones son
*strict serializable*. También muestra que sus cerrojos con arrendamiento no dan exclusión mutua: con
pausas de proceso, dos clientes llegan a tenerlo a la vez. Recomienda usar como ficha de cercado
(*fencing token*) la revisión de etcd de la clave, y que el recurso protegido rechace las fichas antiguas.
Esto importa aquí porque el líder de DFSha da órdenes destructivas a los nodos de datos en la respuesta al
latido (ADR 0018): un líder depuesto que no lo sabe podría ordenar borrados con un estado viejo. El contrato
del Anexo A no lleva nada que lo impida, y el problema existiría con cualquier implementación de Raft.

## Opciones consideradas
1. **PySyncObj tal cual.** Incumple la §4.2 y G2.
2. **PySyncObj modificado:** sincronizar el journal y el voto en disco en cada entrada, y pasar las lecturas
   por el log. Sería mantener una versión propia de una librería con un solo mantenedor y 34 issues
   abiertos, es decir, implementar a medias el consenso que el ADR 0014 dice no implementar a mano.
3. **etcd.**

## Decisión
Opción 3: **etcd v3.7.3**.
- **Un miembro de etcd en cada servidor de metadatos** (`metadata-1` a `metadata-3`), con su directorio de
  datos en el volumen EBS del servidor (ADR 0035). Puertos: 2380 entre los miembros y 2379 para sus
  clientes, abiertos solo dentro de `dfsha-sg-metadata`, con TLS mutuo (ADR 0023).
- **Valores de partida:** latido de 100 ms, elección de 1000 ms e instantánea cada 10 000 transacciones,
  que son los de etcd. Se ajustan con E7.
- **Todo cambio de metadatos es una transacción de etcd**, que es una entrada de su log replicado. Las
  condiciones de las que depende (versión base, arrendamiento vigente) van en la comparación de esa misma
  transacción, así que se comprueban y se aplican de forma atómica.
- **El servidor de metadatos de DFSha es un cliente de etcd.** Su líder se elige con una clave de
  elección ligada a un arrendamiento de etcd.
- **Sin cerebro dividido en DFSha**, con tres defensas:
  1. **Época del líder.** La revisión de etcd en la que se creó la clave de elección del líder es su época,
     que crece en cada elección. Cada escritura del líder comprueba en la misma transacción que la clave de
     elección sigue siendo la suya: un líder depuesto no puede escribir.
  2. **Ficha de cercado en las órdenes.** Las respuestas al latido llevan la época, y cada nodo de datos
     recuerda la mayor que ha visto y descarta las órdenes con una época menor. Un líder depuesto no puede
     ordenar borrados ni re-replicaciones. Exige añadir la época a `ReportHeartbeatResponse` y
     `ReportBlocksResponse`, un cambio compatible del contrato que se hace en la etapa 4.
  3. **Renuncia anticipada.** El líder deja de actuar como tal, y responde `NODE_NOT_LEADER`, si no ha
     renovado su arrendamiento antes de que pase el TTL menos un margen, medido con su reloj monótono. Así
     suele renunciar antes de que se elija otro. No es suficiente por sí sola, porque una pausa del
     proceso puede saltarse la comprobación; por eso existen las dos defensas anteriores.
- **Copia de seguridad** con `etcdctl snapshot save`, que el script de despliegue lleva a S3 (ADR 0035).
- La forma de guardar el modelo de metadatos en claves y el cliente de Python se deciden en la etapa 4.

## Consecuencias
- **Se gana:** se cumplen la §4.2 y G2 sin tocar el consenso. etcd es el almacén de Kubernetes, y trae la
  copia y la restauración hechas.
- **Se pierde:**
  - Un proceso más en cada servidor de metadatos, y un viaje de red entre el servidor de metadatos y
    etcd en cada operación.
  - El estado de los metadatos ya no vive en la memoria del líder, como describía la §3.3 de la fase I:
    se guarda en claves de etcd. El estado de vida de los nodos de datos sí sigue en la memoria del
    líder, así que el modo seguro (ADR 0031) se mantiene.
  - Al caer el líder de DFSha hay que esperar a que caduque su arrendamiento de elección, y además a la
    elección de etcd si cae también su miembro. E7 lo mide.
- **Límites de etcd que condicionan el diseño:** peticiones de hasta 1,5 MiB, transacciones de hasta 128
  operaciones y una base de datos de 2 GiB, todo por defecto.
- **Cambia el despliegue:** cada servidor de metadatos tiene dos contenedores. El ADR 0040 sustituye al 0027.
- **La fase I ya está entregada** y no se modifica. Este cambio entra en la tabla de cambios del informe
  (ADR 0006).
