# 0037 · Imágenes Docker en ECR, construidas una vez por versión

- **Estado:** Aceptada
- **Fecha:** 2026-11-06
- **Requisitos relacionados:** §5.1 (procesos o contenedores separados), §5.3 (instrucciones reproducibles); aclaración A10; ADR 0027 y 0030

## Contexto
El ADR 0027 fija una imagen por rol, con la versión como etiqueta, y la §14 de la fase I dejó pendiente
cómo llegan las imágenes a las instancias: construirlas en cada una o usar ECR. Se comprobó el 2026-11-06
en el Learner Lab, con una t3.micro con Ubuntu 26.04 LTS y una imagen de prueba (`python:3.12-slim` con
`grpcio`, `grpcio-tools` y `cryptography`):
- Docker 29.1.3 y Docker Compose 2.40.3, de los repositorios de Ubuntu, se instalan en 31 s.
- Construir la imagen en la instancia tarda 20 s; obtenerla de ECR, 5 s.
- Con `LabInstanceProfile`, la instancia inicia sesión en ECR y lee. También puede escribir, en contra de
  lo que daban por hecho los consejos y la §14.
- Desde la máquina de administración, con las credenciales de la sesión, se crea el repositorio y se envía
  la imagen en 21 s.

Además, la defensa incluye una demostración en vivo (A10): el clúster tiene que levantarse en una sesión
nueva del Learner Lab sin sorpresas.

## Opciones consideradas
1. **Construir la imagen en cada instancia**, a partir de un clon del repositorio. No usa ningún servicio
   más, pero son nueve construcciones independientes: si entre una y otra cambia la imagen base o una
   dependencia, las instancias ejecutan imágenes distintas con la misma etiqueta. Cada despliegue depende
   de Docker Hub y de PyPI, y gasta créditos de CPU de las t3.
2. **Construir una vez en la máquina de administración y enviarla a ECR.** Las instancias la obtienen con
   `LabInstanceProfile`.
3. **Construir en una instancia del clúster y enviarla a ECR desde ella.** No hace falta Docker en la
   máquina de administración, pero el despliegue de las demás instancias tiene que esperar a esa.

## Decisión
Opción 2.
- **Repositorios:** uno por imagen en `us-east-1`: `dfsha-metadata`, `dfsha-datanode` y `dfsha-client`,
  con etiquetas inmutables (`imageTagMutability=IMMUTABLE`). La etiqueta es la versión (ADR 0027), así que
  una versión siempre corresponde a los mismos bytes.
- **Script de despliegue:** construye las tres imágenes en la máquina de administración, las envía a ECR si
  esa versión aún no está, y en cada instancia inicia sesión en ECR con `LabInstanceProfile` y obtiene la
  imagen de su rol.
- **Instancias:** Ubuntu 26.04 LTS, con `docker.io` y `docker-compose-v2` de sus repositorios.
- **Entorno local** (ADR 0030): construye las mismas imágenes con los mismos Dockerfile y no usa ECR.

## Consecuencias
- **Se gana:**
  - Las nueve instancias ejecutan exactamente la misma imagen, identificada por su versión.
  - Desplegar no construye nada en las instancias. Es más rápido, no gasta créditos de CPU y es más
    fiable para la demostración en vivo (A10).
- **Se pierde:**
  - Un servicio de AWS más, con un coste de almacenamiento de céntimos.
  - La máquina de administración necesita Docker. Ya lo necesitaba para el entorno local (ADR 0030).
- **Límite:** las imágenes viven en ECR mientras exista la cuenta del Learner Lab. Si se pierden, el script
  las vuelve a construir a partir de la etiqueta de Git de esa versión.
- **Corrige** la §14 de la fase I, que decía que el Learner Lab solo permitía leer de ECR desde las
  instancias. El documento de la fase I ya está entregado y no se modifica.
- **Término nuevo en el glosario:** registro de imágenes.
