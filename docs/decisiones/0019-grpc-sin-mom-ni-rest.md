# 0019 · gRPC en todas las interfaces, sin MOM ni API REST

- **Estado:** Aceptada
- **Fecha:** 2026-10-23
- **Requisitos relacionados:** §4.1 («REST, gRPC, TCP o MOM, según corresponda»), §7 (herramientas justificadas), RNF5, RNF6; C5, C15, C22, C23, C24

## Contexto
§4.1 pide elegir el protocolo de cada interfaz «según corresponda», y §7 pide justificar la elección. Las
interacciones de DFSha son estas:

| Interacción | Naturaleza |
|---|---|
| Cliente → servidor de metadatos (`open`, `lock`, `commit`, `ls`…) | Petición-respuesta. El cliente necesita la respuesta para seguir |
| Cliente ↔ nodo de datos | Transferencia de bloques de 16 MiB, en flujo |
| Réplica primaria → secundarias, y nodo → nodo al re-replicar | Transferencia en flujo |
| Nodo de datos → servidor de metadatos (latido, informe de bloques, bloque recibido) | Periódica. La respuesta lleva órdenes para el nodo |
| Entre servidores de metadatos | Consenso Raft, que aporta la implementación elegida (ADR 0014) |
| Trabajo en segundo plano (re-replicación, borrado) | Órdenes dirigidas a un nodo concreto, derivadas del estado de los metadatos |

## Opciones consideradas
1. **REST/JSON (FastAPI).** Legible y fácil de probar con `curl`. Pero los bloques binarios van en base64
   (un 33 % más de datos) o en multipart, no hay contrato tipado ni flujo bidireccional estándar, y los
   plazos hay que programarlos a mano.
2. **gRPC.** Protobuf binario y flujos sobre HTTP/2; contrato `.proto` con código generado; plazos, códigos
   de estado y TLS/mTLS incluidos.
3. **MOM (RabbitMQ) para el trabajo en segundo plano.** Desacopla en el tiempo, pero:
   - añade un broker, que es otro proceso, otra instancia y otro SPOF, salvo que se monte en clúster de tres;
   - las órdenes van a un nodo concreto, así que no hay consumidores que compitan (C24);
   - la cola sería una segunda fuente de verdad, además de los metadatos.
4. **TCP propio.** Máximo control, pero obliga a reinventar el enmarcado de mensajes, los errores y TLS.

## Decisión
- gRPC en todas las interfaces, con plazo en cada llamada.
- El trabajo en segundo plano viaja en la respuesta al latido (ADR 0018), no por un MOM.
- No hay API REST.

## Consecuencias
- **Se gana:**
  - Un solo stack para todo.
  - Contratos versionados en `dfsha.v1`.
  - Errores con los códigos estándar de las convenciones.
- **Se pierde:**
  - No se puede usar desde un navegador ni con `curl`; para inspeccionar se usa `grpcurl`.
  - No hay desacoplamiento temporal: si se pierde una orden, no queda guardada en una cola. Se vuelve a
    calcular a partir del estado de los metadatos en el siguiente latido (reconciliación).
- **Cuándo revisarlo:** si aparecen consumidores de eventos que necesiten difusión, como una auditoría o
  notificaciones a varios destinatarios, un MOM con tópicos tendría sentido (C24).
