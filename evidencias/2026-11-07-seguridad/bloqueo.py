"""Bloqueo tras 5 intentos fallidos seguidos (ADR 0043), con la hora de cada intento.
Se ejecuta dentro de client-1 como python -c <script> <usuario> <contraseña>; ejecutar.sh le pasa la
contraseña por la entrada estándar del contenedor, así que no queda en la línea de órdenes de ssh."""

import sys
import time
from pathlib import Path

import grpc

from dfsha.common.errors import DfshaError, Reason
from dfsha.common.tls import load_identity, make_channel_factory
from dfsha.v1 import metadata_pb2, metadata_pb2_grpc

username = sys.argv[1]
password = sys.argv[2]
create_channel = make_channel_factory(load_identity(Path("/run/secrets/dfsha")))
stubs = [metadata_pb2_grpc.MetadataServiceStub(create_channel(f"metadata-{n}:50051")) for n in (1, 2, 3)]
start = time.monotonic()


def attempt(label: str, secret: str) -> None:
    for stub in stubs:  # el que responda sin NODE_NOT_LEADER es el líder
        try:
            stub.Authenticate(metadata_pb2.AuthenticateRequest(username=username, password=secret), timeout=10)
            print(f"t = {time.monotonic() - start:5.1f} s  {label}: aceptado")
            return
        except grpc.RpcError as error:
            failure = DfshaError.from_rpc_error(error)
            if failure.reason == Reason.NODE_NOT_LEADER:
                continue
            print(f"t = {time.monotonic() - start:5.1f} s  {label}: rechazado, {failure.code.name}: {failure.message}")
            return


for number in range(1, 7):
    attempt(f"intento {number} con contraseña incorrecta", "contraseña-incorrecta")
attempt("contraseña correcta durante el bloqueo", password)
time.sleep(max(0.0, 31 - (time.monotonic() - start)))
attempt("contraseña correcta pasados 31 s", password)
