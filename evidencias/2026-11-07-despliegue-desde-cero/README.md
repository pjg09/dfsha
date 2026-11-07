# Despliegue desde cero con una orden

- **Fecha:** 2026-11-07
- **Commit y versión:** `ddb9bc6` · imágenes `0.9.2.dev3-gddb9bc6`, construidas por la propia orden (mismo código de la aplicación que `v0.9.1`)
- **Entorno:** aws · los 9 hosts del clúster, en una cuenta sin ningún recurso del proyecto (0 instancias, 0 volúmenes y 0 grupos `dfsha-sg-*`, tras `deploy.sh down`)
- **Cubre:** condición de cierre de la etapa 7: el clúster se levanta desde cero con un comando y pasa la prueba de carga y recuperación (fase I §3.6)
- **Resultado esperado:** `deploy/aws/deploy.sh all` construye las imágenes, crea los recursos, instala los 9 hosts y deja el clúster en marcha sin intervención.
- **Resultado obtenido:** coincide.
  - `all` termina sin errores en 6 min 50 s: imágenes en ECR en 24 s, recursos e instancias en 4 min 37 s, instalación en 1 min 49 s.
  - Los 12 contenedores quedan en marcha (`status.txt`).
  - La prueba de carga y recuperación pasa: 192 réplicas repartidas en 38, 38, 38, 39 y 39, el mismo SHA-256 y un pico de memoria de 94 a 145 MiB por nodo de datos.

## Comandos
```bash
deploy/aws/deploy.sh down        # dos veces: la primera dejó dos grupos de seguridad (ver abajo)
deploy/aws/deploy.sh all > evidencias/2026-11-07-despliegue-desde-cero/salida-all.txt 2>&1
deploy/aws/deploy.sh status > evidencias/2026-11-07-despliegue-desde-cero/status.txt 2>&1
NEW_PASSWORD_FILE=deploy/aws/secrets/pedro-password deploy/aws/run.sh dfsha admin useradd pedro
evidencias/2026-11-07-carga-y-recuperacion/ejecutar.sh > evidencias/2026-11-07-despliegue-desde-cero/carga-y-recuperacion.txt 2>&1
```

El primer `down` no borró `dfsha-sg-client` ni `dfsha-sg-datanode`, porque las reglas de `dfsha-sg-metadata` aún los citaban. Se corrigió en `ddb9bc6` (dos pasadas), y el segundo `down` los borró.

## Archivos
- `salida-all.txt`: salida completa de `deploy.sh all`.
- `status.txt`: instancias y contenedores al terminar.
- `carga-y-recuperacion.txt`: la prueba de carga y recuperación sobre el clúster recién levantado.
