"""Claves de etcd del modelo de metadatos (ADR 0041). Todas cuelgan de un prefijo, ``/dfsha/`` en producción."""

ROOT_DIRECTORY_ID = "root"


class Keys:
    def __init__(self, prefix: bytes = b"/dfsha/") -> None:
        if not prefix.endswith(b"/"):
            raise ValueError("El prefijo de las claves termina en /")
        self.prefix = prefix

    def _key(self, *parts: str) -> bytes:
        return self.prefix + "/".join(parts).encode()

    @property
    def leader(self) -> bytes:
        return self.prefix + b"leader"

    def entry(self, user_id: str, directory_id: str, name: str) -> bytes:
        return self._key("entries", user_id, directory_id, name)

    def entries_prefix(self, user_id: str, directory_id: str) -> bytes:
        return self._key("entries", user_id, directory_id) + b"/"

    def file(self, file_id: str) -> bytes:
        return self._key("files", file_id)

    def version(self, file_id: str, version: int) -> bytes:
        return self._key("versions", file_id, f"{version:020d}")

    def all_versions_prefix(self) -> bytes:
        return self._key("versions") + b"/"

    def replicas_prefix(self, block_id: str) -> bytes:
        return self._key("replicas", block_id) + b"/"

    def replica(self, block_id: str, node_id: str) -> bytes:
        return self._key("replicas", block_id, node_id)

    def pending_prefix(self, lease_id: str) -> bytes:
        return self._key("pending", lease_id) + b"/"

    def all_pending_prefix(self) -> bytes:
        return self._key("pending") + b"/"

    def pending(self, lease_id: str, request_id: str) -> bytes:
        return self._key("pending", lease_id, request_id)

    def leases_prefix(self, file_id: str) -> bytes:
        return self._key("leases", file_id) + b"/"

    def all_leases_prefix(self) -> bytes:
        return self._key("leases") + b"/"

    def lease(self, file_id: str, lease_id: str) -> bytes:
        return self._key("leases", file_id, lease_id)

    def lease_guard(self, file_id: str) -> bytes:
        return self._key("lease-guards", file_id)

    def request(self, user_id: str, request_id: str) -> bytes:
        return self._key("requests", user_id, request_id)

    def user(self, user_id: str) -> bytes:
        return self._key("users", user_id)

    def username(self, username: str) -> bytes:
        return self._key("usernames", username)

    def node(self, node_id: str) -> bytes:
        return self._key("nodes", node_id)

    @property
    def nodes_prefix(self) -> bytes:
        return self.prefix + b"nodes/"
