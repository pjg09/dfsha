# 0013 · Confirmación atómica de archivos y escrituras interrumpidas

- **Estado:** Aceptada
- **Fecha:** 2026-10-23
- **Requisitos relacionados:** RF2, RF3, RNF3, §4.2 (escenario 3), §7; C13, C15, C18, C25

## Contexto
En el escenario 3, un nodo falla después de recibir parte de un bloque, y hay que evitar que se publique
un archivo incompleto. §7 menciona hashes, validaciones y escrituras atómicas.

## Opciones consideradas
1. **Publicar bloque a bloque.** El archivo es visible mientras se escribe, así que un lector puede ver un
   archivo a medias.
2. **Área temporal en el cliente hasta tener el archivo entero** (HDFS 1.2.1). La propia guía de HDFS
   advierte que el archivo se pierde si algo cae antes de cerrarlo, y ocupa disco en el cliente.
3. **Dos fases.** Los bloques van al área temporal de los nodos de datos, y después la versión se confirma
   de forma atómica en los metadatos.

## Decisión
Opción 3, con estos pasos:
1. **`AllocateBlocks`.** El servidor de metadatos registra una escritura en curso, bajo el arrendamiento
   (ADR 0011), y devuelve los `block_id`, sus ubicaciones y los tokens de bloque (ADR 0022).
2. **Escritura en cada réplica.** El nodo de datos, sea la primaria o una secundaria:
   - escribe en el área temporal y hace `fsync`;
   - verifica el `block_sha256` que envió el cliente;
   - renombra el bloque de forma atómica al almacén de bloques.

   Si el hash no coincide, descarta el bloque y responde `ABORTED` con el motivo `BLOCK_CORRUPTED`.
3. **Aviso al servidor de metadatos.** Cada nodo de datos informa de cada bloque recibido, de modo que el
   servidor sabe cuántas réplicas hay sin fiarse del cliente.
4. **`CommitFile`.** Se acepta solo si todos los bloques nuevos tienen al menos W réplicas avisadas y el
   arrendamiento sigue vigente. La versión nueva se publica con **una sola** entrada del log replicado (ADR 0014).
5. **Abortar.** Si el arrendamiento caduca o el cliente llama a `AbortFile`, la escritura en curso se
   descarta. Sus bloques quedan huérfanos y los borra la recolección de basura (ADR 0018).

**Escenario 3:**
- El bloque a medias se queda en el área temporal: nunca se renombra y no cuenta como réplica.
- El cliente repite ese bloque en otros nodos de datos.
- El archivo no se publica hasta que todos sus bloques tienen W réplicas.

## Consecuencias
- **Se gana:** hay un único punto de visibilidad, así que ningún lector ve un archivo incompleto (G4 del ADR 0010).
- **Se pierde:**
  - Los bloques huérfanos ocupan disco hasta la recolección de basura.
  - Una carga larga depende de que el cliente renueve el arrendamiento.
- **Recordatorio (§7):** el hash detecta corrupción, pero no coordina escrituras. Eso lo hace el ADR 0011.
