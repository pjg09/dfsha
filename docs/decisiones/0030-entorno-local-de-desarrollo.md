# 0030 · Entorno local de desarrollo con las mismas imágenes que AWS

- **Estado:** Aceptada
- **Fecha:** 2026-10-23
- **Requisitos relacionados:** §5 («no basta una simulación local monolítica»), §5.3 (instrucciones reproducibles); completa lo que el ADR 0027 dejó pendiente; C27

## Contexto
El ADR 0027 fija que el producto se ejecuta en AWS y dejó pendiente si se mantiene el entorno `local` de
`convenciones.md` §2. El enunciado no lo exige, y por §5 tampoco puede ser el producto final. Pero
desarrollar solo contra AWS tiene un coste:
- cada prueba consume crédito;
- la sesión del Learner Lab caduca a las 4 h (C27);
- desplegar en 9 instancias tarda minutos.

## Opciones consideradas
1. **Solo AWS.** Hay un único entorno que mantener, pero cada iteración es lenta y cuesta crédito.
2. **Entorno local como herramienta de desarrollo.** El clúster completo en una sola máquina con Docker
   Compose, usando las mismas imágenes y configuración que en AWS.

## Decisión
Opción 2.

**Qué es `deploy/local/`:** un `compose.yaml` con el clúster completo: `metadata-1` a `metadata-3`,
`datanode-1` a `datanode-5` y `client-1`.

**Qué comparte con AWS (`deploy/aws/`):**
- las imágenes;
- los nombres de host (ADR 0003);
- las variables de entorno;
- los certificados (ADR 0023), generados con el mismo script.

**Qué cambia:** solo la resolución de nombres (la red de Docker frente a `/etc/hosts`) y los volúmenes
(volúmenes Docker frente a volúmenes EBS).

**Regla de sincronización:** todo cambio de imagen, configuración o puertos se hace en los dos entornos
en el mismo commit.

**Usos:**
- desarrollar;
- ejecutar las pruebas automatizadas;
- ensayar los escenarios de fallo con `docker stop` antes de llevarlos a AWS.

**Para qué no vale:** las evidencias de §5.2 y los experimentos (ADR 0028) se obtienen siempre en AWS.

## Consecuencias
- **Se gana:** iterar es rápido y gratis, y las caídas se pueden reproducir sin gastar crédito.
- **Se pierde:**
  - Hay dos ficheros de despliegue que mantener sincronizados.
  - El entorno local no reproduce la red real: latencia, ancho de banda y créditos de CPU. Un resultado
    local no sirve como evidencia.
