# 0035 · Persistencia de los metadatos en un volumen EBS por servidor de metadatos

- **Estado:** Aceptada
- **Fecha:** 2026-10-24
- **Requisitos relacionados:** RNF2, RNF3 (G1 del ADR 0010), RNF6, §5.1; completa los ADR 0014, 0024 y 0026; C27, C29

## Contexto
El ADR 0014 fija el mecanismo: los metadatos son una máquina de estados replicada con Raft, con un log replicado e
instantáneas periódicas. No dice dónde quedan en disco ni con qué garantías:
- **Ubicación.** Sin una decisión, el log y las instantáneas acabarían en el disco raíz de 8 GiB, que comparten el
  sistema operativo y Docker y que se borra al terminar la instancia (C29). El ADR 0026 solo da volumen propio a los
  nodos de datos.
- **Durabilidad.** Raft exige guardar cada entrada en almacenamiento estable antes de responder. Si la implementación
  no hace `fsync`, una caída simultánea de dos servidores puede perder escrituras ya confirmadas al cliente, y G1
  deja de cumplirse.
- **Copias de seguridad.** Raft protege frente a la pérdida de un servidor, pero no frente a la de los tres ni
  frente a un error que se replica a todos.

HDFS 1.2.1 resuelve lo mismo con el espacio de nombres en memoria y, en el disco local del NameNode, un log de
transacciones (EditLog) y una imagen periódica (FsImage). Puede mantener varias copias de los dos, actualizadas de
forma síncrona.

## Opciones consideradas
1. **Disco raíz** (volumen Docker). Es lo más simple, y Raft ya guarda tres copias. Pero sustituir un servidor
   obliga a dar de alta un miembro nuevo en Raft y a enviarle una instantánea entera, y el log compite por espacio
   con el sistema y con Docker.
2. **Un volumen EBS propio por servidor de metadatos.** Sobrevive a que se termine la instancia y se puede conectar
   a una instancia nueva con la misma identidad.
3. **Una base de datos externa** (PostgreSQL o RDS). Sería otro punto único de fallo o necesitaría su propia
   replicación, justo lo que ya resuelve Raft. Además, sacaría los metadatos del modelo de consistencia del ADR 0010.

## Decisión
Opción 2.

**Volumen:**
- Cada servidor de metadatos tiene un volumen EBS gp3 de 4 GiB, cifrado con `aws/ebs`, con la etiqueta
  `Name=dfsha-metadata-<n>-data`.
- Guarda el log replicado y las instantáneas de Raft.
- El script de despliegue lo monta por UUID con `nofail`. El servidor comprueba al arrancar que su directorio de
  datos es un punto de montaje y que contiene una marca con su nombre de host; si no, no arranca (igual que en el ADR 0026).
- Si una instancia se rompe, su volumen se conecta a una instancia nueva con el mismo nombre de host. Así no hace
  falta cambiar la composición del clúster de Raft.

**Durabilidad:**
- Cada entrada del log se escribe con `fsync` antes de que el servidor la cuente para la mayoría.
- Es un **requisito para elegir la implementación** en la fase II (ADR 0014): si no lo hace por defecto, se
  configura; si no se puede configurar, esa implementación se descarta.

**Organización:**
- La máquina de estados guarda las entidades del modelo de metadatos (usuarios, directorios, archivos, versiones,
  bloques, réplicas, arrendamientos, escrituras en curso y registro de peticiones), indexadas por su identificador.
- Confirmar una versión, un `mv` o un `rm` es **una sola entrada del log**. En etcd sería una transacción con
  varias escrituras.
- Todo el estado cabe en memoria: unos pocos KiB por archivo de 1 GiB.

**Copias de seguridad:**
- Al final de cada sesión de trabajo, el script de despliegue toma la última instantánea del líder y la guarda en
  S3, en el bucket `dfsha-copias-<sufijo>`. Usa las credenciales de la sesión, así que ningún componente usa
  credenciales de AWS mientras funciona (C27).
- La restauración es manual: se copia la instantánea al volumen de los tres servidores y se arranca el clúster.

**Separación de la clave de envoltura** (completa el ADR 0024):
- El volumen de metadatos y la copia de seguridad contienen las claves de datos **envueltas**. Si la clave de
  envoltura estuviera en el mismo volumen o en la misma copia, quien robara cualquiera de los dos podría descifrar
  todos los archivos.
- Por eso la clave de envoltura **nunca se escribe** en el volumen de metadatos ni en la copia de S3. Se monta en el
  contenedor como secreto, desde el disco raíz de cada servidor de metadatos.
- El administrador la guarda fuera del clúster y fuera del repositorio, con los demás secretos del despliegue. El
  script la vuelve a copiar si se sustituye una instancia, y hace falta para restaurar una copia de seguridad.

## Consecuencias
- **Se gana:**
  - Los metadatos sobreviven a que se termine una instancia, y sustituir un servidor es conectar su volumen a otra
    instancia.
  - G1 queda garantizada en disco, no solo en memoria.
  - Hay una copia fuera del clúster frente a la pérdida de los tres servidores.
- **Se pierde:**
  - Tres volúmenes más, unos 1 USD/mes en total.
  - El script de despliegue tiene un paso más.
  - El `fsync` de cada entrada añade latencia a las escrituras de metadatos; se mide con E7.
- **Límite:**
  - No hay recuperación a un momento anterior a la última copia de seguridad.
  - Un borrado por error se replica a los tres servidores al instante. Solo se recupera desde la copia, perdiendo
    lo posterior a ella.
  - La copia guarda los hashes de las contraseñas y las claves de datos envueltas, nunca en claro. El bucket es
    privado y cifrado.
  - Si se pierde la clave de envoltura, ningún archivo se puede descifrar, aunque se conserven los bloques y los
    metadatos. Su custodia fuera del clúster es tan crítica como la de la clave de la CA.
- **Término nuevo en el glosario:** copia de seguridad.
