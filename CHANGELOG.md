# Changelog

Generado automáticamente por semantic-release a partir de los commits. No editar a mano.

## [0.8.0](https://github.com/pjg09/dfsha/compare/v0.7.0...v0.8.0) (2026-11-07)

### Funcionalidades

* **client:** añade la biblioteca y la línea de órdenes dfsha ([d431357](https://github.com/pjg09/dfsha/commit/d43135765e5adb40420cc83680850fccbe65a23e))

### Correcciones

* **datanode:** rechaza un block_id repetido con otro contenido ([be54bcf](https://github.com/pjg09/dfsha/commit/be54bcf8dee8586202a61b126e126fbf8c5d65f8))

## [0.7.0](https://github.com/pjg09/dfsha/compare/v0.6.0...v0.7.0) (2026-11-07)

### Funcionalidades

* **datanode:** conecta el nodo de datos con el líder de metadatos ([9766d89](https://github.com/pjg09/dfsha/commit/9766d89bc0e7c32ffe8b14932ddd1e4d74f00bec))
* **metadata:** usa la dirección que envía el nodo al darse de alta ([9607a78](https://github.com/pjg09/dfsha/commit/9607a78f5b1cb9dc85d09df4ecc5fce25053c016))
* **proto:** añade la dirección del nodo a RegisterDataNodeRequest ([f8a4876](https://github.com/pjg09/dfsha/commit/f8a48762e65676487d88eb99040d8b86491afdd2))

## [0.6.0](https://github.com/pjg09/dfsha/compare/v0.5.0...v0.6.0) (2026-11-06)

### Funcionalidades

* **metadata:** añade el servicio de metadatos sobre etcd ([0950154](https://github.com/pjg09/dfsha/commit/0950154c27815cb591caa321c515cf57f6c6d349))
* **proto:** añade los registros internos del servidor de metadatos ([626a25e](https://github.com/pjg09/dfsha/commit/626a25efaf307cc01a6e0185cc014b6f4064b931))

## [0.5.0](https://github.com/pjg09/dfsha/compare/v0.4.0...v0.5.0) (2026-11-06)

### Funcionalidades

* **metadata:** añade la elección del líder con cercado ([1f81bfa](https://github.com/pjg09/dfsha/commit/1f81bfa50dcfcbb41dad44cac53d589689094b73))

### Correcciones

* **metadata:** acepta revocar un arrendamiento de etcd que ya no existe ([7b8493d](https://github.com/pjg09/dfsha/commit/7b8493dda729a80f6a4d194963bac0952760750b))

## [0.4.0](https://github.com/pjg09/dfsha/compare/v0.3.0...v0.4.0) (2026-11-06)

### Funcionalidades

* **metadata:** añade el cliente de etcd del servidor de metadatos ([364cdec](https://github.com/pjg09/dfsha/commit/364cdece86cb7531e430ac3fab1b2fd2cd5cd1f7))
* **proto:** añade el subconjunto de la API v3 de etcd ([b2669c1](https://github.com/pjg09/dfsha/commit/b2669c1d17854b8a1337eaddee305bd2170e455c))
* **proto:** añade la época del líder a las respuestas con órdenes ([2598e63](https://github.com/pjg09/dfsha/commit/2598e6309141d45d92e57658f8b61fafb51f630a))

## [0.3.0](https://github.com/pjg09/dfsha/compare/v0.2.0...v0.3.0) (2026-11-06)

### Funcionalidades

* **common:** añade la lectura de booleanos a la configuración ([eaecc8c](https://github.com/pjg09/dfsha/commit/eaecc8c03d0c03c5e05f860e600f071848da3211))
* **datanode:** añade el almacén de bloques y DataNodeService ([3e24df4](https://github.com/pjg09/dfsha/commit/3e24df4a1352987a38de053061be7748145b17a5))

## [0.2.0](https://github.com/pjg09/dfsha/compare/v0.1.0...v0.2.0) (2026-11-06)

### Funcionalidades

* **common:** añade configuración, logs y errores con código de motivo ([23c4480](https://github.com/pjg09/dfsha/commit/23c4480836bea6ac25815949c8e341e418ed16c4))
* **proto:** añade los contratos gRPC del Anexo A y su código generado ([c381859](https://github.com/pjg09/dfsha/commit/c381859f8585e6be61999b0e1b1fd8c9544382e9))

## [0.1.0](https://github.com/pjg09/dfsha/compare/v0.0.0...v0.1.0) (2026-11-06)

### Funcionalidades

* cierra el diseño de la fase I e inicia la fase II ([ce5f1c2](https://github.com/pjg09/dfsha/commit/ce5f1c276d0a911f06d7fcdb4734848532ba8902))
