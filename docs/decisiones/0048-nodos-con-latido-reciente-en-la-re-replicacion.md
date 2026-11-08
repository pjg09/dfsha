# 0048 · Nodos con latido reciente en la re-replicación y plazo de 15 s por copia

- **Estado:** Aceptada
- **Fecha:** 2026-11-08
- **Requisitos relacionados:** RNF2, RNF3; fase I §9.2 y §9.3

## Contexto
En el escenario 2 repetido con la `v0.13.1` (`evidencias/2026-11-08-escenario-2/`), `datanode-5` se paró a las 04:43:08:
1. Al escribir, no guardó el bloque 0, que quedó con 2 réplicas.
2. A las 04:43:13 el líder ordenó copiarlo, y eligió como destino a `datanode-5`. Seguía vivo para el líder, porque un nodo no pasa a sospechoso hasta los 9 s sin latido (§9.2), y era el de más espacio libre.
3. La primaria vio fallar la copia a las 04:43:14, pero un nodo de datos no tiene forma de avisar al líder de que una orden falló.
4. El líder esperó los 60 s de `REPLICATION_TIMEOUT_S`, sin aviso de bloque recibido, y la volvió a ordenar hacia otro nodo a las 04:44:13.

El bloque pasó 61 s con 2 réplicas en lugar de 1 s. No incumple ninguna garantía, porque W = 2 se cumplió, pero alarga la ventana en la que otra caída lo dejaría con una sola réplica. Es el mismo patrón que el ADR 0044, esta vez en la re-replicación.

Lo mismo pasa con el origen: las órdenes viajan en la respuesta al latido (§9.2), así que una orden para un origen que ya no envía latidos no se entrega, y también espera los 60 s.

En esa misma prueba, las otras 107 copias tardaron desde la orden 1,3 s de mediana y 1,9 s como mucho, incluida la espera al latido siguiente del origen.

`REPLICATION_TIMEOUT_S` es una constante del código; no está en la Tabla 37.

## Opciones consideradas
1. **Origen y destino solo entre nodos con un latido reciente** (4,5 s, 1,5 veces el intervalo de 3 s). Es un cambio pequeño en el líder y no toca el contrato. No sirve si el nodo cae después de recibir la orden.
2. **Bajar `REPLICATION_TIMEOUT_S` de 60 a 15 s.** Cubre cualquier fallo de la copia, también después de la orden. 15 s es unas 8 veces la copia más lenta medida.
3. **Que el nodo de datos avise del fallo de una orden.** Es lo más exacto, pero cambia el contrato (un RPC o un campo nuevo, ADR 0044) para un caso que las dos anteriores ya acotan.

## Decisión
Opciones 1 y 2 juntas, aprobadas por Pedro el 2026-11-08:
- **Latido reciente:** el líder solo elige como origen o destino de una copia los nodos vivos cuyo último latido tiene 4,5 s o menos (`COPY_NODE_MAX_SILENCE_S`). Los demás siguen contando como vivos para todo lo demás (§9.2).
- **Plazo de una copia:** `REPLICATION_TIMEOUT_S` baja a 15 s. Una copia sin aviso de bloque recibido en ese tiempo se vuelve a ordenar.
- **Ubicación al escribir:** la de las escrituras del cliente no cambia, porque allí ya está el ADR 0044.

## Consecuencias
- **Se gana:** un nodo que acaba de caer deja de recibir copias en cuanto pasan 4,5 s sin latido, en vez de 9 s. Si aun así una copia falla, se repite en 15 s en vez de 60. En el caso del escenario 2, la ventana con 2 réplicas baja de 61 s a 1–2 s. En el peor caso, con el nodo cayendo justo después de un latido, son unos 15–18 s.
- **Se pierde:** un nodo sano con un latido retrasado más de 4,5 s se salta una pasada, y la siguiente, 3 s después, ya lo tiene en cuenta.
- **Se pierde:** si una copia tarda más de 15 s, porque haya muchas en cola o la red esté lenta, se ordena otra. Al llegar las dos, sobra una réplica, que la pasada siguiente borra (§9.3): se gasta tráfico, pero no se pierde nada.
- **Límite:** los 4,5 s suponen el intervalo de latido de 3 s. Si cambia, hay que cambiar también esta constante.
- **La fase I ya está entregada** y no se modifica; el cambio entra en la tabla de cambios del informe (ADR 0006).
