# 0023 · Cifrado en tránsito: TLS con el cliente y TLS mutuo entre nodos

- **Estado:** Aceptada
- **Fecha:** 2026-10-23
- **Requisitos relacionados:** RNF6; C23, C30

## Contexto
RNF6 exige cifrado en tránsito y protección de las comunicaciones entre nodos. El lab de gRPC del profesor
usa `add_insecure_port`, sin TLS (C23).

## Opciones consideradas
1. **Sin TLS dentro de la VPC.** Incumple RNF6.
2. **TLS solo de servidor en todas las conexiones.** El canal va cifrado, pero los nodos no se autentican
   entre sí: cualquier proceso de la VPC podría hacerse pasar por un nodo de datos.
3. **TLS mutuo entre nodos, y TLS de servidor más token para el cliente.**

## Decisión
Opción 3.

**Certificados:**
- El script de despliegue genera una CA interna del proyecto y un certificado por nombre de host, con el
  nombre `<rol>-<n>` en el SAN.
- En las RPC internas (latidos, informes de bloques, replicación), cada nodo exige un certificado firmado
  por esa CA y de un rol autorizado para esa llamada.

**Cliente:** verifica el certificado del servidor con la CA y se autentica con su token (ADR 0022).

**Secretos:** las claves privadas nunca se versionan; `.gitignore` ya excluye `*.pem` y `*.key`.

**Red:**
- Grupos de seguridad `dfsha-sg-<rol>`, con los puertos del clúster abiertos solo entre los grupos del proyecto.
- SSH abierto solo desde la IP de quien administra (C30).

## Consecuencias
- **Se gana:** canal cifrado y nodos autenticados entre sí.
- **Se pierde:**
  - La clave de la CA pasa a ser el secreto más sensible del despliegue.
  - La rotación de certificados es manual.
  - TLS consume CPU; el coste se mide (ADR 0028).
