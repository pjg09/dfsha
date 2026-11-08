# Acceso RF3, con la versión final

- **Fecha:** 2026-11-08, de 04:40:05 a 04:40:38 UTC
- **Commit y versión:** imágenes `v0.13.1` (`17c5dbd`), la versión final de la etapa 10; scripts de `32c0dba`
- **Entorno:** aws · `metadata-1` a `metadata-3` (t3.small), `datanode-1` a `datanode-5` (t3.micro, volumen gp3 de 10 GiB cifrado), `client-1` (t3.small, ADR 0045); `us-east-1a`. Configuración por defecto, sin los parámetros de los experimentos.
- **Cubre:** prueba mínima «Acceso RF3» de §5.2, repetida con la versión final. La primera ejecución está en [`2026-11-07-acceso-rf3`](../2026-11-07-acceso-rf3/).
- **Resultado esperado:** `read()` y `write()` con la semántica declarada (fase I §7): los cuatro modos de escritura, solo los bloques afectados son nuevos, y las garantías G2, G3 y G4.
- **Resultado obtenido:** coincide, con la misma salida que la primera ejecución salvo los hashes y las versiones de `/texto.txt`:
  - **Biblioteca:** las seis escrituras dan un SHA-256 igual al del modelo local: creación, anexado, dos modificaciones parciales y dos reemplazos. Solo se crean los bloques que tocan; por ejemplo, la modificación parcial de 1 000 bytes en la frontera de los bloques 0 y 1 crea esos dos y reutiliza el 2 y el 3.
  - **Garantías:** G4 (un `open()` durante una escritura sin confirmar ve la versión anterior), G3 (quien abrió antes sigue leyendo su versión entera) y G2 (un `open()` posterior ve la versión confirmada) dan `True`.
  - **CLI:** `read`, `write` y `append` sobre `/texto.txt` dan «hola MUNDO desde AWS».

## Comandos
```bash
evidencias/2026-11-07-acceso-rf3/ejecutar.sh > evidencias/2026-11-08-acceso-rf3/salida.txt 2>&1
```

## Archivos
- `salida.txt`: salida completa.
