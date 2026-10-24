# 0012 · Replicación: factor 3, confirmación por mayoría y reenvío desde la réplica primaria

- **Estado:** Aceptada
- **Fecha:** 2026-10-23
- **Requisitos relacionados:** RNF2, RNF3, RNF5, §4.2 (escenario 2), §7; C8, C9, C10, C11

## Contexto
Hay que decidir tres cosas: cuántas réplicas tiene cada bloque, cuándo se considera escrito y cómo llega
a cada réplica. Los bloques son inmutables (ADR 0009).

## Opciones consideradas
**Factor de replicación y confirmación:**
1. **R = 3, W = 3.** Máxima durabilidad al confirmar, pero la réplica más lenta marca la latencia y una
   caída bloquea las escrituras hasta que se detecta.
2. **R = 3, W = 2 (mayoría).**
3. **R = 2.** Ocupa menos disco, pero tolera un solo fallo sin margen.

**Propagación:**
- **a) Cadena** (HDFS). El cliente sube el bloque una vez, pero la latencia suma los saltos.
- **b) El cliente envía a todas las réplicas.** El cliente sube el bloque tres veces.
- **c) La réplica primaria reenvía en paralelo.** El cliente sube el bloque una vez, y la latencia es la
  de las réplicas más rápidas.

## Decisión
`replication_factor` = 3 y `write_quorum` = 2 (⌊3/2⌋+1), con propagación c.

**Escritura de un bloque:**
- El servidor de metadatos asigna tres nodos de datos. El primero es la réplica primaria.
- La primaria recibe el bloque del cliente, lo escribe, lo reenvía en paralelo a las dos secundarias y
  responde OK cuando al menos dos réplicas, ella incluida, lo tienen en disco con el SHA-256 verificado.
- La tercera réplica termina en segundo plano. Si falla, el bloque queda con menos réplicas y lo repara la
  re-replicación (ADR 0018).

**Lectura:** basta una réplica, porque el bloque es inmutable y su hash se verifica (ADR 0013). No hay
quórum de lectura.

**Escenario 2 (una réplica desconectada durante una escritura):**
- La escritura se confirma con dos réplicas.
- Los metadatos solo anuncian las réplicas que confirmaron, así que ningún lector intenta leer la versión
  nueva de la réplica desconectada.
- Los bloques antiguos que tenga esa réplica siguen siendo correctos para la versión antigua.
- Cuando vuelve, su informe de bloques dispara la resincronización (ADR 0018).

## Consecuencias
- **Se gana:**
  - La latencia es la de las dos réplicas más rápidas (C10).
  - Con un nodo de datos caído se sigue escribiendo, sin esperar a que se detecte la caída.
- **Se pierde:**
  - Durante un rato hay dos copias, y una segunda caída en ese intervalo deja una.
  - La primaria envía el doble de tráfico de salida.
  - Si la primaria cae a mitad de un bloque, el cliente lo repite con otra asignación (ADR 0020).
- **Medición:** W = 2 frente a W = 3 (ADR 0028).
- **Glosario:** se redefine «réplica primaria» como la réplica que recibe el bloque del cliente y lo
  reenvía. Aquí no ordena escrituras, porque los bloques no cambian.
