# 0047 · Vigilante de inactividad en las transferencias del cliente

- **Estado:** Aceptada
- **Fecha:** 2026-11-08
- **Requisitos relacionados:** RNF2, RNF3; fase I §8.3, §11.4 (escenario 4) y §13.2

## Contexto
En E6, el 2026-11-07, se congeló un nodo de datos con `docker pause`. El proceso deja de ejecutarse, pero el núcleo de la instancia sigue aceptando conexiones TCP. El cliente, con la conexión ya abierta, no recibía ningún error: esperaba los 120 s del plazo de transferencia (`TRANSFER_TIMEOUT_S`) por cada bloque que leía de ese nodo. Dentro de un mismo `get` lo volvía a probar con otros bloques, y hubo lecturas de 120, 240 y 360 s (`bench/resultados/2026-11-07-e6.md`). La §11.4 pide pasar a otra réplica cuando una no responde.

El plazo de transferencia limita la duración total de una llamada, no el tiempo sin progreso. Un nodo parado rechaza la conexión y el cambio de réplica es inmediato; uno congelado, no.

La corrección salió en la `v0.13.1` (`80419b9`) sin ADR. Este ADR la documenta después: añade un parámetro configurable con un valor por defecto, y un término nuevo.

## Opciones consideradas
1. **Un vigilante de inactividad por transferencia en el cliente:** si pasan N s sin ningún mensaje del nodo (lectura) o sin que gRPC pida el trozo siguiente (escritura), se cancela la llamada y se prueba otra réplica, o se reserva el bloque en otros nodos.
2. **Bajar el plazo de transferencia** a unos pocos segundos. Ese plazo cuenta la duración total, no el progreso, así que también cortaría transferencias lentas pero sanas, como las de E4 con varios clientes compartiendo la red.
3. **El keepalive de gRPC** (pings HTTP/2; si no llega la respuesta en el plazo, se cierra la conexión) [grpc-keepalive]:
   - Es solo de conexión, y no dice nada de un nodo cuyo transporte responde pero cuya lectura o escritura no avanza.
   - Exige configurar también los servidores: por defecto rechazan los pings más frecuentes que uno cada 5 min y cierran la conexión con `GOAWAY too_many_pings`.
   - grpc.io desaconseja configurarlo en el cliente muy por debajo de un minuto, cuando aquí harían falta unos 10 s.
   - No se probó en DFSha.

## Decisión
Opción 1, como está en la `v0.13.1`:
- **Parámetro:** `TRANSFER_INACTIVITY_S` del cliente, 10 s por defecto. Con trozos de 1 MiB, 10 s sin ningún mensaje es una tasa por debajo de 0,1 MB/s, muy por debajo de cualquier transferencia sana medida (E1–E5).
- **Lectura:** el vigilante se reinicia con cada mensaje de `ReadBlock`. Si salta, el cliente prueba la réplica siguiente. Dentro de un mismo `get`, las réplicas que ya fallaron se prueban las últimas.
- **Escritura:** el vigilante se reinicia cada vez que gRPC pide el trozo siguiente de `WriteBlock`. Si salta, el cliente trata a la primaria como inalcanzable y repite el bloque excluyéndola (ADR 0044).
- **El plazo de transferencia se mantiene** (120 s en el cliente) como tope de una llamada que sí avanza.

## Consecuencias
- **Se gana:** con un nodo congelado, la lectura más lenta baja de 360,7 a 12,1 s, sin lecturas fallidas, en 5 repeticiones de E6 con la `v0.13.1` (`bench/resultados/2026-11-07-e6.md`). La detección y la re-replicación del líder no cambian.
- **Se pierde:** un hilo más por transferencia en curso, que comprueba el reloj cada 0,5 s.
- **Límite:** en una escritura, el vigilante sigue activo mientras el cliente espera la respuesta de la primaria. La primaria responde en cuanto tiene W réplicas, así que una secundaria congelada no lo dispara. Pero con dos fallos a la vez (una secundaria caída y la otra congelada), la primaria espera hasta 60 s a la congelada. El cliente cancela a los 10 s y excluye a la primaria, que está sana. El bloque se repite en otros nodos y la escritura sigue; solo se culpa al nodo equivocado en esa reserva.
- **Límite:** un nodo con el disco o la red degradados por debajo de 0,1 MB/s durante 10 s se trata como caído para esa transferencia. Es lo deseado.
- **La fase I ya está entregada** y no se modifica: el parámetro entra en la tabla de cambios del informe (ADR 0006), junto a los de la Tabla 37.
