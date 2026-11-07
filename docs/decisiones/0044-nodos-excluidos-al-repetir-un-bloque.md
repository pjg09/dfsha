# 0044 · Nodos excluidos al repetir un bloque

- **Estado:** Aceptada
- **Fecha:** 2026-11-07
- **Requisitos relacionados:** RNF2, RNF3; fase I §9.2 y §11.3 (escenario 3); Anexo A (`AllocateBlocksRequest`)

## Contexto
Cuando un bloque falla al escribirse, el cliente vuelve a llamar a `AllocateBlocks` para ese índice, y la §11.3 (paso 3) dice que recibe «un `block_id` nuevo y otros tres nodos de datos». La implementación no lo garantizaba:
- Un nodo de datos que acaba de caer sigue contando como vivo para el líder hasta 9 s, hasta que pasa a sospechoso (§9.2).
- La ubicación elige primero a los nodos con más espacio libre (§4.3), y al reservar un solo bloque la primaria es siempre la primera de la lista.

En AWS, el 2026-11-07, `datanode-4` cayó durante una carga de 1 GiB con el mayor espacio libre del clúster. El líder lo volvió a dar como primaria en las cuatro reservas del bloque 58, el cliente agotó sus intentos y la carga falló (`evidencias/2026-11-07-escenario-3/salida-2-mismo-nodo.txt`).

`AllocateBlocksRequest` no tiene forma de decirle al líder qué nodos fallaron.

## Opciones consideradas
1. **Un campo nuevo en `AllocateBlocksRequest`** con los nodos que ya fallaron con esos bloques; el líder no los elige en esa reserva.
2. **Que el aviso del cliente marque el nodo como sospechoso** para todos. Un cliente podría sacar del reparto a nodos sanos, el mismo abuso que la §8.5 evita con las réplicas corruptas (S5).
3. **Que el cliente espere más de 9 s entre intentos.** Hace lentas todas las cargas con un nodo caído y sigue sin garantizar otros nodos.
4. **Repetir con la misma reserva cambiando la primaria.** Evita una primaria caída, pero no sirve si fallan dos de las tres réplicas, y no cambia de nodos.

## Decisión
Opción 1. `AllocateBlocksRequest` gana el campo `excluded_datanode_addrs = 5`.
- **Qué nodos pone el cliente:**
  - Si no pudo hablar con la primaria, la primaria.
  - Si la primaria respondió `QUORUM_NOT_REACHED`, las secundarias que no guardaron el bloque. La primaria las devuelve en los metadatos del error (`failed_addrs`), dentro del modelo de errores que ya existe.
  - En cualquier otro caso, ninguno.
- **Alcance:** los excluidos solo cuentan para esa reserva; el líder no los guarda ni los comparte.
- **Si no quedan W nodos sin los excluidos:** el líder responde `QUORUM_NOT_REACHED`, como ya hacía con menos de W nodos vivos.

## Consecuencias
- **Se gana:** al repetir un bloque, el cliente recibe otros nodos, como dice la §11.3, aunque el líder aún no sepa que el nodo cayó. Un cliente solo influye en sus propias reservas.
- **Se pierde:** el contrato cambia respecto al Anexo A. El campo es nuevo y opcional, así que un cliente que no lo envía se comporta como antes.
- **Límite:** si el cliente no llega a un nodo que está sano (un problema de su red), deja de pedirlo para ese bloque. Es lo correcto para esa escritura, y no afecta a nadie más.
- **La fase I ya está entregada** y no se modifica; el cambio entra en la tabla de cambios del informe (ADR 0006).
