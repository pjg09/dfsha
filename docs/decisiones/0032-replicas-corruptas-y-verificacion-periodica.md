# 0032 · Réplicas corruptas y verificación periódica de bloques

- **Estado:** Aceptada
- **Fecha:** 2026-10-23
- **Requisitos relacionados:** RNF2, RNF3, §4.1 (integridad y recuperación); resuelve un pendiente del ADR 0018; C16, C18

## Contexto
Hoy la corrupción se detecta en dos momentos. Al escribir, el nodo de datos comprueba `block_sha256` antes
de confirmar (ADR 0013). Al leer, el cliente comprueba la etiqueta GCM (ADR 0024). Pero el diseño no dice qué
pasa a continuación. Una réplica corrupta que nadie repara cuenta como una de las R = 3 sin servir para
nada. Además, un bloque que nadie lee puede corromperse sin que nadie lo note, hasta que fallen también
las otras réplicas.

Hay un riesgo de seguridad. Si el servidor de metadatos borrara una réplica cada vez que un cliente dice
que está corrupta, un cliente malicioso podría hacer borrar réplicas sanas.

## Opciones consideradas
1. **Solo la detección actual.** No cuesta nada, pero la réplica corrupta se queda y nadie la repara.
2. **Reparar al detectarla al leer.** Repara lo que se lee, pero no lo que no se lee.
3. **Reparar al leer y, además, verificar periódicamente en segundo plano**, como el *block scanner* de HDFS.

## Decisión
Opción 3.

**Al leer:**
- El nodo de datos calcula `block_sha256` mientras envía el bloque. Si al terminar no coincide, cierra la
  llamada con `DATA_LOSS` + `BLOCK_CORRUPTED` e informa al servidor de metadatos con `ReportCorruptReplica`.
- Ante ese error, o si falla la etiqueta GCM, el cliente descarta lo recibido y pasa a otra réplica.
- Si la etiqueta GCM falla y el nodo no ha avisado de nada, el cliente también llama a `ReportCorruptReplica`.

**Quién puede marcar una réplica como corrupta:**
- Si el aviso viene del **nodo de datos** que la guarda, la réplica queda marcada como corrupta.
- Si viene de un **cliente**, no se marca nada. El servidor de metadatos ordena a ese nodo que la
  verifique (en la respuesta al latido, ADR 0018), y solo la marca si el nodo lo confirma. Así, un
  cliente no puede provocar el borrado de una réplica sana.

**Reparación** de una réplica marcada como corrupta:
1. Deja de entregarse en las ubicaciones.
2. Se re-replica desde una réplica sana, con la misma prioridad que un bloque con una sola réplica (ADR 0018).
3. Cuando la copia nueva está confirmada con el aviso de bloque recibido, se ordena borrar la corrupta.
4. **Nunca se borra la última réplica**, aunque esté corrupta. Si todas lo están, el bloque se da por
   perdido: las lecturas devuelven `DATA_LOSS` + `BLOCK_CORRUPTED` y queda registrado.

**Verificación periódica:**
- El verificador de bloques de cada nodo de datos recalcula el `block_sha256` de todos sus bloques una vez
  al periodo (`DFSHA_BLOCK_VERIFIER_PERIOD_S`, 1 día por defecto).
- Lee con un ritmo limitado (`DFSHA_BLOCK_VERIFIER_MAX_MB_S`, 4 MB/s por defecto) para no competir con el
  tráfico normal. A ese ritmo, un volumen lleno de 10 GiB se recorre en unos 45 min.
- Una discrepancia se trata igual que si la hubiera detectado el propio nodo al leer.

**En modo seguro** (ADR 0031) se aceptan los avisos, pero ni se re-replica ni se borra hasta salir.

## Consecuencias
- **Se gana:**
  - Una réplica corrupta se repara, venga de una lectura o de la verificación periódica.
  - Un cliente no puede hacer borrar réplicas sanas.
  - La evidencia es sencilla: corromper un bloque en disco a mano y ver cómo se detecta y se repara.
- **Se pierde:**
  - Hay que calcular el hash en cada lectura. En una t3 cuesta decenas de milisegundos por bloque de
    16 MiB (estimación sin medir; se mide junto con E8).
  - La verificación periódica consume E/S de disco y créditos de CPU.
  - Hay un RPC más en `MetadataService` y una orden más en la respuesta al latido.
- **Límite:**
  - Entre dos pasadas de la verificación periódica puede pasar hasta un día sin detectar un bloque
    corrupto que nadie lee.
  - Con R = 3, el bloque solo se pierde si las tres réplicas se corrompen antes de repararse.
- **Términos nuevos:**
  - en el glosario: réplica corrupta y verificador de bloques;
  - en `convenciones.md` §3: el verbo `report`.
