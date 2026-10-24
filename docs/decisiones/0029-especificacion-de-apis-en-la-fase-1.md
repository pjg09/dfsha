# 0029 · Especificación de las APIs en el documento de la fase I

- **Estado:** Aceptada
- **Fecha:** 2026-10-23
- **Requisitos relacionados:** §4.1 (protocolos y APIs, con ejemplos de mensajes y respuestas de error), §4.3; aclaraciones A3 y A4

## Contexto
§4.1 pide especificar las APIs entre el cliente, los controladores y los nodos de datos, con ejemplos de
mensajes y de respuestas de error. Según A4, todo va dentro del documento, sin anexos aparte y sin límite de páginas.

## Opciones consideradas
1. **Describir las operaciones en prosa.** Es ambiguo y no se puede contrastar con el código.
2. **Extractos `.proto`, una tabla de errores y ejemplos de mensajes.**
3. **Los `.proto` completos y nada más.** Es preciso, pero no explica los flujos.

## Decisión
Opción 2, y además los `.proto` completos al final del documento:
- **Servicios** del paquete `dfsha.v1`, uno por rol (`convenciones.md` §2):
  - `MetadataService`, que usan el cliente y los nodos de datos;
  - `DataNodeService`, que usan el cliente y los demás nodos de datos.
- **Errores:** una tabla con el código de estado gRPC, el código de motivo y la operación donde aparece.
- **Ejemplos:** una petición y su respuesta en cada flujo: carga, recuperación, modificación parcial,
  conflicto de cerrojo, caída de una réplica, redirección al líder, escritura rechazada en modo seguro
  (ADR 0031) y réplica corrupta (ADR 0032).
- **Nombres:** con los verbos de `convenciones.md` §3. Si hace falta un verbo nuevo (por ejemplo, para
  renovar un arrendamiento), se añade antes a las convenciones.

## Consecuencias
- El contrato del documento es el punto de partida de `proto/` en la fase II, y cualquier cambio posterior va con su ADR (ADR 0006).
- **Se pierde:** el documento se alarga. Lo permite A4.
