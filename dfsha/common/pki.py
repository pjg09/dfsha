"""CA interna, certificados por host y secretos del clúster (fase I §10.4 y §10.7; ADR 0023 y 0043).

Uso: python -m dfsha.common.pki <directorio> <host> [<host> ...]

Crea en el directorio, que nunca se versiona:
- ``ca/``: la CA interna (``ca.pem`` y ``ca.key``). La clave de la CA es el secreto más sensible.
- ``<host>/``: lo que se monta en el contenedor de ese host: ``ca.pem``, ``cert.pem`` y ``key.pem`` (también
  el cliente: TLS mutuo en todas las conexiones, ADR 0043) y, según el rol, las claves compartidas. El rol
  sale del nombre ``<rol>-<n>`` (convenciones §4).
- ``admin-password``: la contraseña del primer administrador.
Si el directorio ya tiene una CA y claves, las reutiliza y solo emite los certificados que faltan.
"""

import datetime
import ipaddress
import secrets
import sys
from collections.abc import Iterable
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from dfsha.common.security import generate_key

CERTIFICATE_VALIDITY_DAYS = 365
ACCESS_TOKEN_KEY_FILE = "access-token.key"
BLOCK_TOKEN_KEY_FILE = "block-token.key"
WRAPPING_KEY_FILE = "wrapping.key"
ADMIN_PASSWORD_FILE = "admin-password"

# Qué claves compartidas recibe cada rol (§10.7)
_KEYS_BY_ROLE = {
    "metadata": (ACCESS_TOKEN_KEY_FILE, BLOCK_TOKEN_KEY_FILE, WRAPPING_KEY_FILE, ADMIN_PASSWORD_FILE),
    "datanode": (BLOCK_TOKEN_KEY_FILE,),
    "client": (),
}


def get_role(host: str) -> str:
    role, _, number = host.rpartition("-")
    if role not in _KEYS_BY_ROLE or not number.isdigit():
        raise ValueError(f"{host!r} no sigue el patrón <rol>-<n> con un rol de {sorted(_KEYS_BY_ROLE)}")
    return role


def _write_private(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(mode=0o600, exist_ok=True)
    path.chmod(0o600)
    path.write_bytes(data)


def _new_key() -> ec.EllipticCurvePrivateKey:
    return ec.generate_private_key(ec.SECP256R1())


def _key_pem(key: ec.EllipticCurvePrivateKey) -> bytes:
    return key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())


def _load_or_create_ca(directory: Path) -> tuple[x509.Certificate, ec.EllipticCurvePrivateKey]:
    cert_path, key_path = directory / "ca" / "ca.pem", directory / "ca" / "ca.key"
    if cert_path.exists() and key_path.exists():
        key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
        assert isinstance(key, ec.EllipticCurvePrivateKey)
        return x509.load_pem_x509_certificate(cert_path.read_bytes()), key
    key = _new_key()
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "DFSha CA interna")])
    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(days=CERTIFICATE_VALIDITY_DAYS))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(x509.KeyUsage(False, False, False, False, False, True, True, False, False), critical=True)
        .sign(key, hashes.SHA256())
    )
    _write_private(key_path, _key_pem(key))
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return cert, key


def issue_certificate(
    ca_cert: x509.Certificate, ca_key: ec.EllipticCurvePrivateKey, host: str, extra_names: Iterable[str] = ()
) -> tuple[bytes, bytes]:
    """Certificado de un host con ``<rol>-<n>`` en el SAN, válido como servidor y como cliente (TLS mutuo)."""
    key = _new_key()
    now = datetime.datetime.now(datetime.UTC)
    names: list[x509.GeneralName] = [x509.DNSName(host)]
    for name in extra_names:
        try:
            names.append(x509.IPAddress(ipaddress.ip_address(name)))
        except ValueError:
            names.append(x509.DNSName(name))
    cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, host)]))
        .issuer_name(ca_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(days=CERTIFICATE_VALIDITY_DAYS))
        .add_extension(x509.SubjectAlternativeName(names), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH, ExtendedKeyUsageOID.CLIENT_AUTH]), critical=False)
        .sign(ca_key, hashes.SHA256())
    )
    return cert.public_bytes(serialization.Encoding.PEM), _key_pem(key)


def _load_or_create_shared(directory: Path) -> dict[str, bytes]:
    shared: dict[str, bytes] = {}
    for name in (ACCESS_TOKEN_KEY_FILE, BLOCK_TOKEN_KEY_FILE, WRAPPING_KEY_FILE, ADMIN_PASSWORD_FILE):
        path = directory / "ca" / name
        if not path.exists():
            value = secrets.token_urlsafe(24).encode() if name == ADMIN_PASSWORD_FILE else generate_key()
            _write_private(path, value)
        shared[name] = path.read_bytes()
    return shared


def create_cluster_secrets(directory: Path, hosts: Iterable[str], extra_names: Iterable[str] = ()) -> None:
    """Crea o completa los secretos del clúster para los hosts indicados."""
    directory.mkdir(parents=True, exist_ok=True)
    ca_cert, ca_key = _load_or_create_ca(directory)
    shared = _load_or_create_shared(directory)
    ca_pem = ca_cert.public_bytes(serialization.Encoding.PEM)
    extra = list(extra_names)
    for host in hosts:
        role = get_role(host)
        host_directory = directory / host
        host_directory.mkdir(exist_ok=True)
        host_directory.chmod(0o755)
        (host_directory / "ca.pem").write_bytes(ca_pem)
        if not (host_directory / "cert.pem").exists():
            cert_pem, key_pem = issue_certificate(ca_cert, ca_key, host, extra)
            (host_directory / "cert.pem").write_bytes(cert_pem)
            _write_private(host_directory / "key.pem", key_pem)
        for name in _KEYS_BY_ROLE[role]:
            _write_private(host_directory / name, shared[name])
    _write_private(directory / ADMIN_PASSWORD_FILE, shared[ADMIN_PASSWORD_FILE])


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if len(arguments) < 2:
        print("Uso: python -m dfsha.common.pki <directorio> <host> [<host> ...]", file=sys.stderr)
        return 2
    directory, hosts = Path(arguments[0]), arguments[1:]
    create_cluster_secrets(directory, hosts)
    print(f"Secretos de {len(hosts)} hosts en {directory}. No los versiones (CONTRIBUTING.md §8).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
