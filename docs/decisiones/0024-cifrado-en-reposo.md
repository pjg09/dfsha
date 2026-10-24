# 0024 · Cifrado en reposo: cifrado de sobre en el cliente con AES-256-GCM

- **Estado:** Aceptada
- **Fecha:** 2026-10-23
- **Requisitos relacionados:** RNF6; aclaración A5; C25, C27

## Contexto
Según A5, los metadatos no necesitan cifrado, y la elección entre cifrar el volumen EBS o cifrar por bloque
queda a criterio del diseño: hay que elegir la opción que mejor se defienda en arquitectura.

## Opciones consideradas
1. **Cifrado del volumen EBS.** Es transparente y no requiere código, pero solo protege frente al robo del
   disco o de una instantánea de EBS: quien accede al sistema operativo del nodo lee en claro. Además, no
   deja ninguna decisión de diseño que defender.
2. **Cifrado en el nodo de datos, con una clave por nodo.** Protege el disco, pero el nodo y la red
   interna ven el texto en claro, y la re-replicación tiene que descifrar y volver a cifrar.
3. **Cifrado de sobre en el cliente.** Cada archivo tiene una clave de datos y cada bloque se cifra en el
   cliente. La clave de datos se guarda envuelta con una clave de envoltura que solo tienen los servidores de metadatos.

## Decisión
Opción 3.

**Claves:**
- Al crear un archivo, el servidor de metadatos genera una clave de datos aleatoria de 256 bits y la guarda
  envuelta con la clave de envoltura.
- En `open()` se la entrega al propietario autenticado, por TLS.
- La clave de envoltura es un secreto en un archivo de los hosts de metadatos, fuera del repositorio. No se
  usa KMS porque no hay credenciales de AWS en tiempo de ejecución (C27).

**Cifrado de cada bloque:**
- El cliente cifra con AES-256-GCM, usando un nonce aleatorio de 96 bits por bloque.
- El `block_id` va como dato asociado, para que no se puedan intercambiar bloques entre posiciones.

**Integridad:**
- `block_sha256` se calcula sobre el texto cifrado, y es lo que verifican los nodos de datos.
- La etiqueta GCM verifica el bloque de extremo a extremo en el cliente.

**Defensa en profundidad:** además, el volumen EBS se cifra con la clave gestionada `aws/ebs`. El Learner
Lab lo permite: se comprobó el 2026-10-23 con un volumen de prueba (C28).

## Consecuencias
- **Se gana:**
  - Ni los nodos de datos, ni sus discos, ni la red interna ven nunca el texto en claro.
  - La re-replicación copia texto cifrado sin necesitar claves.
  - La evidencia es sencilla: un volcado del bloque en disco.
- **Se pierde:**
  - La clave de envoltura es un punto crítico: quien comprometa un servidor de metadatos puede descifrarlo todo.
  - El cliente gasta CPU en cifrar; se mide (ADR 0028).
  - Los metadatos van en claro, como permite A5: nombres y tamaños de archivo quedan visibles en el disco de los servidores de metadatos.
- **Fuera de alcance:** la rotación de la clave de envoltura.
- **Términos nuevos en el glosario:** cifrado de sobre, clave de datos y clave de envoltura.
