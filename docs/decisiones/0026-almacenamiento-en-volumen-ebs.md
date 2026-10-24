# 0026 · Almacenamiento de bloques en un volumen EBS por nodo de datos

- **Estado:** Aceptada
- **Fecha:** 2026-10-23
- **Requisitos relacionados:** RNF2, §5.1; C28, C29

## Contexto
Si un volumen EBS no queda bien montado, el nodo escribe en el disco raíz sin dar ningún error, y el disco
raíz se borra al terminar la instancia (C29). En HDFS, cada bloque es un archivo local del DataNode.

## Opciones consideradas
1. **Disco raíz.** Es lo más simple, pero sus 8 GiB se comparten con el sistema operativo y Docker, y se
   pierden al terminar la instancia.
2. **Un volumen EBS gp3 propio para cada nodo de datos.**
3. **S3 como almacén.** Dejaría de ser un DFS propio, y las réplicas no tendrían sentido.

## Decisión
Opción 2.

**El volumen:**
- gp3 de 10 GiB al principio, con la etiqueta `Name=dfsha-datanode-<n>-data`.
- Cifrado con la clave gestionada `aws/ebs` (ADR 0024).
- El script de despliegue lo monta por UUID con `nofail`, y llega al contenedor como volumen.

**Comprobación al arrancar:** el nodo de datos verifica que su directorio de datos es un punto de montaje y
que contiene una marca con su `node_id`. Si no, no arranca.

**Organización en disco:**
- Un archivo local por bloque, con el `block_id` como nombre y repartidos en subdirectorios por prefijo.
- El área temporal va en el mismo volumen, porque el renombrado atómico exige que sea el mismo sistema de archivos.

## Consecuencias
- **Se gana:**
  - Los datos sobreviven aunque se termine la instancia.
  - Si falta el volumen, el error es visible en vez de silencioso.
- **Se pierde:**
  - El volumen se cobra aunque la instancia esté parada.
  - El tamaño es fijo; ampliarlo es un paso manual.
