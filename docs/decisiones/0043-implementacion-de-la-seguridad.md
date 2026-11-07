# 0043 · Implementación de la seguridad: TLS mutuo en todas las conexiones, formatos y secretos

- **Estado:** Aceptada
- **Fecha:** 2026-11-07
- **Requisitos relacionados:** RNF6; ADR 0022, 0023, 0024, 0033 y 0041; fase I §10 (Tablas 30 y 31)

## Contexto
Los ADR 0022 a 0024 fijan qué protege cada mecanismo, pero no cómo se implementa. Al implementarlos en la
etapa 6 hubo que decidir lo que no recogían, y apareció una restricción técnica:

- **gRPC para Python no permite pedir un certificado de cliente sin exigirlo.** `ssl_server_credentials` solo
  ofrece `require_client_auth=True` o `False`, y con `False` el servidor no recibe el certificado del otro
  extremo. Comprobado el 2026-11-07: con `False`, el contexto de la llamada no trae ningún dato del certificado
  del nodo de datos que se conectó. La §10.4 eligió «TLS mutuo entre nodos; TLS de servidor más token para el
  cliente», y eso no se puede tener en un mismo puerto.
- Faltaban por fijar el formato de los tokens y del descriptor de archivo firmado, cómo se envuelve la clave
  de datos, cómo se lee el rol de un certificado, dónde viven los secretos, cómo se crea el primer
  administrador y el límite de intentos fallidos que la Tabla 30 dejó «para la fase II».

## Opciones consideradas
**Cliente y TLS**
1. **Un puerto para clientes y otro para nodos**, con TLS mutuo solo en el segundo. Cambia la Tabla 10 y los
   grupos de seguridad, y duplica cada servicio.
2. **TLS mutuo en todas las conexiones**: también el host cliente tiene un certificado de la CA interna, y el
   usuario se autentica además con su token.

**Intentos fallidos**
1. No limitarlos: solo frena scrypt.
2. **Bloquear un usuario unos segundos tras varios fallos seguidos**, con el contador en la memoria del líder.
3. Guardar el contador en etcd: sobrevive a un cambio de líder, pero cada intento fallido sería una escritura
   replicada.

## Decisión
Opción 2 en los dos casos. Además:

**Conexiones (cambia la §10.4)**
- Todas las conexiones usan TLS mutuo con la CA interna, también las del cliente y las de etcd, tanto con
  sus clientes como entre sus miembros. La negociación da TLS 1.3, comprobado en las pruebas.
- El rol del otro extremo sale del nombre `<rol>-<n>` del SAN de su certificado.
  - Las RPC de usuario exigen un certificado de rol `client` y un token de acceso.
  - Las RPC de los nodos de datos exigen el certificado de ese mismo nodo: el `node_id` de la petición tiene
    que coincidir con el del certificado, así que un nodo no puede hablar en nombre de otro.
  - Los nodos de datos atienden a clientes y a otros nodos de datos, y exigen siempre un token de bloque.

**Formatos**
- **Token de acceso:** el mensaje `AccessTokenClaims` (`user_id`, `is_admin`, caducidad), seguido de su
  HMAC-SHA256, en base64url. Viaja en los metadatos de la llamada como `authorization: Bearer <token>`.
- **Descriptor de archivo:** el mensaje `FileHandle` seguido de su HMAC-SHA256. El servidor comprueba la firma
  y que el descriptor es del usuario de la llamada.
- **Token de bloque:** el `BlockToken` del contrato, con el HMAC-SHA256 de los campos 1 a 3 serializados de
  forma determinista.
- **Separación de dominios:** cada tipo firmado lleva su propio prefijo dentro del HMAC, así que una firma de un
  tipo no vale para otro. El token de acceso y el descriptor comparten clave, porque solo los firman y
  verifican los servidores de metadatos.
- **Caducidad** con el margen de 30 s del ADR 0033.

**Claves y contraseñas**
- **Clave de datos:** se genera en `OpenFile` en modo creación y se envuelve con AES-256-GCM, la clave de
  envoltura y el `file_id` como dato asociado, que la liga a su archivo. Hasta la confirmación viaja envuelta
  dentro del descriptor firmado, y `CommitFile` la guarda en el archivo.
- **Contraseñas:** scrypt con n = 2^15, r = 8, p = 1 y una sal de 16 bytes por usuario.

**Usuarios**
- Las claves de etcd del ADR 0041 se amplían con `users/<user_id>` (el usuario) y `usernames/<nombre>` (el
  índice por nombre).
- El primer administrador, `admin`, lo crea el líder la primera vez que es elegido, con la contraseña del
  secreto de despliegue. Los demás usuarios los crea un administrador con `CreateUser`, desde la orden
  `dfsha useradd`.
- **Intentos fallidos:** tras 5 fallos seguidos, el usuario queda bloqueado 30 s.

**Secretos**
- `python -m dfsha.common.pki <directorio> <hosts>` crea la CA interna (EC P-256, 1 año), un certificado por
  host válido como servidor y como cliente, y las claves compartidas. Si ya existen, los reutiliza.
- Cada host recibe solo lo suyo:
  - **Servidores de metadatos:** clave de los tokens de acceso, clave de los tokens de bloque, clave de
    envoltura y contraseña del primer administrador.
  - **Nodos de datos:** solo la clave de los tokens de bloque.
  - **Cliente:** solo su certificado.
- Los componentes leen los secretos de `DFSHA_SECRETS_DIRECTORY`, por defecto `/run/secrets/dfsha`, montado
  desde fuera de la imagen.

## Consecuencias
- **Se gana:**
  - Todas las conexiones están autenticadas en los dos sentidos, sin puertos nuevos.
  - Un nodo de datos comprometido no puede suplantar a otro ante el servidor de metadatos.
  - La clave de envoltura solo está en los servidores de metadatos.
- **Se pierde:**
  - Cada máquina cliente necesita un certificado de la CA interna. En este despliegue el único cliente es
    `client-1`; un cliente fuera del clúster tendría que pedir el suyo.
  - El bloqueo por intentos fallidos vive en la memoria del líder: un cambio de líder lo reinicia.
- **Límite:** quien tenga la clave de la CA puede emitir certificados de cualquier rol, como ya decía la §10.4.
- **La fase I ya está entregada** y no se modifica; el cambio de la §10.4 entra en la tabla de cambios del
  informe (ADR 0006).
