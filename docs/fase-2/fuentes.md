# Fuentes de la fase II

Fuentes que apoyan las decisiones de la fase II, en el formato de [`referencias.md`](../referencias.md), para
citarlas en el informe técnico final. Se añaden **en el momento** en que se usan para decidir algo, con cómo se
comprobó cada una. Las de la fase I siguen en `referencias.md` con su número; aquí se remite a ellas.

Las claves (`[jepsen-etcd]`) son provisionales: el número IEEE se asigna al redactar el informe, por orden de
primera cita.

## Consenso y metadatos (etapa 2)

### [jepsen-etcd]

- **Referencia:** K. Kingsbury, «Jepsen: etcd 3.4.3», Jepsen, 30 ene. 2020. [En línea]. Disponible en: https://jepsen.io/analyses/etcd-3.4.3 (consultado: 6 nov. 2026).
- **Tipo:** Análisis técnico
- **Usada en:** ADR 0039
- **Verificación:** Leída el 6 nov. 2026. Las lecturas, escrituras y transacciones de etcd son *strict serializable* («etcd is in fact strict serializable by default»). Sus cerrojos con arrendamiento no dan exclusión mutua: «Multiple processes can hold an etcd lock concurrently, even in healthy clusters». Recomienda la revisión de la clave como ficha de cercado monótona.
- **Nota:** Base de las tres defensas contra el cerebro dividido del ADR 0039.

### [hdfs-ha]

- **Referencia:** The Apache Software Foundation, «HDFS high availability using the Quorum Journal Manager», Apache Hadoop 3.3.5 Documentation, 2023. [En línea]. Disponible en: https://hadoop.apache.org/docs/stable/hadoop-project-dist/hadoop-hdfs/HDFSHighAvailabilityWithQJM.html (consultado: 6 nov. 2026).
- **Tipo:** Documentación
- **Usada en:** ADR 0039
- **Verificación:** Leída el 6 nov. 2026. La conmutación automática añade «a ZooKeeper quorum, and the ZKFailoverController process (abbreviated as ZKFC)»; ZooKeeper elige el NameNode activo con un znode efímero que hace de cerrojo. Los JournalNodes solo admiten un escritor para evitar el «split-brain scenario», y aun así aconseja configurar cercado porque el NameNode activo anterior puede servir lecturas desfasadas.
- **Nota:** Muestra que delegar la elección del líder en un servicio de consenso, con cercado, es el diseño de referencia del curso (A8) en su versión con alta disponibilidad.

### [etcd-3.7.3]

- **Referencia:** etcd Authors, «etcd v3.7.3», versión publicada en GitHub, 22 oct. 2026. [En línea]. Disponible en: https://github.com/etcd-io/etcd/releases/tag/v3.7.3 (consultado: 6 nov. 2026).
- **Tipo:** Software
- **Usada en:** ADR 0039 y 0040
- **Verificación:** Fecha tomada de la API de GitHub. Valores por defecto leídos de `etcd --help` en la imagen `gcr.io/etcd-development/etcd:v3.7.3`: latido de 100 ms, elección de 1000 ms, instantánea cada 10 000 transacciones, 128 operaciones por transacción, peticiones de 1 572 864 bytes y base de datos de 2 GiB. Un `fsync` del WAL por escritura, medido con la métrica `etcd_disk_wal_fsync_duration_seconds_count` en un prototipo de tres nodos.
- **Nota:** Versión concreta de la documentación general de etcd, que es la [16] de `referencias.md`.

### [pysyncobj-0.3.17]

- **Referencia:** bakwc, «pysyncobj 0.3.17», Python Package Index, 30 ago. 2026. [En línea]. Disponible en: https://pypi.org/project/pysyncobj/0.3.17/ (consultado: 6 nov. 2026).
- **Tipo:** Software
- **Usada en:** ADR 0039
- **Verificación:** Código fuente leído el 6 nov. 2026. `journal.py` escribe el journal en memoria mapeada y `syncobj.py` nunca llama a su `flush`. `config.py` documenta `appendEntriesUseBatch`, `leaderFallbackTimeout` (30 s) y la advertencia «there could be multiple leaders at the same time». Con `strace` sobre el líder: 200 escrituras confirmadas y ninguna llamada a `fsync`, `fdatasync` ni `msync`.
- **Nota:** Versión concreta de la [17] de `referencias.md`.

### [etcd-sdk-python]

- **Referencia:** «etcd-sdk-python 0.0.7», Python Package Index, 4 ago. 2025. [En línea]. Disponible en: https://pypi.org/project/etcd-sdk-python/ (consultado: 6 nov. 2026).
- **Tipo:** Software
- **Usada en:** ADR 0039
- **Verificación:** Instalado con grpcio 1.85.1 y protobuf 7.36.2. Contra un etcd v3.7.3: escritura, lectura y una transacción condicional que rechaza la escritura basada en un valor viejo. El módulo se importa como `pyetcd`.
- **Nota:** Cliente síncrono; candidato para la etapa 4.

### [aetcd]

- **Referencia:** «aetcd 1.0.0», Python Package Index, 29 jun. 2026. [En línea]. Disponible en: https://pypi.org/project/aetcd/ (consultado: 6 nov. 2026).
- **Tipo:** Software
- **Usada en:** ADR 0039
- **Verificación:** Instalado con grpcio 1.85.1 y protobuf 7.36.2; escritura y lectura correctas contra un etcd v3.7.3.
- **Nota:** Cliente para asyncio; candidato para la etapa 4.

### [etcd3]

- **Referencia:** «etcd3 0.12.0», Python Package Index, 31 mar. 2020. [En línea]. Disponible en: https://pypi.org/project/etcd3/ (consultado: 6 nov. 2026).
- **Tipo:** Software
- **Usada en:** ADR 0039
- **Verificación:** Fecha de su última versión en PyPI.
- **Nota:** Cliente clásico de etcd, descartado por no actualizarse desde 2020.

## Despliegue y entorno (etapas 0 y 1)

### [ecr-inmutables]

- **Referencia:** Amazon Web Services, «Preventing image tags from being overwritten in Amazon ECR», Amazon ECR User Guide. [En línea]. Disponible en: https://docs.aws.amazon.com/AmazonECR/latest/userguide/image-tag-mutability.html (consultado: 6 nov. 2026).
- **Tipo:** Documentación
- **Usada en:** ADR 0037
- **Verificación:** Leída el 6 nov. 2026: «After tag immutability is turned on, the ImageTagAlreadyExistsException error is returned if you push an image with a tag that is already in the repository.»
- **Nota:** Existe además `IMMUTABLE_WITH_EXCLUSION`, que deja actualizar algunas etiquetas; el ADR 0037 usa `IMMUTABLE` sin excepciones.

### [grpcio-status]

- **Referencia:** The gRPC Authors, «grpcio-status 1.85.1», Python Package Index. [En línea]. Disponible en: https://pypi.org/project/grpcio-status/ (consultado: 6 nov. 2026).
- **Tipo:** Software
- **Usada en:** ADR 0038 y `dfsha/common/errors.py`
- **Verificación:** Código de `grpc_status/rpc_status.py` leído el 6 nov. 2026: `to_status()` pone el `google.rpc.Status` en los metadatos finales de la llamada y `from_call()` lo recupera. Probado con un servidor gRPC real en las pruebas de `tests/test_errors.py`.
- **Nota:** Implementación del modelo de error enriquecido de gRPC, que es la [28] de `referencias.md`.

### [uv]

- **Referencia:** Astral, «uv: An extremely fast Python package and project manager», documentación. [En línea]. Disponible en: https://docs.astral.sh/uv/ (consultado: 6 nov. 2026).
- **Tipo:** Documentación
- **Usada en:** ADR 0038
- **Verificación:** No se leyó la documentación. El comportamiento se comprobó al usarlo (versión 0.12.5): instala Python 3.12 junto al 3.14 del sistema y `uv sync --locked` reproduce `uv.lock`, en local y en GitHub Actions.

### [hatch-vcs]

- **Referencia:** «hatch-vcs 0.5.0», Python Package Index. [En línea]. Disponible en: https://pypi.org/project/hatch-vcs/ (consultado: 6 nov. 2026).
- **Tipo:** Software
- **Usada en:** ADR 0038
- **Verificación:** Comprobado al usarlo: sin filtro tomaba la etiqueta `entrega-fase-1` y daba la versión `2.dev12`; con `git describe --match "v[0-9]*"` da `0.1.1.dev12`.

## Nodo de datos (etapa 3)

### [glibc-malloc]

- **Referencia:** Free Software Foundation, «Memory allocation tunables», en *The GNU C Library Reference Manual*. [En línea]. Disponible en: https://www.gnu.org/software/libc/manual/html_node/Memory-Allocation-Tunables.html (consultado: 6 nov. 2026).
- **Tipo:** Documentación
- **Usada en:** `Dockerfile` (`MALLOC_ARENA_MAX=2`)
- **Verificación:** No se leyó la página. El efecto se midió: con 8 escrituras simultáneas, la mediana del pico de memoria de la primaria baja de 257 a 167 MiB (5 repeticiones, `docs/fase-2/notas.md`).

## Seguridad (etapa 6)

### [grpc-python-tls]

- **Referencia:** The gRPC Authors, «grpc.ssl_server_credentials», gRPC Python API reference. [En línea]. Disponible en: https://grpc.github.io/grpc/python/grpc.html#grpc.ssl_server_credentials (consultado: 7 nov. 2026).
- **Tipo:** Documentación
- **Usada en:** ADR 0043
- **Verificación:** No se leyó la página. Se comprobó con grpcio 1.85.1: la función solo admite `require_client_auth=True` o `False`, y con `False` el contexto de la llamada no trae ningún dato del certificado del otro extremo; con `True` trae su SAN y `ssl_tls_version = TLSv1.3` (`tests/test_tls.py`).

### [cryptography-aead-scrypt]

- **Referencia:** The Python Cryptographic Authority, «cryptography 50.0.2 documentation: AEAD (AESGCM) y Scrypt». [En línea]. Disponible en: https://cryptography.io/en/latest/ (consultado: 7 nov. 2026).
- **Tipo:** Documentación
- **Usada en:** ADR 0043 y `dfsha/common/security.py`
- **Verificación:** No se leyó la documentación. El uso se comprobó en `tests/test_security.py`: AES-GCM rechaza un bit cambiado y un dato asociado distinto, y scrypt da hashes distintos con sales distintas.


## Despliegue en AWS (etapa 7)

### [etcdutl-restore]

- **Referencia:** etcd Authors, «etcdutl snapshot restore», ayuda de la orden en etcd v3.7.3. [En línea]. Disponible en: https://etcd.io/docs/v3.6/op-guide/recovery/ (consultado: 7 nov. 2026).
- **Tipo:** Software
- **Usada en:** `deploy/aws/deploy.sh restore` (ADR 0035)
- **Verificación:** No se leyó la página. Se leyó `etcdutl snapshot restore --help` en la imagen fijada `gcr.io/etcd-development/etcd:v3.7.3`: `--bump-revision` («How much to increase the latest revision after restore») exige `--mark-compacted`. Comprobado en AWS: tras restaurar, el líder salió con la época 2 000 000 252 y los nodos de datos lo aceptaron (`evidencias/2026-11-07-restauracion-de-metadatos`).
- **Nota:** La versión de la URL es la última documentada que se conoce; la ayuda leída es la de v3.7.3.

### [ubuntu-ami-ssm]

- **Referencia:** Canonical, «Find Ubuntu images on AWS», Ubuntu on public clouds. [En línea]. Disponible en: https://documentation.ubuntu.com/aws/aws-how-to/instances/find-ubuntu-images/ (consultado: 7 nov. 2026).
- **Tipo:** Documentación
- **Usada en:** `deploy/aws/deploy.sh up` (parámetro de SSM con la AMI de Ubuntu 26.04)
- **Verificación:** No se leyó la página. El parámetro `/aws/service/canonical/ubuntu/server/26.04/stable/current/amd64/hvm/ebs-gp3/ami-id` devolvió una AMI con la que las 9 instancias arrancaron con Ubuntu 26.04 y chrony sincronizado (lo comprueba `install`).
