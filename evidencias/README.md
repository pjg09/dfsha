# Evidencias

Salida registrada de las pruebas mínimas (§5.2 del enunciado), de los experimentos y de los fallos
provocados. Cuándo se registra, con qué formato y qué se quita antes de commitear: [ADR 0036](../docs/decisiones/0036-evidencias-y-material-del-informe.md).
Las mediciones de los experimentos están en `bench/resultados/` (ADR 0028).

## Índice

Una fila sin evidencia es una evidencia que falta.

### Pruebas mínimas (§5.2)

| Prueba | Qué tiene que verse | Evidencia | Estado |
|---|---|---|---|
| Carga y recuperación | Archivo grande repartido en varios nodos de datos; el archivo recuperado tiene el mismo hash | [`2026-11-07-carga-y-recuperacion`](2026-11-07-carga-y-recuperacion/) | Hecha |
| Acceso RF3 | `read()` y `write()` con la semántica declarada (fase I, §7) | — | Pendiente |
| Concurrencia | Dos clientes sobre el mismo archivo y bloque; resultado según los arrendamientos (fase I, §11.1) | — | Pendiente |
| Replicación y fallos | Caída de un nodo de datos; lectura y re-replicación según las garantías (fase I, §9 y §11.3) | — | Pendiente |
| Consistencia | Réplica retrasada o desconectada durante una escritura (fase I, §11.2) | — | Pendiente |
| Seguridad | Acceso autorizado y denegado; TLS en el canal y bloques cifrados en disco (fase I, §10) | [`2026-11-07-seguridad`](2026-11-07-seguridad/) | Hecha |
| Rendimiento | Latencia y tasa de transferencia en al menos dos condiciones (experimentos) | — | Pendiente |

### Experimentos (ADR 0028)

| Exp. | Variable | Evidencia | Estado |
|---|---|---|---|
| E1 | Tamaño del archivo | — | Pendiente |
| E2 | Número de nodos de datos | — | Pendiente |
| E3 | W = 2 frente a W = 3 | — | Pendiente |
| E4 | Clientes concurrentes | — | Pendiente |
| E5 | Tamaño de bloque | — | Pendiente |
| E6 | Caída de un nodo de datos | — | Pendiente |
| E7 | Caída del líder de metadatos | — | Pendiente |
| E8 | Con y sin cifrado | — | Pendiente |
| E9 | Arranque en frío | — | Pendiente |

### Otros fallos provocados

| Fallo | Qué tiene que verse | Evidencia | Estado |
|---|---|---|---|
| Pérdida del estado de etcd en los tres servidores de metadatos | Restaurar la copia de S3 recupera lo anterior a ella; el nuevo líder tiene mayor época y los nodos de datos lo aceptan (§4.2, §11.3) | [`2026-11-07-restauracion-de-metadatos`](2026-11-07-restauracion-de-metadatos/) | Hecha |

## Plantilla del `README.md` de cada evidencia

```markdown
# <escenario>

- **Fecha:** AAAA-MM-DD
- **Commit y versión:** `abc1234` · vX.Y.Z
- **Entorno:** aws · hosts implicados
- **Cubre:** prueba de §5.2 o experimento
- **Resultado esperado:** lo que dice el diseño, con su sección de `fase-1.md` o su ADR
- **Resultado obtenido:** coincide o no coincide, y por qué

## Comandos
Los comandos exactos, en orden.

## Archivos
- `salida.txt`: …
```
