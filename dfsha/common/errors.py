"""Errores del sistema: código de estado gRPC más código de motivo (fase I §5.4).

Cada error viaja como un estado gRPC estándar con un ``google.rpc.ErrorInfo`` en sus
detalles: el motivo es uno de los códigos de la Tabla 20 y el dominio es ``dfsha.v1``.
El mensaje está en español y es para el usuario; el motivo es para programas y pruebas.
"""

from collections.abc import Mapping
from enum import StrEnum

import grpc
from google.protobuf import any_pb2
from google.rpc import error_details_pb2, status_pb2
from grpc_status import rpc_status

ERROR_DOMAIN = "dfsha.v1"


class Reason(StrEnum):
    """Códigos de motivo de la Tabla 20 de la fase I."""

    ACCESS_TOKEN_EXPIRED = "ACCESS_TOKEN_EXPIRED"
    BLOCK_TOKEN_INVALID = "BLOCK_TOKEN_INVALID"
    PATH_NOT_FOUND = "PATH_NOT_FOUND"
    PATH_ALREADY_EXISTS = "PATH_ALREADY_EXISTS"
    PATH_INVALID = "PATH_INVALID"
    BLOCK_RANGE_INVALID = "BLOCK_RANGE_INVALID"
    DIRECTORY_NOT_EMPTY = "DIRECTORY_NOT_EMPTY"
    FILE_VERSION_EXPIRED = "FILE_VERSION_EXPIRED"
    LOCK_CONFLICT = "LOCK_CONFLICT"
    LEASE_EXPIRED = "LEASE_EXPIRED"
    VERSION_CONFLICT = "VERSION_CONFLICT"
    BLOCK_CORRUPTED = "BLOCK_CORRUPTED"
    BLOCK_LOST = "BLOCK_LOST"
    NODE_NOT_LEADER = "NODE_NOT_LEADER"
    SAFE_MODE_ACTIVE = "SAFE_MODE_ACTIVE"
    QUORUM_NOT_REACHED = "QUORUM_NOT_REACHED"


class DfshaError(Exception):
    """Error con su código de estado gRPC, su motivo y datos adicionales.

    ``metadata`` lleva datos para el programa que recibe el error, por ejemplo
    ``leader_addr`` con ``NODE_NOT_LEADER``.
    """

    def __init__(
        self,
        code: grpc.StatusCode,
        message: str,
        reason: Reason | None = None,
        metadata: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.reason = reason
        self.metadata: dict[str, str] = dict(metadata or {})

    def __repr__(self) -> str:
        return f"DfshaError({self.code.name}, {self.reason}, {self.message!r})"

    def to_status(self) -> grpc.Status:
        """Convierte el error en un estado gRPC para ``context.abort_with_status()``."""
        status = status_pb2.Status(code=self.code.value[0], message=self.message)
        if self.reason is not None:
            info = error_details_pb2.ErrorInfo(
                reason=self.reason.value, domain=ERROR_DOMAIN, metadata=self.metadata
            )
            detail = any_pb2.Any()
            detail.Pack(info)
            status.details.append(detail)
        return rpc_status.to_status(status)

    @classmethod
    def from_rpc_error(cls, error: grpc.RpcError) -> "DfshaError":
        """Reconstruye el error que recibió el cliente de una llamada gRPC."""
        if not isinstance(error, grpc.Call):
            return cls(grpc.StatusCode.UNKNOWN, str(error))
        code = error.code()
        message = error.details() or ""
        status = rpc_status.from_call(error)
        if status is None:
            return cls(code, message)
        for detail in status.details:
            if detail.Is(error_details_pb2.ErrorInfo.DESCRIPTOR):
                info = error_details_pb2.ErrorInfo()
                detail.Unpack(info)
                if info.domain != ERROR_DOMAIN:
                    continue
                try:
                    reason = Reason(info.reason)
                except ValueError:
                    reason = None
                return cls(code, message, reason, dict(info.metadata))
        return cls(code, message)

