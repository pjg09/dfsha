# 0018 · Detección de fallos, re-replicación y recolección de basura

- **Estado:** Aceptada
- **Fecha:** 2026-10-23
- **Requisitos relacionados:** RNF2, §4.2 (escenario 2), §5.2 (replicación y fallos); C16, C17, C18

## Contexto
Con los valores por defecto, HDFS tarda unos 10,5 minutos en dar por muerto un nodo (C16): es demasiado
para un sistema de alta disponibilidad y para un vídeo de 10–15 minutos. La guía de HDFS 1.2.1 describe
los latidos, el informe de bloques y la re-replicación, y dice que el NameNode nunca inicia RPC: sus
órdenes viajan en la respuesta al latido.

## Opciones consideradas
**Umbrales de detección:**
- **Agresivos** (latido de 1 s, caído a los 5 s): detectan rápido, pero dan falsos positivos con la red lenta.
- **Los de HDFS:** el nodo tarda minutos en darse por muerto.
- **Intermedios.**

**Cómo llegan las órdenes al nodo de datos:**
- **a)** el servidor de metadatos llama al nodo de datos;
- **b)** van en la respuesta al latido, como en HDFS.

## Decisión
Umbrales intermedios y órdenes por la opción b.

**Latido y estados del nodo:**
- Cada nodo de datos envía un latido cada 3 s, con su espacio libre.
- **Sospechoso** tras 9 s sin latido: deja de recibir escrituras nuevas.
- **Caído** a los 30 s: se quita de las ubicaciones y se re-replican sus bloques.

**Re-replicación:**
- El servidor de metadatos elige una réplica viva como origen y un destino (ADR 0017).
- Envía la orden en la respuesta al latido del origen.
- El origen copia el bloque directamente al destino, por mTLS, y el destino avisa de que lo ha recibido.
- Primero se reparan los bloques con una sola réplica.

**Informe de bloques** (al darse de alta y cada 5 min):
- Los bloques que no pertenecen a ninguna versión viva ni a una escritura en curso reciben una orden de
  borrado: es la **recolección de basura**.
- Si hay réplicas de más, por ejemplo porque vuelve un nodo, se borran las que pasan de R.

**Nodo que vuelve:** se resincroniza con su informe de bloques. Sus bloques son inmutables, así que siguen
siendo válidos si su hash coincide.

## Consecuencias
- **Se gana:**
  - Una caída se detecta en 30 s.
  - La re-replicación es automática; con 5 nodos de datos y R = 3 se toleran dos caídas sucesivas.
- **Se pierde:**
  - Un falso positivo crea copias de más. Es inofensivo porque los bloques son inmutables, y las copias se borran después.
  - Durante esos 30 s, un cliente puede intentar leer del nodo caído; agota el plazo y pasa a otra réplica.
- **Pendiente:**
  - Ajustar los umbrales con los experimentos (ADR 0028).
  - La verificación periódica de los hashes en disco y la reparación de réplicas corruptas se deciden en el ADR 0032.
