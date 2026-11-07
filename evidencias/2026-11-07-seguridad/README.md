# Seguridad: acceso autorizado y denegado, TLS y cifrado en disco

- **Fecha:** 2026-11-07
- **Commit y versión:** imágenes `v0.9.0` (`c82e0e1`) en ECR; despliegue con `deploy/aws/deploy.sh` de `57d91bc`
- **Entorno:** aws · los 9 hosts del clúster; las pruebas salen de `client-1`
- **Cubre:** prueba mínima «Seguridad» de §5.2
- **Resultado esperado:** fase I §10 y ADR 0043. Todas las conexiones con TLS 1.3 mutuo; sin certificado de la CA interna, sin token de acceso o con un token falso no hay acceso; cada usuario ve solo su espacio de nombres; solo un administrador crea usuarios; tras 5 fallos seguidos el usuario queda bloqueado 30 s; los nodos de datos exigen un token de bloque válido; en disco solo hay bloques cifrados; los volúmenes EBS están cifrados y los secretos repartidos por rol.
- **Resultado obtenido:** coincide en todos los puntos.
  - **Red:** los puertos del clúster solo se abren entre los grupos del proyecto, y SSH solo desde la IP de la máquina de administración.
  - **Volúmenes:** los 8 de datos y los 9 discos raíz están cifrados.
  - **Secretos:** la clave de envoltura solo está en los servidores de metadatos.
  - **TLS:** `metadata-1` negocia TLS 1.3 con el certificado de `client-1`, y sin certificado cierra la conexión.
  - **Llamadas rechazadas:** sin TLS, sin certificado, sin token, con un token inventado, haciéndose pasar por `datanode-1` y leyendo una réplica sin token de bloque o con uno falso.
  - **Usuarios:** `admin` no ve los archivos de `pedro`, y `pedro` no puede crear usuarios.
  - **Bloqueo:** el sexto intento y la contraseña correcta se rechazan durante el bloqueo, y la contraseña correcta vuelve a valer pasados 31 s.
  - **Disco:** una marca de texto repetida 50 000 veces no aparece en ninguna réplica de los cinco nodos de datos, y el archivo se recupera idéntico.

## Comandos
`ejecutar.sh`, desde la raíz del repositorio, con el clúster en marcha tras la evidencia de carga y recuperación:

```bash
evidencias/2026-11-07-seguridad/ejecutar.sh > evidencias/2026-11-07-seguridad/salida.txt 2>&1
```

`salida.txt` es la tercera ejecución. Las dos anteriores no sirven como evidencia, por fallos del propio script:
- **El resumen de los grupos de seguridad** no se generó, por un error de comillas en Python; ahora está en `grupos.py`.
- **«Solo un administrador crea usuarios» no probaba lo que dice:** la contraseña nueva llegaba vacía, y la CLI fallaba en el cliente sin llamar al servidor. El fallo estaba en `run.sh`.
- **El bloqueo se probaba con un proceso por intento**, y cada intento tardaba unos 3 s. En la segunda ejecución, la contraseña correcta se aceptó durante lo que debía ser el bloqueo: lo más probable es que llegara pasados los 30 s, pero no se guardó la hora de cada intento. Al repetirlo a mano con la hora, el bloqueo se cumplió. Ahora `bloqueo.py` hace todos los intentos desde un solo proceso y muestra la hora de cada uno.

En la sección de cifrado en disco, el recuento de réplicas incluye las de las cargas de `/marca.txt` de las ejecuciones anteriores. `ejecutar.sh` borra el archivo antes de cargarlo, pero sus réplicas siguen en disco hasta que pasa el periodo de gracia. La marca no aparece en ninguna.

No hay tokens, claves ni contraseñas en la salida. Las contraseñas llegan a `client-1` por la entrada estándar desde `deploy/aws/secrets/`, que no se versiona.

## Archivos
- `ejecutar.sh`: la prueba.
- `sondas.py`: llamadas gRPC que el clúster tiene que rechazar.
- `bloqueo.py`: intentos de inicio de sesión con la hora de cada uno.
- `grupos.py`: resumen de las reglas de cada grupo de seguridad.
- `salida.txt`: salida completa de la tercera ejecución.
