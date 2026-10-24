# 0022 · Autenticación de usuarios, autorización por propietario y tokens de bloque

- **Estado:** Aceptada
- **Fecha:** 2026-10-23
- **Requisitos relacionados:** RF1, RNF6; C5, C20, C25

## Contexto
Según RF1, cada usuario autenticado solo accede a su propio espacio de nombres. RNF6 exige autenticación y
autorización. El plano de datos va directamente del cliente a los nodos de datos (C5), así que un nodo de
datos tiene que poder decidir si atiende una petición sin preguntar al servidor de metadatos (C20).

## Opciones consideradas
**Usuarios:**
1. **Un certificado de cliente por usuario (mTLS).** Es seguro, pero gestionar un certificado por usuario es engorroso.
2. **Usuario y contraseña, a cambio de un token de acceso con caducidad.**
3. **Un proveedor externo (OAuth, Cognito).** Queda fuera del alcance y del Learner Lab.

**Autorización en los nodos de datos:**
- **a) Ninguna.** Cualquiera que conozca un `block_id` puede leerlo.
- **b) Consultar al servidor de metadatos en cada acceso.** Lo convierte en cuello de botella (C20).
- **c) Un token de bloque firmado por el servidor de metadatos.**

## Decisión
Opción 2 para los usuarios y opción c en los nodos de datos.

**Usuarios:**
- Los da de alta un comando de administración; no hay autorregistro.
- La contraseña se guarda con scrypt y una sal por usuario.
- `Authenticate` devuelve un `access_token` firmado con HMAC-SHA256, que contiene el `user_id` y caduca en 1 h.

**Autorización en el servidor de metadatos:** en cada RPC comprueba el token y que la ruta pertenece al
espacio de nombres del usuario. Si no, responde `UNAUTHENTICATED` o `PERMISSION_DENIED`.

**Autorización en los nodos de datos:**
- Junto con las ubicaciones, el servidor de metadatos entrega un **token de bloque**: `block_id`,
  operación (`read` o `write`) y caducidad de 10 min, firmado con una clave compartida entre los
  servidores de metadatos y los nodos de datos.
- El nodo de datos verifica la firma y la caducidad, con el margen de reloj del ADR 0033.
- Un lector que tarde más de 10 min pide tokens nuevos.

**Órdenes entre nodos** (re-replicación): las autentica el mTLS (ADR 0023).

## Consecuencias
- **Se gana:** el plano de datos autoriza sin consultar al servidor de metadatos.
- **Se pierde:**
  - Un token solo se revoca cuando caduca: 1 h el de acceso, 10 min el de bloque.
  - Las claves HMAC son secretos que no se versionan y que el despliegue tiene que repartir.
- **Fuera de alcance:** compartir archivos entre usuarios (RF1 no lo exige).
- **Término nuevo en el glosario:** token de bloque.
