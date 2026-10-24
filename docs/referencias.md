# Referencias del proyecto

Todas las fuentes usadas en el diseño de DFSha, en formato IEEE. Las citadas en [`fase-1.md`](fase-1.md) llevan el mismo número que allí; las demás se consultaron pero no se citan en el texto.

Fecha de consulta de todas las fuentes en línea: 23 oct. 2026. El campo «Verificación» dice cómo se comprobó cada fuente y si se leyó en esta fase.

## Citadas en el documento de la fase I

### [1] enunciado

- **Referencia:** Universidad Pontificia Bolivariana, «Proyecto 1 · DFSha: diseño e implementación de un sistema de archivos distribuido con alta disponibilidad, rendimiento y seguridad», enunciado del proyecto, Sistemas Distribuidos 2026-2, 2026.
- **Tipo:** Curso
- **Citada en:** 1. Introducción, 3. Arquitectura, 5. Protocolos y APIs, 7. Semántica de `read()` y `write()`, 8. Concurrencia, integridad y recuperación de escrituras interrumpidas, 11. Escenarios obligatorios de razonamiento, 12. Métricas y experimentos
- **Verificación:** Transcripción fiel del PDF oficial en docs/enunciado.md (SHA-256 397daf0a…).
- **Nota:** Fuente de los requisitos RF1–RF3, RNF1–RNF7, §4 a §7.

### [2] raft

- **Referencia:** D. Ongaro y J. Ousterhout, «In search of an understandable consensus algorithm», en *Proc. USENIX Annual Technical Conf. (ATC)*, Philadelphia, PA, EE. UU., 2014, pp. 305–319. Versión extendida disponible en: https://raft.github.io/raft.pdf (consultado: 23 oct. 2026).
- **Tipo:** Artículo
- **Citada en:** 1. Introducción, 3. Arquitectura, 4. Distribución de archivos, metadatos y réplicas, 9. Tolerancia a fallos y disponibilidad, 10. Seguridad
- **Verificación:** Versión extendida descargada el 23 oct. 2026: título, autores, temporizadores aleatorios para elegir líder y lecturas linealizables.

### [3] gfs

- **Referencia:** S. Ghemawat, H. Gobioff y S.-T. Leung, «The Google file system», en *Proc. 19th ACM Symp. Operating Systems Principles (SOSP)*, Bolton Landing, NY, EE. UU., 2003, pp. 29–43. doi: 10.1145/945445.945450.
- **Tipo:** Artículo
- **Citada en:** 1. Introducción
- **Verificación:** Referencia bibliográfica conocida; no se descargó en esta sesión.
- **Nota:** Separación de control y datos, réplica primaria y arrendamientos.

### [4] hdfs

- **Referencia:** D. Borthakur, «HDFS architecture guide», Apache Hadoop 1.2.1 Documentation, The Apache Software Foundation, 2013. [En línea]. Disponible en: https://hadoop.apache.org/docs/r1.2.1/hdfs_design.html (consultado: 23 oct. 2026).
- **Tipo:** Documentación
- **Citada en:** 1. Introducción, 3. Arquitectura, 4. Distribución de archivos, metadatos y réplicas, 5. Protocolos y APIs, 7. Semántica de `read()` y `write()`, 8. Concurrencia, integridad y recuperación de escrituras interrumpidas, 9. Tolerancia a fallos y disponibilidad
- **Verificación:** Leída el 23 oct. 2026: NameNode como SPOF, bloque típico de 64 MB, latidos e informe de bloques, réplicas en cadena, Safemode, verificación de checksums en el cliente y staging en el cliente.
- **Nota:** Recomendada por el profesor (A8).

### [5] d03

- **Referencia:** A. Ospina Sanjuan, «Introducción y conceptos», diapositivas de clase, Arquitectura de Nube y Sistemas Distribuidos, Universidad Pontificia Bolivariana, 26 jul. 2026.
- **Tipo:** Clase
- **Citada en:** 1. Introducción, 9. Tolerancia a fallos y disponibilidad
- **Verificación:** Texto del deck en la base de conocimiento (fuentes/texto/03-Introduccion_conceptos.txt): fallas parciales (línea 301) y falacias, «La topología no cambia» (línea 356).
- **Nota:** Fallos parciales y falacias de la computación distribuida.

### [6] libro

- **Referencia:** M. van Steen y A. S. Tanenbaum, *Distributed Systems*, 4.ª ed. (v. 4.03). distributed-systems.net, 2025. [En línea]. Disponible en: https://www.distributed-systems.net/index.php/books/ds4/ (consultado: 23 oct. 2026).
- **Tipo:** Libro
- **Citada en:** 1. Introducción, 3. Arquitectura, 7. Semántica de `read()` y `write()`, 8. Concurrencia, integridad y recuperación de escrituras interrumpidas, 10. Seguridad
- **Verificación:** Libro de referencia del curso (D03 lo cita con esta URL; la base de conocimiento usa la v. 4.03).
- **Nota:** Capítulos citados: 1 (introducción), 2 (arquitecturas), 4 (comunicación), 5 (coordinación), 7 (consistencia y replicación), 8 (tolerancia a fallos), 9 (seguridad).

### [7] aws-time

- **Referencia:** Amazon Web Services, «Precision clock and time synchronization on your EC2 instance», Amazon EC2 User Guide. [En línea]. Disponible en: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/set-time.html (consultado: 23 oct. 2026).
- **Tipo:** Documentación
- **Citada en:** 1. Introducción, 10. Seguridad
- **Verificación:** Leída el 23 oct. 2026: Amazon Time Sync Service local y público (time.aws.com), chrony.
- **Nota:** La dirección 169.254.169.123 está en la subpágina configure-ec2-ntp.

### [8] aws-learner-lab

- **Referencia:** AWS Academy, «AWS Academy Learner Lab: Readme», Vocareum, 2026. Documento interno del laboratorio, accesible desde la sesión del Learner Lab.
- **Tipo:** Documentación
- **Citada en:** 1. Introducción, 3. Arquitectura, 9. Tolerancia a fallos y disponibilidad
- **Verificación:** Leído el 23 oct. 2026 desde la sesión del lab: máximo 9 instancias, 32 vCPU, tipos de nano a large, EBS hasta 100 GB, rearranque de instancias entre sesiones, IAM limitado a LabRole.
- **Nota:** El enlace lleva un token personal de sesión: no se publica.

### [9] aclaraciones

- **Referencia:** A. Ospina Sanjuan, aclaraciones sobre el enunciado del Proyecto 1 (A1–A8), comunicación personal, oct. 2026.
- **Tipo:** Curso
- **Citada en:** 1. Introducción, 7. Semántica de `read()` y `write()`, 10. Seguridad, 11. Escenarios obligatorios de razonamiento
- **Verificación:** Registradas en docs/aclaraciones.md el 2026-10-22.
- **Nota:** Proyecto individual, PDF, extensión, cifrado en reposo, alcance de RNF7, sin simplificaciones, guía de HDFS.

### [10] adr

- **Referencia:** DFSha, «Registro de decisiones de arquitectura (ADR 0001–0033)», repositorio del proyecto, carpeta docs/decisiones, 2026. [En línea]. Disponible en: https://github.com/pjg09/dfsha/tree/main/docs/decisiones (consultado: 23 oct. 2026).
- **Tipo:** Proyecto
- **Citada en:** 1. Introducción, Anexo B. Registro de decisiones
- **Verificación:** Commit faeba71 del repositorio local.
- **Nota:** Comprobar que el repositorio es visible para el profesor antes de entregar.

### [11] d09

- **Referencia:** A. Ospina Sanjuan, «Arquitecturas peer-to-peer», diapositivas de clase, Arquitectura de Nube y Sistemas Distribuidos, Universidad Pontificia Bolivariana, 24 sep. 2026.
- **Tipo:** Clase
- **Citada en:** 3. Arquitectura
- **Verificación:** fuentes/texto/09-P2P-wn.txt: índice central y «control ≠ datos» (líneas 239–257).
- **Nota:** Separación entre plano de control y plano de datos.

### [12] clase-p2p

- **Referencia:** A. Ospina Sanjuan, «P2P: índices, control y datos», clase (transcripción de audio), Arquitectura de Nube y Sistemas Distribuidos, Universidad Pontificia Bolivariana, 2026.
- **Tipo:** Clase
- **Citada en:** 3. Arquitectura, 4. Distribución de archivos, metadatos y réplicas, 8. Concurrencia, integridad y recuperación de escrituras interrumpidas, 9. Tolerancia a fallos y disponibilidad
- **Verificación:** Guía de clase G1 (fuentes/texto/p2-audio1-p2p.txt): dos disponibilidades, índice central con transferencia directa, granularidad.
- **Nota:** «Si se cae el índice, los datos siguen existiendo; el problema es encontrarlos».

### [13] amdahl

- **Referencia:** G. M. Amdahl, «Validity of the single processor approach to achieving large scale computing capabilities», en *Proc. AFIPS Spring Joint Computer Conf.*, 1967, pp. 483–485. doi: 10.1145/1465482.1465560.
- **Tipo:** Artículo
- **Citada en:** 3. Arquitectura
- **Verificación:** Referencia bibliográfica conocida; no se descargó en esta sesión.
- **Nota:** La fracción secuencial limita la mejora al escalar.

### [14] d04

- **Referencia:** A. Ospina Sanjuan, «Capítulo 2: Arquitecturas», diapositivas de clase, Arquitectura de Nube y Sistemas Distribuidos, Universidad Pontificia Bolivariana, 13 ago. 2026.
- **Tipo:** Clase
- **Citada en:** 3. Arquitectura
- **Verificación:** fuentes/texto/04-ArqSistemasDistribuidos_Cap2.txt: puntos únicos de fallo (línea 73).
- **Nota:** Cliente/servidor, SPOF y acoplamiento.

### [15] clase-mom

- **Referencia:** A. Ospina Sanjuan, «MOM: mensajes, trabajo y réplicas», clase (transcripción de audio), Arquitectura de Nube y Sistemas Distribuidos, Universidad Pontificia Bolivariana, 2026.
- **Tipo:** Clase
- **Citada en:** 3. Arquitectura, 4. Distribución de archivos, metadatos y réplicas, 7. Semántica de `read()` y `write()`, 8. Concurrencia, integridad y recuperación de escrituras interrumpidas, 11. Escenarios obligatorios de razonamiento
- **Verificación:** Guía de clase G4 (fuentes/texto/p2-audio4-mom.txt): idempotencia (línea 613), réplicas y quórum (líneas 958–984), ejemplo de confirmación por mayoría con 12, 20 y 55 ms.
- **Nota:** Quórum de mayoría, idempotencia, at-least-once.

### [16] etcd

- **Referencia:** etcd Authors, «etcd documentation». [En línea]. Disponible en: https://etcd.io/docs/ (consultado: 23 oct. 2026).
- **Tipo:** Documentación
- **Citada en:** 3. Arquitectura
- **Verificación:** Documentación oficial conocida; no se descargó en esta sesión.
- **Nota:** Candidata para Raft en la fase II.

### [17] pysyncobj

- **Referencia:** bakwc, «PySyncObj: A library for replicating your python class between multiple servers, based on raft protocol», GitHub, licencia MIT. [En línea]. Disponible en: https://github.com/bakwc/PySyncObj (consultado: 23 oct. 2026).
- **Tipo:** Software
- **Citada en:** 3. Arquitectura
- **Verificación:** Repositorio consultado el 23 oct. 2026: descripción y licencia MIT; el autor figura solo como usuario bakwc.
- **Nota:** Candidata para Raft en la fase II.

### [18] lab-hdfs

- **Referencia:** A. Ospina Sanjuan, «hdfs-hadoop», repositorio del laboratorio de HDFS, GitHub, 2026. [En línea]. Disponible en: https://github.com/aospina/hdfs-hadoop (consultado: 23 oct. 2026).
- **Tipo:** Clase
- **Citada en:** 3. Arquitectura, 9. Tolerancia a fallos y disponibilidad
- **Verificación:** Copia local en fuentes/repos-profesor/hdfs-hadoop y guía en practicas/hdfs/README.md (detección por defecto en unos 10,5 min; factor 3 con 3 DataNodes).
- **Nota:** Laboratorio no ejecutado: los valores salen de la configuración por defecto documentada.

### [19] docker-restart

- **Referencia:** Docker Inc., «Start containers automatically», Docker Docs. [En línea]. Disponible en: https://docs.docker.com/engine/containers/start-containers-automatically/ (consultado: 23 oct. 2026).
- **Tipo:** Documentación
- **Citada en:** 3. Arquitectura, 9. Tolerancia a fallos y disponibilidad
- **Verificación:** Leída el 23 oct. 2026: políticas no, on-failure, always y unless-stopped. No trata el arranque del daemon con el sistema.
- **Nota:** Política always: el contenedor vuelve cuando arranca el daemon.

### [20] aws-stopstart

- **Referencia:** Amazon Web Services, «How Amazon EC2 instance stop and start works», Amazon EC2 User Guide. [En línea]. Disponible en: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/how-ec2-instance-stop-start-works.html (consultado: 23 oct. 2026).
- **Tipo:** Documentación
- **Citada en:** 3. Arquitectura
- **Verificación:** Consultada el 23 oct. 2026: la IP privada se conserva al parar y arrancar; la pública cambia.

### [21] uuid

- **Referencia:** K. Davis, B. Peabody y P. Leach, «Universally unique identifiers (UUIDs)», RFC 9562, IETF, may. 2024. [En línea]. Disponible en: https://www.rfc-editor.org/rfc/rfc9562 (consultado: 23 oct. 2026).
- **Tipo:** Estándar
- **Citada en:** 4. Distribución de archivos, metadatos y réplicas, 8. Concurrencia, integridad y recuperación de escrituras interrumpidas
- **Verificación:** RFC conocido; no se descargó en esta sesión.
- **Nota:** Identificadores de bloque y de petición.

### [22] d07

- **Referencia:** A. Ospina Sanjuan, «Llamadas a procedimientos remotos. gRPC: de la invocación local a los microservicios modernos», diapositivas de clase, Arquitectura de Nube y Sistemas Distribuidos, Universidad Pontificia Bolivariana, 24 sep. 2026.
- **Tipo:** Clase
- **Citada en:** 5. Protocolos y APIs
- **Verificación:** fuentes/texto/07-gRPC-2026.txt: HTTP/2, Protocol Buffers y streaming nativo (líneas 118–127).
- **Nota:** Comparación gRPC frente a REST.

### [23] protobuf

- **Referencia:** Google, «Protocol Buffers documentation». [En línea]. Disponible en: https://protobuf.dev/ (consultado: 23 oct. 2026).
- **Tipo:** Documentación
- **Citada en:** 5. Protocolos y APIs
- **Verificación:** Documentación oficial conocida; no se descargó en esta sesión.

### [24] d08

- **Referencia:** A. Ospina Sanjuan, «Message-Oriented Middleware: comunicación asíncrona y desacoplada entre procesos distribuidos», diapositivas de clase, Arquitectura de Nube y Sistemas Distribuidos, Universidad Pontificia Bolivariana, 24 sep. 2026.
- **Tipo:** Clase
- **Citada en:** 5. Protocolos y APIs
- **Verificación:** fuentes/texto/08-MOM.txt: colas punto a punto frente a tópicos (líneas 133–146).
- **Nota:** Colas frente a tópicos; desacoplamiento temporal.

### [25] grpc-deadlines

- **Referencia:** gRPC Authors, «Deadlines», gRPC Documentation. [En línea]. Disponible en: https://grpc.io/docs/guides/deadlines/ (consultado: 23 oct. 2026).
- **Tipo:** Documentación
- **Citada en:** 5. Protocolos y APIs
- **Verificación:** Leída el 23 oct. 2026: «you should always explicitly set a realistic deadline»; sin plazo, el cliente puede esperar indefinidamente.

### [26] lab-grpc

- **Referencia:** A. Ospina Sanjuan, «gRPC», repositorio del laboratorio de gRPC, GitHub, 2026. [En línea]. Disponible en: https://github.com/aospina/gRPC (consultado: 23 oct. 2026).
- **Tipo:** Clase
- **Citada en:** 5. Protocolos y APIs, 10. Seguridad
- **Verificación:** Copia local en fuentes/repos-profesor/gRPC: usa add_insecure_port y no fija plazos.

### [27] grpc-status

- **Referencia:** gRPC Authors, «Status codes and their use in gRPC», gRPC Documentation. [En línea]. Disponible en: https://grpc.io/docs/guides/status-codes/ (consultado: 23 oct. 2026).
- **Tipo:** Documentación
- **Citada en:** 5. Protocolos y APIs
- **Verificación:** Leída el 23 oct. 2026: definiciones de UNAVAILABLE (reintentar con espera), ABORTED, FAILED_PRECONDITION, DATA_LOSS y DEADLINE_EXCEEDED.

### [28] grpc-errors

- **Referencia:** gRPC Authors, «Error handling», gRPC Documentation. [En línea]. Disponible en: https://grpc.io/docs/guides/error/ (consultado: 23 oct. 2026).
- **Tipo:** Documentación
- **Citada en:** 5. Protocolos y APIs
- **Verificación:** Leída el 23 oct. 2026: modelo de error enriquecido con detalles en mensajes protobuf, enviados como metadatos finales.

### [29] afs

- **Referencia:** J. H. Howard *et al.*, «Scale and performance in a distributed file system», *ACM Trans. Computer Systems*, vol. 6, n.º 1, pp. 51–81, feb. 1988. doi: 10.1145/35037.35059.
- **Tipo:** Artículo
- **Citada en:** 7. Semántica de `read()` y `write()`
- **Verificación:** Referencia bibliográfica conocida; no se descargó en esta sesión.
- **Nota:** Origen de la semántica de apertura-cierre (AFS).

### [30] leases

- **Referencia:** C. G. Gray y D. R. Cheriton, «Leases: An efficient fault-tolerant mechanism for distributed file cache consistency», en *Proc. 12th ACM Symp. Operating Systems Principles (SOSP)*, 1989, pp. 202–210. doi: 10.1145/74850.74870.
- **Tipo:** Artículo
- **Citada en:** 8. Concurrencia, integridad y recuperación de escrituras interrumpidas
- **Verificación:** Referencia bibliográfica conocida; no se descargó en esta sesión.
- **Nota:** Arrendamientos con caducidad como cerrojo tolerante a fallos.

### [31] sha2

- **Referencia:** National Institute of Standards and Technology, «Secure Hash Standard (SHS)», FIPS PUB 180-4, ago. 2015. doi: 10.6028/NIST.FIPS.180-4.
- **Tipo:** Estándar
- **Citada en:** 8. Concurrencia, integridad y recuperación de escrituras interrumpidas
- **Verificación:** Estándar conocido; no se descargó en esta sesión.
- **Nota:** SHA-256.

### [32] gcm

- **Referencia:** M. Dworkin, «Recommendation for block cipher modes of operation: Galois/Counter Mode (GCM) and GMAC», NIST, Gaithersburg, MD, EE. UU., SP 800-38D, nov. 2007. doi: 10.6028/NIST.SP.800-38D.
- **Tipo:** Estándar
- **Citada en:** 8. Concurrencia, integridad y recuperación de escrituras interrumpidas, 10. Seguridad
- **Verificación:** Estándar conocido; no se descargó en esta sesión.
- **Nota:** Nonce de 96 bits, etiqueta de autenticación y datos asociados.

### [33] clase-rpc

- **Referencia:** A. Ospina Sanjuan, «RPC: fallos y plazos», clase (transcripción de audio), Arquitectura de Nube y Sistemas Distribuidos, Universidad Pontificia Bolivariana, 2026.
- **Tipo:** Clase
- **Citada en:** 8. Concurrencia, integridad y recuperación de escrituras interrumpidas
- **Verificación:** Guía de clase G3 (fuentes/texto/p2-audio3-rpc.txt, línea 495): un timeout no dice si la operación se ejecutó.
- **Nota:** Semántica ante fallos de las llamadas remotas.

### [34] scrypt

- **Referencia:** C. Percival y S. Josefsson, «The scrypt password-based key derivation function», RFC 7914, IETF, ago. 2016. [En línea]. Disponible en: https://www.rfc-editor.org/rfc/rfc7914 (consultado: 23 oct. 2026).
- **Tipo:** Estándar
- **Citada en:** 10. Seguridad
- **Verificación:** RFC conocido; no se descargó en esta sesión.

### [35] hmac

- **Referencia:** H. Krawczyk, M. Bellare y R. Canetti, «HMAC: Keyed-hashing for message authentication», RFC 2104, IETF, feb. 1997. [En línea]. Disponible en: https://www.rfc-editor.org/rfc/rfc2104 (consultado: 23 oct. 2026).
- **Tipo:** Estándar
- **Citada en:** 10. Seguridad
- **Verificación:** RFC conocido; no se descargó en esta sesión.

### [36] tls13

- **Referencia:** E. Rescorla, «The Transport Layer Security (TLS) protocol version 1.3», RFC 8446, IETF, ago. 2018. [En línea]. Disponible en: https://www.rfc-editor.org/rfc/rfc8446 (consultado: 23 oct. 2026).
- **Tipo:** Estándar
- **Citada en:** 10. Seguridad
- **Verificación:** RFC conocido; no se descargó en esta sesión.

### [37] aws-ebs-enc

- **Referencia:** Amazon Web Services, «Amazon EBS encryption», Amazon EBS User Guide. [En línea]. Disponible en: https://docs.aws.amazon.com/ebs/latest/userguide/ebs-encryption.html (consultado: 23 oct. 2026).
- **Tipo:** Documentación
- **Citada en:** 10. Seguridad
- **Verificación:** Leída el 23 oct. 2026: el cifrado ocurre en los servidores que alojan la instancia y cubre los datos en reposo y en tránsito entre la instancia y el volumen.

### [38] aws-envelope

- **Referencia:** Amazon Web Services, «AWS KMS cryptography essentials: Envelope encryption», AWS Key Management Service Developer Guide. [En línea]. Disponible en: https://docs.aws.amazon.com/kms/latest/developerguide/kms-cryptography.html (consultado: 23 oct. 2026).
- **Tipo:** Documentación
- **Citada en:** 10. Seguridad
- **Verificación:** Leída el 23 oct. 2026: sección «Envelope encryption»: cifrar los datos con una clave de datos y esta con otra clave.
- **Nota:** Definición de cifrado de sobre (no se usa KMS en tiempo de ejecución).

### [39] d06

- **Referencia:** A. Ospina Sanjuan, «Llamadas a procedimientos remotos (RPC)», diapositivas de clase, Arquitectura de Nube y Sistemas Distribuidos, Universidad Pontificia Bolivariana, 13 ago. 2026.
- **Tipo:** Clase
- **Citada en:** 11. Escenarios obligatorios de razonamiento
- **Verificación:** fuentes/texto/06-RPC-2026.txt: el binder o servidor de registro (líneas 171–173).
- **Nota:** Binder: el cliente pregunta dónde está el servicio y después lo llama.

### [40] aws-burstable

- **Referencia:** Amazon Web Services, «Burstable performance instances», Amazon EC2 User Guide. [En línea]. Disponible en: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/burstable-performance-instances.html (consultado: 23 oct. 2026).
- **Tipo:** Documentación
- **Citada en:** 12. Métricas y experimentos
- **Verificación:** Leída el 23 oct. 2026: rendimiento base con ráfagas; T3 usa Intel Xeon Skylake o Cascade Lake; modos standard y unlimited.
- **Nota:** Créditos de CPU de las instancias t3.

## Consultadas y no citadas

### rfc1123

- **Referencia:** R. Braden, Ed., «Requirements for Internet hosts: Application and support», RFC 1123, IETF, oct. 1989. [En línea]. Disponible en: https://www.rfc-editor.org/rfc/rfc1123 (consultado: 23 oct. 2026).
- **Tipo:** Estándar
- **Verificación:** RFC conocido; no se descargó en esta sesión.
- **Nota:** Sintaxis de los nombres de host.

### mermaid

- **Referencia:** Mermaid, «mermaid-cli», v. 12.0.0, GitHub, 2026. [En línea]. Disponible en: https://github.com/mermaid-js/mermaid-cli (consultado: 23 oct. 2026).
- **Tipo:** Software
- **Verificación:** Instalada y usada el 23 oct. 2026 para generar las figuras (npm, versión del 24 sep. 2026).
- **Nota:** Herramienta, no se cita en el texto.
