# 0017 · Ubicación de réplicas y reparto de bloques

- **Estado:** Aceptada
- **Fecha:** 2026-10-23
- **Requisitos relacionados:** RNF1, RNF4, RNF5; C5, C20

## Contexto
RNF4 exige repartir entre varios nodos tanto los archivos como los bloques de un mismo archivo. Al haber
una sola zona de disponibilidad (ADR 0015), no hay racks ni zonas que tener en cuenta.

## Opciones consideradas
1. **Aleatoria uniforme.** Es simple, pero con pocos bloques puede quedar desequilibrada.
2. **Por espacio libre, con desempate aleatorio y rotación de la primaria.**
3. **Hash consistente** (como Chord). Elimina el estado de ubicación, pero mueve datos cada vez que cambia
   un nodo. Los metadatos ya guardan las ubicaciones, así que no aporta nada.

## Decisión
Opción 2.

**Escritura:**
- Para cada bloque, el servidor de metadatos elige R nodos de datos vivos y distintos: los que tienen más
  espacio libre según su último latido, con desempate aleatorio.
- Ningún nodo guarda dos réplicas del mismo bloque.
- La réplica primaria rota entre bloques consecutivos.

**Lectura:**
- El cliente pide todas las ubicaciones en `open()` (C20).
- Lee bloques distintos en paralelo, cada uno de una réplica elegida al azar.
- Si la réplica falla o el hash no coincide, pasa a otra.

## Consecuencias
- **Se gana:** la carga de escritura y de lectura se reparte entre todos los nodos de datos.
- **Se pierde:**
  - No hay conciencia de zona ni de rack.
  - Lo ya escrito no se rebalancea, igual que en HDFS 1.2.1: un nodo nuevo solo recibe bloques nuevos.
- **Pendiente:** el grado de paralelismo del cliente es un parámetro que se ajusta con los experimentos (ADR 0028).
