# 0036 · Evidencias y material del informe durante la fase II

- **Estado:** Aceptada
- **Fecha:** 2026-11-06
- **Requisitos relacionados:** §5.1 (evidencia observable), §5.2 (pruebas mínimas), §5.3 (informe técnico final y vídeo); aclaración A2; ADR 0006 y 0028

## Contexto
§5.2 pide una evidencia para cada una de las siete pruebas mínimas, y el informe técnico final (§5.3)
tiene que contar las pruebas, los resultados y las limitaciones. El enunciado no fija el formato de las
evidencias. El informe se redactará al final de la fase II, con el sistema terminado, para no reescribirlo
cada vez que cambie la implementación.

Redactarlo al final solo es viable si el material ya existe cuando se escribe. Lo que vive en el
repositorio no se pierde: el código, los `.proto`, los ADR y el historial de commits cubren las APIs, los
algoritmos y los cambios de diseño (ADR 0006). Lo que sí se pierde si no se registra en el momento:
- **La ejecución en AWS.** La sesión del Learner Lab termina, las IP cambian, y una caída de nodo o una
  medición no se repiten igual sin volver a desplegar.
- **El contexto de una medición:** con qué versión, qué configuración y en qué instancias se hizo. Sin él,
  el número no se puede defender.
- **Las limitaciones y los problemas** que aparecen al implementar, y cómo se resolvieron. Si no pasan por
  un ADR, solo quedan en la memoria.

## Opciones consideradas
1. **Capturas en un documento aparte**, como en las prácticas del curso. Una captura no se puede comprobar
   ni buscar, y el documento duplica el informe.
2. **Reunir las evidencias al final**, antes de redactar el informe. Obliga a repetir todas las pruebas en
   AWS en pocos días y deja sin registrar lo que ya no se puede repetir.
3. **Registrar cada evidencia cuando se produce**, en texto y en el repositorio, con un índice que muestra
   qué falta.

## Decisión
Opción 3.

**Cuándo se registra una evidencia.** En el momento, no después:
- una prueba mínima de §5.2 pasa por primera vez en el entorno `aws`, o vuelve a pasar después de un
  cambio que la afecta;
- se ejecuta un experimento del ADR 0028;
- se provoca un fallo a propósito: caída de un nodo de datos o del líder, réplica desconectada;
- antes de terminar una sesión del Learner Lab en la que pasó algo de lo anterior y aún no se registró.

Una ejecución en `local` sirve para desarrollar, pero no es evidencia del producto (ADR 0030).

**Formato.**
- Un directorio `evidencias/AAAA-MM-DD-<escenario>/` por evidencia. Las mediciones de los experimentos
  siguen en `bench/resultados/` (ADR 0028), y la evidencia de un experimento enlaza a su CSV.
- Primero, texto: los comandos ejecutados con su salida completa, los logs de los nodos implicados y los
  hashes. Una captura PNG solo para lo que no tiene salida de texto, como la consola de AWS.
- Cada directorio lleva un `README.md` con la fecha, el commit (`git rev-parse --short HEAD`) y la
  versión, el entorno y los hosts, la prueba o el experimento que cubre, los comandos, el resultado
  esperado según el diseño y el resultado obtenido.
- Antes de commitear se quitan de la salida los tokens, las claves y las credenciales
  (`CONTRIBUTING.md` §8). Las IP pueden quedar: `evidencias/` es el único sitio donde se admiten.

**Índice.** `evidencias/README.md` tiene una fila por cada prueba mínima de §5.2 y por cada experimento
E1–E9, con su estado y el directorio que lo demuestra. Una fila sin evidencia es una evidencia que falta.

**Material del informe.** `docs/fase-2/notas.md` recoge, en viñetas con fecha y commit, lo que el informe
necesitará y no está en otro sitio: las limitaciones descubiertas y los problemas encontrados, con cómo se
resolvieron. Un cambio de diseño no va ahí: va en un ADR (ADR 0006).

**El informe** se redacta al final a partir de esas fuentes: los ADR (cambios frente a la fase I), el
código y los `.proto` (APIs y algoritmos), `evidencias/` y `bench/resultados/` (pruebas y resultados) y
`docs/fase-2/notas.md` (limitaciones).

## Consecuencias
- **Se gana:** el informe se escribe sin reconstruir nada de memoria. El índice dice en cualquier momento
  qué pruebas faltan, las evidencias se pueden comprobar en el repositorio, y el vídeo y la defensa salen
  del mismo material.
- **Se pierde:** tiempo en cada sesión de pruebas para guardar la salida y rellenar el `README.md`.
- **Límite:** la regla solo funciona si se cumple en el momento. Por eso también está en `CLAUDE.md`, para
  que cada sesión de Claude Code proponga registrar la evidencia cuando se dé uno de los casos.
- **Pendiente:** preguntar al profesor si le valen las evidencias en texto en el repositorio o las quiere
  como capturas dentro del informe. Si pide capturas, se sacan de estos directorios.
