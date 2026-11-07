# Escenario 4: el cliente desconoce la ubicación física de los bloques

- **Fecha:** 2026-11-07
- **Commit y versión:** `8848cf8` · v0.12.0 (imágenes `0.12.0` en ECR); líder `metadata-1`
- **Entorno:** aws · `client-1`
- **Cubre:** escenario 4 de la fase I §11.4 (condición de cierre de la etapa 9) y RNF7
- **Resultado esperado:**
  - El cliente solo se configura con los servidores de metadatos.
  - Si pregunta a un seguidor, recibe `UNAVAILABLE` + `NODE_NOT_LEADER` con la dirección del líder, repite allí y lo recuerda.
  - Las ubicaciones de los bloques son nombres de nodos, nunca IP, y el sistema operativo los resuelve con `/etc/hosts`.
- **Resultado obtenido:** coincide.
  - **Configuración:** la única variable con direcciones del contenedor `client-1` es `DFSHA_METADATA_ADDRS=metadata-1:50051,metadata-2:50051,metadata-3:50051`.
  - **Redirección:** `metadata-3` y `metadata-2` responden `UNAVAILABLE [NODE_NOT_LEADER]` con `leader_addr = metadata-1:50051`. Con la lista en orden inverso, empezando por un seguidor, el cliente lista `/` y queda recordando a `metadata-1:50051`.
  - **Ubicaciones:** `GetBlockLocations` devuelve `datanode-1:50052`, `datanode-2:50052`…
  - **Resolución de nombres:** `datanode-2` se resuelve en `client-1` con el bloque de `/etc/hosts` que escribe `deploy.sh` a partir de las IP privadas. Ninguna IP está en el repositorio salvo en esta evidencia (ADR 0036).

## Comandos
```bash
evidencias/2026-11-07-escenario-4/ejecutar.sh > evidencias/2026-11-07-escenario-4/salida.txt 2>&1
```

## Archivos
- `ejecutar.sh`: la prueba.
- `descubrimiento.py`: consultas directas a cada servidor de metadatos, redirección del cliente y ubicaciones.
- `salida.txt`: salida completa.
