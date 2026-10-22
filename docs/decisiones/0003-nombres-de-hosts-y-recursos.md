# 0003 · Nombres de hosts y de recursos de red y de AWS

- **Estado:** Aceptada
- **Fecha:** 2026-10-21
- **Requisitos relacionados:** RNF7 (transparencia de localización), §5.1 (despliegue en AWS Academy)

## Contexto
RNF7 prohíbe direcciones de nodos codificadas de forma estática en el cliente. En AWS Academy las IP
públicas cambian en cada sesión del Learner Lab, así que una IP fija además de incumplir el requisito
deja de funcionar al día siguiente. La cuenta del lab también contiene recursos de otros laboratorios,
y eso complica identificar los del proyecto. Un nombre de host con `_` no es válido según RFC 1123.

## Opciones consideradas
1. Referirse a los nodos por IP.
2. Nombres libres para cada nodo.
3. Nombres lógicos con el patrón `<rol>-<n>`, iguales en todos los entornos, y prefijo `dfsha-` en los
   recursos de AWS.

## Decisión
Opción 3, con el detalle de [`convenciones.md` §4](../convenciones.md#4-nombres-de-host-y-recursos-de-red):
- Hosts `metadata-1`, `datanode-1…n`, `client-1`. Lista cerrada de roles, numeración desde 1, solo `a-z0-9-`.
- El mismo nombre en Docker Compose, en el `hostname` de la EC2, en los logs y en los diagramas.
- En AWS, la etiqueta `Name` es `dfsha-<rol>-<n>` y todos los recursos llevan la etiqueta `project=dfsha`.
- No hay IP literales en el código ni en la configuración versionada.

## Consecuencias
- El cliente solo conoce nombres lógicos, lo que ya cubre parte de RNF7.
- Un log o una evidencia se puede relacionar con el diagrama sin traducir nada.
- **Pendiente:** cómo se resuelven esos nombres en AWS (`/etc/hosts` generado, DNS privado o descubrimiento
  a través del servidor de metadatos). Es una decisión de diseño y tendrá su propio ADR en la fase I.
