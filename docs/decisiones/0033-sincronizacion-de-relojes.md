# 0033 · Sincronización de relojes entre nodos

- **Estado:** Aceptada
- **Fecha:** 2026-10-23
- **Requisitos relacionados:** RNF6, RNF3; completa los ADR 0022 y 0023; C27

## Contexto
Varios mecanismos de seguridad comparan instantes fijados en un nodo con el reloj de otro:
- **Token de bloque** (10 min): lo firma el líder de metadatos y comprueba su caducidad el nodo de datos (ADR 0022).
- **`access_token`** (1 h): lo emite un servidor de metadatos, pero tras un cambio de líder lo comprueba otro.
- **Certificados del TLS mutuo** (ADR 0023): cada nodo comprueba sus fechas de validez con su propio reloj.

Si los relojes se separan, se rechazan tokens válidos o se aceptan tokens caducados.

Los arrendamientos no dependen de la sincronización: los gestiona solo el líder (ADR 0011), y tras una
elección recuperan su TTL completo (ADR 0031). Raft usa plazos relativos, no instantes. En el entorno local
todos los contenedores comparten el reloj de la máquina.

No se ha comprobado si las AMI de Ubuntu ya vienen configuradas con el servicio de hora de Amazon.

## Opciones consideradas
1. **Fiarse de la configuración que traiga la AMI.** No cuesta nada, pero lo que no se ha comprobado no
   se puede garantizar.
2. **Configurar chrony** con el servicio de hora de Amazon (Amazon Time Sync Service) y admitir un margen
   en las comprobaciones de caducidad.
3. **Prescindir de los instantes:** que el nodo de datos pregunte al servidor de metadatos si un token
   sigue vigente. Lo descartó el ADR 0022 porque convierte al servidor de metadatos en cuello de botella.

## Decisión
Opción 2.

**Configuración en el despliegue** (ADR 0027):
- El script de despliegue configura chrony en todas las instancias con el servicio de hora de Amazon, en
  la dirección de enlace local `169.254.169.123`. Es una dirección fija que no necesita salida a Internet.
- Después comprueba con `chronyc tracking` que el reloj está sincronizado; si no lo está, el despliegue falla.

**Margen en las comprobaciones de caducidad:**
- Las comprobaciones de los tokens admiten un margen de `DFSHA_CLOCK_SKEW_TOLERANCE_S`, 30 s por defecto.
- El margen es muy pequeño frente a la vida de los tokens (10 min y 1 h), y muy grande frente al desfase
  normal de chrony, que es de milisegundos.

**Excepción a «sin IP literales»:** `169.254.169.123` es la dirección fija de un servicio de AWS, no la de
un nodo, y no cambia entre sesiones. No va contra el motivo de RNF7 ni de C26. Solo puede aparecer en el
script de despliegue de `aws`, y la excepción queda anotada en `CONTRIBUTING.md` §8.

## Consecuencias
- **Se gana:**
  - Que el desfase de los relojes esté acotado queda garantizado por el despliegue, en vez de suponerse.
  - Un desfase residual no produce rechazos falsos.
- **Se pierde:**
  - Un token caducado se acepta hasta 30 s después de caducar.
  - El despliegue depende de un servicio de AWS; si chrony no sincroniza, el despliegue no termina.
- **Término nuevo en el glosario:** desfase de reloj.
