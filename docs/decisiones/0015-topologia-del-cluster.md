# 0015 · Topología del clúster: 3 servidores de metadatos, 5 nodos de datos y 1 cliente

- **Estado:** Aceptada
- **Fecha:** 2026-10-23
- **Requisitos relacionados:** RNF1, RNF2, RNF4, §5.1, §5.2; C17, C26, C28

## Contexto
- Raft necesita tres servidores de metadatos (ADR 0014).
- Con R = 3 (ADR 0012), C17 exige más nodos de datos que réplicas para poder demostrar la re-replicación.
- El experimento de escalabilidad quiere variar el número de nodos de datos (ADR 0028).
- Hay 50 USD de crédito en el Learner Lab y otros 50 USD disponibles.
- Una sola zona de disponibilidad es aceptable.

## Opciones consideradas
1. **3 + 4 + 1 = 8 instancias.** Es el mínimo que permite re-replicar tras un fallo.
2. **3 + 5 + 1 = 9 instancias.** Permite re-replicar tras dos fallos seguidos y medir la escalabilidad con 3, 4 y 5 nodos de datos.
3. **Servidor de metadatos y nodo de datos en la misma instancia.** Ahorra instancias, pero una caída
   tumba dos roles a la vez (fallos correlacionados).

## Decisión
Opción 2, en una sola zona de `us-east-1`:

| Rol | Hosts | Tipo de instancia |
|---|---|---|
| Servidor de metadatos | `metadata-1` a `metadata-3` | t3.small (2 GiB, margen para Raft y Docker) |
| Nodo de datos | `datanode-1` a `datanode-5` | t3.micro |
| Cliente | `client-1` | t3.micro |

Las pruebas de concurrencia lanzan varios procesos cliente desde `client-1`. Si hace falta y hay cupo, se
añade `client-2`.

**Coste estimado,** con precios de lista de `us-east-1` sin comprobar en el lab:
- Cómputo: 3 × 0,0208 + 6 × 0,0104 ≈ 0,125 USD/h, unos 12,5 USD por cada 100 h de uso.
- Volúmenes EBS: 9 × 8 GiB raíz + 5 × 10 GiB de datos ≈ 122 GiB × 0,08 USD/GiB-mes ≈ 10 USD/mes.

## Consecuencias
- **Se gana:**
  - Re-replicación demostrable incluso tras dos caídas.
  - Una curva de escalabilidad con tres puntos.
  - Cada rol en su propia instancia.
- **Se pierde:**
  - La caída de la zona de disponibilidad no se tolera; queda declarado como límite.
  - Los volúmenes EBS se cobran aunque las instancias estén paradas.
- **Sin comprobar:** el tope de instancias simultáneas y los tipos permitidos en el Learner Lab. Si el
  tope es menor de 9, se baja a 4 nodos de datos (opción 1).
