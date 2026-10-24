# 0031 · Modo seguro tras cada elección de líder

- **Estado:** Aceptada
- **Fecha:** 2026-10-23
- **Requisitos relacionados:** RNF2, §5.2 (replicación y fallos); completa los ADR 0014 y 0018; C16, C27, C28

## Contexto
El estado del nodo (vivo, sospechoso o caído) depende de cuándo llegó el último latido. Ese dato solo lo
tiene el líder en memoria, porque no está en el log replicado. Un líder recién elegido todavía no ha
recibido ningún latido. Si aplicara sin más los umbrales del ADR 0018, declararía caídos a los nodos de
datos que aún no le han enviado nada, quitaría sus ubicaciones y lanzaría una re-replicación masiva sin motivo.

Pasa en dos situaciones:
- **Caída del líder de metadatos** (ADR 0014), uno de los escenarios del vídeo.
- **Arranque en frío.** El Learner Lab para las instancias al acabar la sesión y en la siguiente las
  arranca todas a la vez (Readme del lab, consultado el 2026-10-23; C27). Los servidores de metadatos
  pueden estar listos antes que los nodos de datos.

HDFS lo resuelve con su *safe mode*. El NameNode arranca en solo lectura y no re-replica hasta que los
informes de bloques cubren un porcentaje de los bloques. Tiene que esperar a esos informes porque no
guarda las ubicaciones.

## Opciones consideradas
1. **Nada especial.** Cada elección produce un falso positivo: copias de más y tráfico. En el arranque en
   frío, además, hay órdenes de re-replicación hacia nodos que todavía no han arrancado.
2. **Un periodo de gracia fijo** tras la elección, por ejemplo 30 s sin declarar caído a nadie. Es simple,
   pero no garantiza nada sobre los bloques: si a los 30 s todavía faltan nodos por arrancar, el problema
   vuelve. Además, durante la gracia se aceptan escrituras sin saber qué nodos están vivos.
3. **Modo seguro con una condición de salida sobre los bloques**, como en HDFS. La diferencia es que usa
   los latidos en lugar de los informes de bloques, porque las ubicaciones ya están en el log replicado.

## Decisión
Opción 3.

**Entrada:** cada vez que un servidor de metadatos pasa a ser líder, también en el arranque en frío.

**Mientras dura:**
- Los plazos de sospechoso (9 s) y de caído (30 s) cuentan desde la elección, así que no se declara caído a ningún nodo.
- No hay re-replicación, ni recolección de basura, ni borrado de réplicas de más. Un líder que todavía no
  sabe qué nodos están vivos no borra nada.
- **Lecturas:** se atienden. Las ubicaciones salen del log replicado, y si una réplica no responde, el
  cliente pasa a otra (ADR 0021).
- **Operaciones del cliente que cambian metadatos:** se rechazan con `UNAVAILABLE` + `SAFE_MODE_ACTIVE`, y
  el cliente las reintenta (ADR 0020). Son `AllocateBlocks`, `CommitFile`, `mkdir`, `mv`, `rm`, y también
  conceder o renovar arrendamientos.
- **Mensajes de los nodos de datos:** se atienden, porque son los que permiten salir. Son el alta, el
  latido, el informe de bloques y el aviso de bloque recibido.
- **Arrendamientos:** no caducan. Al salir, cada arrendamiento vigente vuelve a tener su TTL completo,
  para que una escritura interrumpida por el cambio de líder todavía pueda confirmarse.

**Salida**, en cuanto se cumpla una de estas condiciones:
- cada bloque de cada versión viva tiene al menos una réplica en un nodo de datos que ha enviado un latido
  desde la elección;
- se alcanza el tope `DFSHA_SAFE_MODE_MAX_WAIT_S`, de 60 s por defecto. En ese caso sale igualmente y
  registra un aviso con los bloques que no tienen ninguna réplica viva: esos bloques se han perdido, y
  esperar más no los recupera.

**Después**, todo funciona con normalidad:
- Un nodo que no ha enviado ningún latido desde la elección no cuenta como vivo para recibir bloques
  nuevos (ADR 0017).
- Ese nodo se declara caído a los 30 s de la elección, y sus bloques se re-replican según el ADR 0018.

**Despliegue:** el script de despliegue deja Docker activado al arrancar el sistema
(`systemctl enable docker`). Así, cuando el lab vuelve a arrancar las instancias, los contenedores vuelven
solos (ADR 0027).

## Consecuencias
- **Se gana:**
  - Ni el cambio de líder ni el arranque en frío lanzan re-replicaciones o borrados sin motivo.
  - En un cambio de líder con todos los nodos de datos vivos, el modo seguro termina en uno o dos
    latidos (3–6 s).
- **Se pierde:**
  - Las escrituras esperan a que termine el modo seguro, y esa espera se suma al tiempo de elección (ADR 0014).
  - Con el tope, el sistema vuelve a aceptar escrituras aunque haya bloques perdidos. La pérdida queda
    registrada, no se oculta.
  - Como cada arrendamiento recupera su TTL completo, un cliente muerto conserva el suyo hasta 30 s más.
- **Límite:** la condición de salida se fía de las ubicaciones del log. Si un nodo perdió bloques en disco
  sin dejar de enviar latidos, el modo seguro no lo detecta; lo detecta su siguiente informe de bloques.
- **Medición:** E7 y E9 del ADR 0028.
- **Términos nuevos en el glosario:** modo seguro y el código de motivo `SAFE_MODE_ACTIVE`.
