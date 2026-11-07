# Evidencias

Salida registrada de las pruebas mínimas (§5.2 del enunciado), de los experimentos y de los fallos
provocados. Cuándo se registra, con qué formato y qué se quita antes de commitear: [ADR 0036](../docs/decisiones/0036-evidencias-y-material-del-informe.md).
Las mediciones de los experimentos están en `bench/resultados/` (ADR 0046).

## Índice

Una fila sin evidencia es una evidencia que falta.

### Pruebas mínimas (§5.2)

| Prueba | Qué tiene que verse | Evidencia | Estado |
|---|---|---|---|
| Carga y recuperación | Archivo grande repartido en varios nodos de datos; el archivo recuperado tiene el mismo hash | [`2026-11-07-carga-y-recuperacion`](2026-11-07-carga-y-recuperacion/) | Hecha |
| Acceso RF3 | `read()` y `write()` con la semántica declarada (fase I, §7) | [`2026-11-07-acceso-rf3`](2026-11-07-acceso-rf3/) | Hecha |
| Concurrencia | Dos clientes sobre el mismo archivo y bloque; resultado según los arrendamientos (fase I, §11.1) | [`2026-11-07-concurrencia`](2026-11-07-concurrencia/) | Hecha |
| Replicación y fallos | Caída de un nodo de datos; lectura y re-replicación según las garantías (fase I, §9 y §11.3) | [`2026-11-07-replicacion-y-fallos`](2026-11-07-replicacion-y-fallos/) | Hecha |
| Consistencia | Réplica retrasada o desconectada durante una escritura (fase I, §11.2) | [`2026-11-07-escenario-2`](2026-11-07-escenario-2/) | Hecha |
| Seguridad | Acceso autorizado y denegado; TLS en el canal y bloques cifrados en disco (fase I, §10) | [`2026-11-07-seguridad`](2026-11-07-seguridad/) | Hecha |
| Rendimiento | Latencia y tasa de transferencia en al menos dos condiciones (experimentos) | — | Pendiente |

### Experimentos (ADR 0046)

| Exp. | Variable | Evidencia | Estado |
|---|---|---|---|
| E1 | Tamaño del archivo | [`bench/resultados/2026-11-07-e1.md`](../bench/resultados/2026-11-07-e1.md) | Hecha |
| E2 | Número de nodos de datos | [`bench/resultados/2026-11-07-e2.md`](../bench/resultados/2026-11-07-e2.md) | Hecha |
| E3 | W = 2 frente a W = 3 | [`bench/resultados/2026-11-07-e3.md`](../bench/resultados/2026-11-07-e3.md) | Hecha |
| E4 | Clientes concurrentes | [`bench/resultados/2026-11-07-e4.md`](../bench/resultados/2026-11-07-e4.md) | Hecha |
| E5 | Tamaño de bloque | — | Pendiente |
| E6 | Caída de un nodo de datos | — | Pendiente |
| E7 | Caída del líder de metadatos | — | Pendiente |
| E8 | Con y sin cifrado | — | Pendiente |
| E9 | Arranque en frío | — | Pendiente |

### Despliegue

| Comprobación | Qué tiene que verse | Evidencia | Estado |
|---|---|---|---|
| Despliegue desde cero | `deploy.sh all` levanta los 9 hosts sin intervención y el clúster pasa la prueba de carga y recuperación (§3.6) | [`2026-11-07-despliegue-desde-cero`](2026-11-07-despliegue-desde-cero/) | Hecha |

### Otras comprobaciones

| Comprobación | Qué tiene que verse | Evidencia | Estado |
|---|---|---|---|
| Recolección de basura | Se borran los bloques de escrituras abortadas y de versiones sustituidas hace más de 10 min, y ninguno vivo (§8.4, §9.3) | [`2026-11-07-recoleccion-de-basura`](2026-11-07-recoleccion-de-basura/) | Hecha |
| Arranque en frío real | Al arrancar el lab, el clúster se levanta solo, elige líder, los nodos de datos se dan de alta y los datos siguen íntegros (§9.6; E9 lo mide en la etapa 10) | [`2026-11-07-arranque-en-frio`](2026-11-07-arranque-en-frio/) | Hecha |

### Otros fallos provocados

| Fallo | Qué tiene que verse | Evidencia | Estado |
|---|---|---|---|
| Pérdida del estado de etcd en los tres servidores de metadatos | Restaurar la copia de S3 recupera lo anterior a ella; el nuevo líder tiene mayor época y los nodos de datos lo aceptan (§4.2, §11.3) | [`2026-11-07-restauracion-de-metadatos`](2026-11-07-restauracion-de-metadatos/) | Hecha |
| Escenario 3: un nodo falla a mitad de un bloque | El bloque se repite en otros nodos, la carga termina y nadie la ve a medias; el nodo descarta su área temporal al volver (§11.3) | [`2026-11-07-escenario-3`](2026-11-07-escenario-3/) | Hecha |
| Escenario 4: el cliente desconoce la ubicación de los bloques | Solo con los servidores de metadatos: sigue `NODE_NOT_LEADER` y recibe nombres de nodos, no IP (§11.4, RNF7) | [`2026-11-07-escenario-4`](2026-11-07-escenario-4/) | Hecha |

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
