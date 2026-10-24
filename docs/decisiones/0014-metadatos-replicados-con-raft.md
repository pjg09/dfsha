# 0014 · Servidor de metadatos replicado con Raft en tres nodos

- **Estado:** Aceptada
- **Fecha:** 2026-10-23
- **Requisitos relacionados:** RNF1, RNF2, RNF3; aclaración A7; C4, C6, C9, C20

## Contexto
El servidor de metadatos guarda el espacio de nombres, las versiones de archivo, las ubicaciones, los
arrendamientos, el registro de nodos y los `request_id`. Si cae, los bloques siguen existiendo pero nadie
puede encontrarlos (C6). La guía de HDFS 1.2.1 reconoce que su NameNode es un SPOF que exige intervención
manual. El objetivo es no simplificar RNF2 (A7), y el presupuesto lo permite.

## Opciones consideradas
1. **Un servidor con log persistente y reinicio.** Es barato, pero el SPOF queda declarado, lo que
   equivale a simplificar RNF2.
2. **Primario y respaldo con copia del log, sin consenso.** Una partición de red puede dejar dos
   primarios aceptando escrituras a la vez (cerebro dividido).
3. **Tres nodos con consenso Raft:** un líder elegido por mayoría y un log replicado.

## Decisión
Opción 3, con los nodos `metadata-1`, `metadata-2` y `metadata-3`.
- Todo cambio de metadatos es una entrada del log replicado, y se aplica cuando la confirma la mayoría (2 de 3).
- El líder atiende escrituras y lecturas. Las lecturas son linealizables, como exige G2 del ADR 0010.
- Un seguidor que recibe una petición responde con el nombre del líder.
- Se toman instantáneas periódicas para acotar el tamaño del log.
- **Raft no se implementa a mano.** Se usará una implementación existente, por ejemplo etcd como almacén o
  una librería de Python como PySyncObj. La elección va en un ADR de la fase II, después de probarlas.

## Consecuencias
- **Se gana:** tolera la caída de un servidor de metadatos sin perder escrituras confirmadas, así que
  desaparece el SPOF.
- **Se pierde:**
  - Cada escritura de metadatos añade un viaje de ida y vuelta hasta la mayoría.
  - Con dos servidores caídos no hay líder ni operaciones de metadatos, ni siquiera `open()`. Solo pueden
    seguir las lecturas ya abiertas, con las ubicaciones en caché, mientras no caduquen sus tokens de bloque (C6).
  - Durante una elección de líder no hay servicio de metadatos. Se mide en el ADR 0028.
  - Hacen falta tres instancias.
- **Pendiente:** la implementación de Raft (fase II) y sus tiempos de elección.
- **Términos nuevos en el glosario:** líder, seguidor, log replicado e instantánea.
