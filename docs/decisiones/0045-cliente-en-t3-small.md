# 0045 · El cliente pasa a una t3.small para los experimentos

- **Estado:** Aceptada
- **Fecha:** 2026-11-07
- **Requisitos relacionados:** §5.2 (rendimiento); ADR 0028 (E4 y E5); fase I §3.6 (Tabla de instancias) y §12.3

## Contexto
La §3.6 fija `client-1` en una t3.micro: 2 vCPU y 908 MiB de RAM, con unos 514 MiB disponibles con Docker en marcha. Medido en AWS el 2026-11-07, con la `v0.12.0` y 4 transferencias en paralelo, un `put` de 1 GiB llega a 247 MiB y un `get` a 291 MiB. Basta para un cliente, pero no para dos experimentos del ADR 0028:
- **E5, bloques de 64 MiB:** cada transferencia en curso tiene en memoria el bloque en claro, el cifrado y los trozos recibidos, unas 3–4 veces el tamaño del bloque. Con 4 transferencias son unos 0,8–1 GiB.
- **E4, 8 clientes concurrentes:** aunque cada uno use una sola transferencia, la suma pasa de los 514 MiB.

Si el kernel mata el proceso por falta de memoria, el experimento no mide nada. Así murió el `get` de la primera ejecución de «Replicación y fallos».

## Opciones consideradas
1. **`client-1` en una t3.small** (2 vCPU, 2 GiB, la misma red), solo con este cambio.
2. **Menos transferencias en paralelo en los puntos que no caben.** Mezcla la variable del experimento con otra, y las comparaciones dejan de valer.
3. **Recortar los puntos:** quitar los bloques de 64 MiB y los 8 clientes. El ADR 0028 los fijó para sostener decisiones del diseño (§4.1 y §8.1).

## Decisión
Opción 1. `deploy.sh` crea `client-1` como t3.small, y la instancia actual se cambia de tipo (parar, cambiar y arrancar).

## Consecuencias
- **Se gana:** E4 y E5 se miden en sus condiciones, sin que la memoria del cliente las limite.
- **Se pierde:** E1 y la primera ejecución de E2 se midieron con la t3.micro; cada CSV anota el tipo de instancia del cliente en cada fila. Las comparaciones dentro de cada experimento siguen valiendo, porque usan siempre el mismo cliente. Las pruebas finales se repiten con la t3.small.
- **Coste:** la instancia más cara del clúster pasa a ser una más; el tope de 9 instancias no cambia.
- **La fase I ya está entregada** y no se modifica; el cambio de la §3.6 entra en la tabla de cambios del informe (ADR 0006).
