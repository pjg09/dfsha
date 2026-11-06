# 0040 · Despliegue en AWS: una imagen por rol, con etcd junto a cada servidor de metadatos

- **Estado:** Aceptada
- **Fecha:** 2026-11-06
- **Requisitos relacionados:** §5 («no basta una simulación local monolítica»), §5.1, §5.3 (instrucciones reproducibles); C26, C27, C29, C30; sustituye al ADR 0027

## Contexto
El ADR 0027 fija una imagen por rol y un solo contenedor por instancia. El ADR 0039 elige etcd como
implementación de Raft, con un miembro en cada servidor de metadatos, así que esas instancias necesitan un
segundo contenedor. Además, el ADR 0037 ya resolvió lo que el 0027 dejaba pendiente: las imágenes llegan
desde ECR. Este ADR recoge el 0027 con esos dos cambios.

## Opciones consideradas
1. **etcd dentro de la imagen `dfsha-metadata`**, con dos procesos en un contenedor. Mantiene un contenedor
   por instancia, pero mezcla dos programas con ciclos de vida distintos y el reinicio automático ya no
   vigila a cada uno.
2. **etcd como servicio del sistema**, fuera de Docker. Rompe la regla de que todo se despliega igual.
3. **Dos contenedores en los servidores de metadatos:** `dfsha-metadata` y etcd, en el mismo `compose.yaml`.

## Decisión
Opción 3.

**Imágenes:** `dfsha-metadata`, `dfsha-datanode` y `dfsha-client`, con la versión como etiqueta, desde ECR
(ADR 0037). etcd usa la imagen oficial `gcr.io/etcd-development/etcd:v3.7.3`, fijada además por su digest.

**Contenedores por instancia:**
- Servidores de metadatos: dos, el miembro de etcd y `dfsha-metadata`.
- Nodos de datos y cliente: uno, el de su rol.

**En cada instancia** hay un `compose.yaml` mínimo que declara, para cada contenedor:
- red del host;
- su volumen de datos: el volumen EBS del nodo de datos (ADR 0026), o el del servidor de metadatos para
  etcd (ADR 0035);
- certificados y secretos montados desde fuera del repositorio;
- reinicio automático.

**Script de despliegue** (aws CLI, repetible):
1. crea o arranca las instancias con sus etiquetas, grupos de seguridad y volúmenes EBS;
2. instala Docker y lo deja activado al arrancar el sistema, para que los contenedores vuelvan solos cuando
   el lab vuelva a arrancar las instancias (ADR 0031);
3. comprueba que chrony está sincronizado con el servicio de hora de Amazon (ADR 0033);
4. genera `/etc/hosts` (ADR 0021), la CA y los certificados (ADR 0023);
5. obtiene las imágenes de ECR (ADR 0037) y arranca los contenedores.

**Entorno del producto:** `aws`.

## Consecuencias
- **Se gana:**
  - La misma imagen en todas las instancias de un rol.
  - El despliegue se rehace desde cero cuando caduca la sesión.
  - etcd se reinicia y se actualiza por separado del servidor de metadatos.
- **Se pierde:** cada despliegue tarda minutos y consume crédito. Los servidores de metadatos tienen un
  contenedor más que vigilar.
- **Entorno local** (ADR 0030): `deploy/local/compose.yaml` añade los tres miembros de etcd.
