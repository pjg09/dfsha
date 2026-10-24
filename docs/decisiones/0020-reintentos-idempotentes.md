# 0020 · Reintentos: al menos una vez, con operaciones idempotentes

- **Estado:** Aceptada
- **Fecha:** 2026-10-23
- **Requisitos relacionados:** RNF2, RNF3; C13, C14, C15, C22

## Contexto
Que venza un plazo no dice si la operación se ejecutó (C13). Reintentar algo que tiene efectos puede
duplicarlo, y un ID solo evita duplicados si el servidor recuerda los IDs que ya procesó (C14).

## Opciones consideradas
1. **Sin reintentos automáticos.** El usuario ve cada error transitorio.
2. **Reintentar sin identificador.** Produce duplicados: un `mkdir` doble, una confirmación doble…
3. **Al menos una vez, con operaciones idempotentes** (C15).

## Decisión
Opción 3.

**Escritura de bloques:** es idempotente por `block_id`. Si llega el mismo `block_id` con el mismo hash,
se responde OK sin volver a escribir; si llega con otro hash, se rechaza.

**Mutaciones de metadatos:**
- Llevan un `request_id`, un UUID que genera el cliente.
- El servidor guarda el `request_id` y su respuesta en el estado replicado, con un TTL de 10 min.
- Si llega un duplicado, devuelve la respuesta guardada.
- El *ack* se envía después de aplicar el efecto, cuando lo ha confirmado la mayoría.

**Lecturas:** son idempotentes por naturaleza.

**Reintentos:** con espera exponencial y un número máximo de intentos, y con plazo en cada llamada. Los
valores están en la configuración.

## Consecuencias
- **Se gana:** cualquier operación se puede reintentar sin peligro.
- **Se pierde:** el registro de `request_id` ocupa memoria, acotada por el TTL, y hay que dimensionarlo.
- **Límite:** un duplicado que llegue después del TTL no se detecta. Por eso el cliente no reintenta más
  allá de esos 10 minutos.
