# 0027 · Despliegue en AWS: una imagen por rol y un contenedor por instancia

- **Estado:** Aceptada
- **Fecha:** 2026-10-23
- **Requisitos relacionados:** §5 («no basta una simulación local monolítica»), §5.1, §5.3 (instrucciones reproducibles); C26, C27, C29, C30

## Contexto
El producto final tiene que ejecutarse en varias instancias EC2 con comunicación real por red (§5.1). Las
sesiones del Learner Lab caducan y las credenciales también (C27), así que el despliegue tiene que poder
repetirse desde cero.

## Opciones consideradas
1. **Nativo** (systemd y un entorno virtual de Python). No necesita Docker, pero la reproducibilidad
   depende de cómo esté el sistema operativo de cada instancia.
2. **Docker:** una imagen por rol y un contenedor por instancia, lanzado con Docker Compose dentro de esa instancia.
3. **Un orquestador** (Kubernetes, ECS, Swarm). Es excesivo para instancias t3 y añade piezas que no
   están entre los requisitos.

## Decisión
Opción 2.

**Imágenes:** `dfsha-metadata`, `dfsha-datanode` y `dfsha-client`, con la versión como etiqueta.

**En cada instancia** hay un `compose.yaml` mínimo, con un solo servicio, el de su rol, que declara:
- red del host;
- el volumen de datos (ADR 0026);
- certificados y secretos montados desde fuera del repositorio;
- reinicio automático.

**Script de despliegue** (aws CLI, repetible):
1. crea o arranca las instancias con sus etiquetas, grupos de seguridad y volúmenes EBS;
2. instala Docker y lo deja activado al arrancar el sistema (`systemctl enable docker`), para que los
   contenedores vuelvan solos cuando el lab vuelva a arrancar las instancias (ADR 0031);
3. configura chrony con el servicio de hora de Amazon y comprueba que el reloj está sincronizado (ADR 0033);
4. genera `/etc/hosts` (ADR 0021), la CA y los certificados (ADR 0023);
5. arranca los contenedores.

**Entorno del producto:** `aws`.

## Consecuencias
- **Se gana:**
  - La misma imagen en todas las instancias.
  - El despliegue se rehace desde cero cuando caduca la sesión.
- **Se pierde:** cada despliegue tarda minutos y consume crédito.
- **Pendiente:**
  - Cómo llegan las imágenes a las instancias (construirlas en cada una o usar un registro). Fase II.
  - El entorno `local` de `convenciones.md` §2 ya está decidido: se mantiene como herramienta de
    desarrollo (ADR 0030).
