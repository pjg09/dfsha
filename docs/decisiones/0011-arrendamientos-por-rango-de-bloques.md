# 0011 · Cerrojos: arrendamientos exclusivos por rango de bloques

- **Estado:** Aceptada
- **Fecha:** 2026-10-23
- **Requisitos relacionados:** RF3 (`lock()`), RNF3, RNF5, §4.2 (escenario 1), §7; C2, C13, C18

## Contexto
En el escenario 1, dos procesos escriben el mismo bloque a la vez. §7 permite que `lock()` sea una
primitiva explícita o un mecanismo equivalente documentado, y avisa de que la integridad no sustituye a la
coordinación. HDFS 1.2.1 admite un solo escritor por archivo. RNF5 pide concurrencia también dentro de un archivo.

## Opciones consideradas
1. **Sin cerrojos; control optimista puro.** Se comprueba la versión al confirmar. No hay estado de
   cerrojos, pero el proceso que pierde se entera al final, después de subir todos sus bloques.
2. **Cerrojo exclusivo por archivo.** Es simple, pero serializa a escritores que tocan bloques distintos (RNF5).
3. **Arrendamiento exclusivo por rango de bloques, más una comprobación de versión al confirmar.**

## Decisión
Opción 3.

**Cómo funciona el arrendamiento:**
- `lock(handle, block_range)` concede un arrendamiento exclusivo de escritura. Tiene un TTL de 30 s y se
  puede renovar.
- Lo gestiona el servidor de metadatos, y su estado se replica (ADR 0014). La caducidad la decide solo el
  servidor, así que los relojes de los clientes no influyen.
- El reemplazo pide el archivo entero. El anexado pide la cola, desde el último bloque.
- El rango se pide en una sola petición y se concede entero o nada. Así no hay esperas parciales y no
  pueden darse interbloqueos.
- Si el rango choca con otro arrendamiento, la respuesta es inmediata: `ABORTED` con el motivo
  `LOCK_CONFLICT`. El cliente puede reintentar con espera.

**Relación con las demás primitivas:**
- `write()` sin un arrendamiento previo lo pide de forma implícita.
- El `lock()` explícito sirve para agrupar varias escrituras.
- `unlock()` y `close()` lo liberan.

**Al confirmar,** el servidor comprueba dos cosas:
1. que el arrendamiento sigue vigente; si no, `LEASE_EXPIRED`;
2. que cada índice del rango conserva el `block_id` de la versión de la que se partió; si no, `VERSION_CONFLICT`.

**Lecturas:** no toman cerrojo (ADR 0010). No se ofrecen cerrojos compartidos.

**Escenario 1:**
1. El segundo proceso recibe `LOCK_CONFLICT`.
2. Si el primero muere, su arrendamiento caduca en 30 s como máximo, y el segundo puede escribir.
3. Si el primero reaparece después de la caducidad, su confirmación se rechaza.

## Consecuencias
- **Se gana:**
  - Concurrencia de escritura sobre bloques distintos del mismo archivo (RNF5).
  - Ningún cerrojo queda huérfano si muere un cliente.
- **Se pierde:**
  - Los anexados concurrentes se serializan.
  - Un escritor lento tiene que renovar el arrendamiento, lo que añade tráfico al servidor de metadatos.
- **Pendiente:** ajustar el TTL con los experimentos (ADR 0028).
