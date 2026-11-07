# Arranque en frío real al empezar una sesión del Learner Lab

- **Fecha:** 2026-11-07
- **Commit y versión:** contenedores `v0.10.0` (`91d8595`), que quedaron instalados al terminar la sesión anterior; `observar.sh` de `fc07220`
- **Entorno:** aws · los 9 hosts. La sesión anterior caducó a las 08:46 UTC sin `deploy.sh down`: el laboratorio paró las instancias y las arrancó todas a la vez al empezar esta sesión.
- **Cubre:** fase I §9.6 (arranque en frío). No es el experimento E9, que lo medirá con repeticiones en la etapa 10.
- **Resultado esperado:** sin intervención, Docker arranca los contenedores (`restart: always`), los volúmenes EBS se montan por UUID, Raft elige líder en cuanto hay dos servidores de metadatos, los nodos de datos se dan de alta y envían su informe de bloques, y los datos siguen íntegros.
- **Resultado obtenido:** coincide.
  - Instancias arrancadas a las 16:52:42 y sistemas en marcha entre las 16:52:47 y las 16:52:50, con el volumen de datos montado en los 8 hosts que lo tienen.
  - Los 12 contenedores arrancan entre las 16:52:56 y las 16:52:58, sin ningún reinicio.
  - `metadata-2` es elegido líder a las 16:52:59 (época 459).
  - Los cinco nodos de datos se dan de alta e informan de 43, 43, 40, 45 y 42 bloques (213 en total, las réplicas que había al terminar la sesión anterior) antes de las 16:53:01.
  - Del arranque de las instancias al clúster completo pasan unos 18 s.
  - `/grande.bin` (1 GiB) se lee con el mismo SHA-256 que antes de la parada.

La `v0.10.0` aún no tiene modo seguro (§9.5): llega con la `v0.11.0`, que se instala después de esta observación.

Las horas vienen de relojes de máquinas distintas, sincronizados con chrony. Por eso el alta de `datanode-1` (16:52:58,85) aparece unas décimas antes que la elección anotada por `metadata-2` (16:52:59,45). No se puede dar de alta en un servidor que todavía no es líder.

## Comandos
```bash
evidencias/2026-11-07-arranque-en-frio/observar.sh > evidencias/2026-11-07-arranque-en-frio/salida.txt 2>&1
```

`observar.sh` solo observa: no reinicia ni cambia nada. La comprobación de los datos (la última sección) se ejecutó justo después de las demás y se añadió al mismo `salida.txt`.

## Archivos
- `observar.sh`: estado de las instancias, volúmenes, contenedores y logs del arranque, y lectura de los datos.
- `salida.txt`: salida completa.
