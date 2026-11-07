# 0042 · El nodo de datos envía su dirección al darse de alta

- **Estado:** Aceptada
- **Fecha:** 2026-11-07
- **Requisitos relacionados:** RNF7; ADR 0021 y 0029; convenciones §4 (puertos definidos en un único sitio)

## Contexto
En el Anexo A, `RegisterDataNodeRequest` lleva el `node_id` y el nombre de host, pero no el puerto. El
servidor de metadatos tiene que construir la dirección del nodo con un puerto de su propia configuración.
Así el puerto del nodo de datos queda definido en dos sitios: en el propio nodo (`DFSHA_DATANODE_ADDR`) y en
el servidor de metadatos. Las convenciones exigen definir cada puerto en un único sitio, y si los dos
valores no coinciden, los clientes reciben direcciones a las que no responde nadie. Además, las pruebas con
varios nodos de datos en una misma máquina, en puertos distintos, no se pueden representar.

## Opciones consideradas
1. **Mantener el contrato** y el puerto en la configuración del servidor de metadatos.
2. **Añadir la dirección completa a `RegisterDataNodeRequest`**, tal como la configura el nodo de datos.

## Decisión
Opción 2. `RegisterDataNodeRequest` lleva un campo nuevo, `string addr = 5`, con la dirección `host:puerto`
por la que los demás alcanzan al nodo, que es su `DFSHA_DATANODE_ADDR`. El servidor de metadatos la valida y
la guarda en el registro de nodos; deja de tener una variable con el puerto de los nodos de datos.

## Consecuencias
- **Se gana:** el puerto de un nodo de datos se define en un único sitio, y las pruebas pueden levantar
  varios nodos en una sola máquina.
- **Se pierde:** nada. Es un campo nuevo, compatible con el contrato anterior; el nombre de host sigue en el
  mensaje para los logs.
- **Sigue cumpliéndose RNF7:** la dirección es un nombre de host con su puerto, nunca una IP, y el cliente la
  recibe del servidor de metadatos en tiempo de ejecución (ADR 0021).
