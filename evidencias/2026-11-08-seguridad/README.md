# Seguridad, con la versión final

- **Fecha:** 2026-11-08, de 04:37 a 04:40 UTC
- **Commit y versión:** imágenes `v0.13.1` (`17c5dbd`), la versión final de la etapa 10; scripts de `32c0dba`
- **Entorno:** aws · `metadata-1` a `metadata-3` (t3.small), `datanode-1` a `datanode-5` (t3.micro, volumen gp3 de 10 GiB cifrado), `client-1` (t3.small, ADR 0045); `us-east-1a`. Configuración por defecto, sin los parámetros de los experimentos.
- **Cubre:** prueba mínima «Seguridad» de §5.2, repetida con la versión final. La primera ejecución está en [`2026-11-07-seguridad`](../2026-11-07-seguridad/).
- **Resultado esperado:** el de la primera ejecución (fase I §10): solo se entra con certificado, token y contraseña válidos, cada usuario ve solo lo suyo, solo un administrador crea usuarios, tras 5 contraseñas incorrectas seguidas se rechaza cualquier intento durante unos segundos, TLS 1.3 en el canal y bloques cifrados en disco.
- **Resultado obtenido:** coincide, con la misma salida que la primera ejecución salvo los identificadores, las horas y el contenido de `/`:
  - **Grupos de seguridad y volúmenes:** los puertos del clúster solo se abren entre grupos del proyecto, y todos los volúmenes EBS están cifrados. Los nodos de datos y el cliente no tienen la clave de envoltura.
  - **TLS:** TLS 1.3 (`TLS_AES_256_GCM_SHA384`) con el certificado de `client-1`. Sin certificado de cliente, el servidor cierra la conexión.
  - **Las siete llamadas indebidas, rechazadas:**
    - sin TLS, o con TLS pero sin certificado: `UNAVAILABLE`;
    - sin token de acceso, o con uno inventado: `UNAUTHENTICATED`;
    - `RegisterDataNode` suplantando a `datanode-1`: `PERMISSION_DENIED`;
    - `ReadBlock` sin token de bloque, o con su firma inventada: `BLOCK_TOKEN_INVALID`.
  - **Usuarios:** `admin` no ve `/grande.bin` de `pedro` (`PATH_NOT_FOUND`), y `pedro` no puede crear usuarios (`PERMISSION_DENIED`).
  - **Límite de intentos:** el sexto intento seguido con contraseña incorrecta, y también la contraseña correcta justo después, reciben «Demasiados intentos fallidos».
  - **Cifrado en disco:** una marca que aparece 50 000 veces en el original no aparece en ninguna de las 438 réplicas, y la copia recuperada tiene el mismo SHA-256.

## Comandos
```bash
evidencias/2026-11-07-seguridad/ejecutar.sh > evidencias/2026-11-08-seguridad/salida.txt 2>&1
```

## Archivos
- `salida.txt`: salida completa. Solo muestra los nombres y los permisos de los secretos, nunca su contenido.
