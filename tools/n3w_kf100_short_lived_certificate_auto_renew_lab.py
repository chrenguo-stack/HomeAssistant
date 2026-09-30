#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import shutil
import socket
import ssl
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Sequence

SCHEMA = "gh.n3w-kf100-short-lived-renewal-lab/1"

PRODUCTION_LIFECYCLE_TOOL = Path("/usr/local/sbin/n3w-broker-certificate-lifecycle")
PRODUCTION_LIFECYCLE_TOOL_BLOB = "65187b27a2ddd8f57221500a7019486e02bca101"
PRODUCTION_STATUS_FILE = Path("/var/lib/n3wfc4-certificate-lifecycle/status.json")
PRODUCTION_TIMER = "n3wfc4-broker-certificate-lifecycle.timer"
PRODUCTION_SERVICE = "n3wfc4-broker-certificate-lifecycle.service"
EXPECTED_ACTIVATION_UNIT = "n3wfc4-broker-activation.service"
EXPECTED_PROJECT = "n3wfc4"
EXPECTED_SERVICE = "broker"
EXPECTED_SERVER_NAME = "armbian"
LAB_SERVER_NAME = "kf100-renew-lab"
LAB_INTERNAL_PORT = 8883

EXPECTED_PRODUCTION_SERVER_CERT_SHA256 = (
    "299a4cbece174692ecc9d82b92f1a98699847fece79543c8f8e565c04a07e917"
)
EXPECTED_PRODUCTION_CA_CERT_SHA256 = (
    "11ff133cdab8bf5f3093f6b488f8fa7e2579a1b5e383d066b1a1da56ad5dae9f"
)
EXPECTED_PRODUCTION_SERVER_FINGERPRINT = (
    "8272aa061d70bf0b5ed41a94a1b6fdc5065bd6b51f6751aa7b7a2059803d74cb"
)


class LabError(RuntimeError):
    def __init__(self, code: str, details: dict[str, object] | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.details = details or {}


def _progress(stage: str, **fields: object) -> None:
    print(
        "KF100_RENEWAL_LAB "
        + json.dumps({"stage": stage, **fields}, sort_keys=True, separators=(",", ":")),
        file=sys.stderr,
        flush=True,
    )


def _run(
    argv: Sequence[str],
    *,
    timeout: int = 60,
    env: dict[str, str] | None = None,
    allow_failure: bool = False,
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            list(argv),
            check=False,
            text=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise LabError("command_unavailable") from error
    if result.returncode != 0 and not allow_failure:
        raise LabError("command_failed")
    return result


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def _git_blob_sha1(path: Path) -> str:
    payload = path.read_bytes()
    return hashlib.sha1(
        f"blob {len(payload)}\0".encode("ascii") + payload
    ).hexdigest()


def _certificate_fingerprint(path: Path) -> str:
    result = _run(
        ("openssl", "x509", "-in", str(path), "-noout", "-fingerprint", "-sha256")
    )
    match = re.search(r"Fingerprint=([0-9A-Fa-f:]+)", result.stdout)
    if match is None:
        raise LabError("certificate_fingerprint_missing")
    value = match.group(1).replace(":", "").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise LabError("certificate_fingerprint_invalid")
    return value


def _certificate_not_after(path: Path) -> str:
    result = _run(("openssl", "x509", "-in", str(path), "-noout", "-enddate"))
    value = result.stdout.strip()
    if not value.startswith("notAfter="):
        raise LabError("certificate_not_after_missing")
    return value.removeprefix("notAfter=")


def _live_tls_fingerprint(
    host: str,
    port: int,
    server_name: str,
    ca_file: Path,
) -> str:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED
    context.load_verify_locations(cafile=str(ca_file))
    try:
        with socket.create_connection((host, port), timeout=10) as raw:
            with context.wrap_socket(raw, server_hostname=server_name) as wrapped:
                der = wrapped.getpeercert(binary_form=True)
    except (OSError, ssl.SSLError) as error:
        raise LabError("tls_probe_failed") from error
    if not der:
        raise LabError("tls_peer_certificate_missing")
    return hashlib.sha256(der).hexdigest()


def _docker_json(container: str) -> dict[str, object]:
    result = _run(("docker", "inspect", container))
    try:
        document = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise LabError("docker_inspect_invalid") from error
    if not isinstance(document, list) or len(document) != 1:
        raise LabError("docker_inspect_invalid")
    item = document[0]
    if not isinstance(item, dict):
        raise LabError("docker_inspect_invalid")
    return item


def _production_broker() -> str:
    result = _run(
        (
            "docker",
            "ps",
            "--filter",
            f"label=com.docker.compose.project={EXPECTED_PROJECT}",
            "--filter",
            f"label=com.docker.compose.service={EXPECTED_SERVICE}",
            "--format",
            "{{.ID}}",
        )
    )
    values = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if len(values) != 1:
        raise LabError("production_broker_not_unique")
    return values[0]


def _mount_source(inspect: dict[str, object], target: str) -> Path:
    mounts = inspect.get("Mounts")
    if not isinstance(mounts, list):
        raise LabError("production_mounts_invalid")
    matches: list[Path] = []
    for mount in mounts:
        if not isinstance(mount, dict):
            continue
        if mount.get("Destination") != target:
            continue
        if mount.get("Type") != "bind":
            raise LabError("production_tls_mount_not_bind")
        source = mount.get("Source")
        if not isinstance(source, str) or not source.startswith("/"):
            raise LabError("production_tls_mount_invalid")
        matches.append(Path(source))
    if len(matches) != 1:
        raise LabError("production_tls_mount_not_unique")
    path = matches[0]
    if not path.is_file() or path.is_symlink():
        raise LabError("production_tls_source_invalid")
    return path


def _systemctl_state(mode: str, unit: str) -> str:
    result = _run(("systemctl", mode, unit), timeout=10, allow_failure=True)
    return result.stdout.strip() or "unknown"


def _production_snapshot() -> dict[str, object]:
    if not PRODUCTION_LIFECYCLE_TOOL.is_file():
        raise LabError("production_lifecycle_tool_missing")
    if _git_blob_sha1(PRODUCTION_LIFECYCLE_TOOL) != PRODUCTION_LIFECYCLE_TOOL_BLOB:
        raise LabError("production_lifecycle_tool_blob_mismatch")

    container = _production_broker()
    inspect = _docker_json(container)
    state = inspect.get("State")
    config = inspect.get("Config")
    if not isinstance(state, dict) or state.get("Running") is not True:
        raise LabError("production_broker_not_running")
    if not isinstance(config, dict):
        raise LabError("production_broker_config_invalid")

    started = state.get("StartedAt")
    image = config.get("Image")
    if not isinstance(started, str) or not started:
        raise LabError("production_broker_started_at_missing")
    if not isinstance(image, str) or not image:
        raise LabError("production_broker_image_missing")

    server_cert = _mount_source(inspect, "/mosquitto/tls/server.pem")
    server_key = _mount_source(inspect, "/mosquitto/tls/server.key")
    ca_cert = _mount_source(inspect, "/mosquitto/tls/ca.pem")

    server_cert_sha256 = _sha256(server_cert)
    ca_cert_sha256 = _sha256(ca_cert)
    if server_cert_sha256 != EXPECTED_PRODUCTION_SERVER_CERT_SHA256:
        raise LabError("production_server_certificate_drift")
    if ca_cert_sha256 != EXPECTED_PRODUCTION_CA_CERT_SHA256:
        raise LabError("production_ca_certificate_drift")
    if _live_tls_fingerprint(
        "127.0.0.1",
        8883,
        EXPECTED_SERVER_NAME,
        ca_cert,
    ) != EXPECTED_PRODUCTION_SERVER_FINGERPRINT:
        raise LabError("production_live_tls_drift")

    if not PRODUCTION_STATUS_FILE.is_file() or PRODUCTION_STATUS_FILE.is_symlink():
        raise LabError("production_status_invalid")

    key_stat = server_key.stat()

    return {
        "container": container,
        "started": started,
        "image": image,
        "server_cert": server_cert,
        "server_key": server_key,
        "ca_cert": ca_cert,
        "server_cert_sha256": server_cert_sha256,
        "server_key_sha256": _sha256(server_key),
        "ca_cert_sha256": ca_cert_sha256,
        "status_sha256": _sha256(PRODUCTION_STATUS_FILE),
        "timer_active": _systemctl_state("is-active", PRODUCTION_TIMER),
        "timer_enabled": _systemctl_state("is-enabled", PRODUCTION_TIMER),
        "service_active": _systemctl_state("is-active", PRODUCTION_SERVICE),
        "broker_uid": key_stat.st_uid,
        "broker_gid": key_stat.st_gid,
    }


def _assert_production_unchanged(before: dict[str, object]) -> None:
    after = _production_snapshot()
    exact_keys = (
        "container",
        "started",
        "server_cert_sha256",
        "server_key_sha256",
        "ca_cert_sha256",
        "status_sha256",
        "timer_active",
        "timer_enabled",
    )
    for key in exact_keys:
        if after[key] != before[key]:
            raise LabError(f"production_drift_{key}")
    if after["service_active"] in {"active", "activating"}:
        raise LabError("production_lifecycle_service_active")


def _write(path: Path, value: str, mode: int) -> None:
    path.write_text(value, encoding="utf-8")
    os.chmod(path, mode)


def _prepare_pki(case_root: Path, uid: int, gid: int) -> dict[str, Path]:
    tls = case_root / "tls"
    status = case_root / "status"
    bin_dir = case_root / "bin"
    for directory in (tls, status, bin_dir):
        directory.mkdir(parents=True, exist_ok=False)
    os.chmod(case_root, 0o700)
    os.chmod(tls, 0o700)
    os.chmod(status, 0o700)
    os.chmod(bin_dir, 0o700)

    ca_key = tls / "ca.key"
    ca_cert = tls / "ca.pem"
    server_key = tls / "server.key"
    server_csr = tls / "server.csr"
    server_cert = tls / "server.pem"
    decoy_cert = tls / "decoy.pem"
    ca_config = tls / "ca.cnf"
    server_config = tls / "server.cnf"

    _write(
        ca_config,
        "\n".join(
            (
                "[req]",
                "prompt=no",
                "distinguished_name=dn",
                "x509_extensions=ca_ext",
                "[dn]",
                "O=Greenhouse KF100 Renewal Lab",
                "CN=Greenhouse KF100 Renewal Lab CA",
                "[ca_ext]",
                "basicConstraints=critical,CA:TRUE,pathlen:0",
                "keyUsage=critical,keyCertSign,cRLSign",
                "subjectKeyIdentifier=hash",
                "",
            )
        ),
        0o600,
    )
    _write(
        server_config,
        "\n".join(
            (
                "[req]",
                "prompt=no",
                "distinguished_name=dn",
                "req_extensions=req_ext",
                "[dn]",
                "O=Greenhouse KF100 Renewal Lab",
                f"CN={LAB_SERVER_NAME}",
                "[req_ext]",
                f"subjectAltName=DNS:{LAB_SERVER_NAME}",
                "[server_ext]",
                "basicConstraints=critical,CA:FALSE",
                "extendedKeyUsage=serverAuth",
                f"subjectAltName=DNS:{LAB_SERVER_NAME}",
                "subjectKeyIdentifier=hash",
                "authorityKeyIdentifier=keyid,issuer",
                "",
            )
        ),
        0o600,
    )

    _run(
        (
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-keyout",
            str(ca_key),
            "-out",
            str(ca_cert),
            "-days",
            "3650",
            "-sha256",
            "-config",
            str(ca_config),
        )
    )
    _run(
        (
            "openssl",
            "genpkey",
            "-algorithm",
            "RSA",
            "-pkeyopt",
            "rsa_keygen_bits:2048",
            "-out",
            str(server_key),
        )
    )
    _run(
        (
            "openssl",
            "req",
            "-new",
            "-key",
            str(server_key),
            "-config",
            str(server_config),
            "-out",
            str(server_csr),
        )
    )

    def sign(output: Path, days: int) -> None:
        serial = secrets.randbits(159) | 1
        _run(
            (
                "openssl",
                "x509",
                "-req",
                "-in",
                str(server_csr),
                "-CA",
                str(ca_cert),
                "-CAkey",
                str(ca_key),
                "-set_serial",
                f"0x{serial:x}",
                "-days",
                str(days),
                "-sha256",
                "-extfile",
                str(server_config),
                "-extensions",
                "server_ext",
                "-out",
                str(output),
            )
        )

    sign(server_cert, 1)
    sign(decoy_cert, 2)

    os.chmod(ca_key, 0o600)
    os.chmod(server_key, 0o600)
    os.chmod(server_cert, 0o644)
    os.chmod(decoy_cert, 0o644)
    os.chmod(ca_cert, 0o644)

    os.chown(server_key, uid, gid)
    os.chown(server_cert, uid, gid)
    os.chown(decoy_cert, uid, gid)
    os.chown(ca_cert, uid, gid)

    return {
        "tls": tls,
        "status": status,
        "bin": bin_dir,
        "ca_key": ca_key,
        "ca_cert": ca_cert,
        "server_key": server_key,
        "server_cert": server_cert,
        "decoy_cert": decoy_cert,
    }


def _write_mosquitto_config(case_root: Path, uid: int, gid: int) -> Path:
    config = case_root / "mosquitto.conf"
    _write(
        config,
        "\n".join(
            (
                "persistence false",
                "log_dest stdout",
                f"listener {LAB_INTERNAL_PORT}",
                "allow_anonymous true",
                "cafile /mosquitto/tls/ca.pem",
                "certfile /mosquitto/tls/server.pem",
                "keyfile /mosquitto/tls/server.key",
                "tls_version tlsv1.2",
                "",
            )
        ),
        0o644,
    )
    os.chown(config, uid, gid)
    return config


def _mosquitto_binary(production_container: str) -> str:
    result = _run(
        (
            "docker",
            "exec",
            production_container,
            "sh",
            "-c",
            "command -v mosquitto",
        )
    )
    value = result.stdout.strip()
    if not value.startswith("/"):
        raise LabError("mosquitto_binary_unresolved")
    return value


def _allocate_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        port = int(probe.getsockname()[1])
    if not 1 <= port <= 65535:
        raise LabError("lab_host_port_invalid")
    return port


def _container_run_args(
    name: str,
    image: str,
    mosquitto_binary: str,
    config: Path,
    pki: dict[str, Path],
    port: int,
) -> list[str]:
    return [
        "docker",
        "run",
        "-d",
        "--name",
        name,
        "--label",
        "gh.n3w.kf100-renewal-lab=true",
        "-p",
        f"127.0.0.1:{port}:{LAB_INTERNAL_PORT}",
        "-v",
        f"{config}:/mosquitto/config/mosquitto.conf:ro",
        "-v",
        f"{pki['ca_cert']}:/mosquitto/tls/ca.pem:ro",
        "-v",
        f"{pki['server_cert']}:/mosquitto/tls/server.pem:ro",
        "-v",
        f"{pki['server_key']}:/mosquitto/tls/server.key:ro",
        "--entrypoint",
        mosquitto_binary,
        image,
        "-c",
        "/mosquitto/config/mosquitto.conf",
    ]


def _start_lab_container(run_args: Sequence[str]) -> None:
    _run(tuple(run_args), timeout=60)


def _wait_lab_tls(port: int, ca_cert: Path, expected_fingerprint: str) -> None:
    deadline = time.monotonic() + 30
    last: Exception | None = None
    while time.monotonic() < deadline:
        try:
            observed = _live_tls_fingerprint(
                "127.0.0.1",
                port,
                LAB_SERVER_NAME,
                ca_cert,
            )
            if observed == expected_fingerprint:
                return
            last = LabError("lab_tls_fingerprint_unexpected")
        except Exception as error:
            last = error
        time.sleep(0.5)
    raise LabError("lab_tls_not_ready") from last


def _write_systemctl_shim(
    pki: dict[str, Path],
    container: str,
    port: int,
    mode: str,
    run_args: Sequence[str],
) -> Path:
    shim = pki["bin"] / "systemctl"
    restart_counter = pki["tls"] / "restart.count"
    code = f"""#!/usr/bin/env python3
import hashlib
import shutil
import socket
import ssl
import subprocess
import sys
import time
from pathlib import Path

UNIT = {EXPECTED_ACTIVATION_UNIT!r}
CONTAINER = {container!r}
PORT = {port!r}
MODE = {mode!r}
ACTIVE_CERT = Path({str(pki["server_cert"])!r})
DECOY_CERT = Path({str(pki["decoy_cert"])!r})
COUNTER = Path({str(restart_counter)!r})
RUN_ARGS = {list(run_args)!r}
SERVER_NAME = {LAB_SERVER_NAME!r}


def running():
    result = subprocess.run(
        ["docker", "inspect", "-f", "{{{{.State.Running}}}}", CONTAINER],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"


def file_fingerprint():
    result = subprocess.run(
        ["openssl", "x509", "-in", str(ACTIVE_CERT), "-outform", "DER"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    if result.returncode != 0 or not result.stdout:
        return None
    return hashlib.sha256(result.stdout).hexdigest()


def live_fingerprint():
    context = ssl._create_unverified_context()
    try:
        with socket.create_connection(("127.0.0.1", PORT), timeout=1) as raw:
            with context.wrap_socket(raw, server_hostname=SERVER_NAME) as wrapped:
                der = wrapped.getpeercert(binary_form=True)
    except (OSError, ssl.SSLError):
        return None
    if not der:
        return None
    return hashlib.sha256(der).hexdigest()


def wait_tls_matches_file():
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        expected = file_fingerprint()
        observed = live_fingerprint()
        if expected is not None and observed == expected:
            return True
        time.sleep(0.25)
    return False


args = sys.argv[1:]
if args == ["is-active", "--quiet", UNIT]:
    raise SystemExit(0 if running() else 3)

if args == ["restart", UNIT]:
    count = 1
    if COUNTER.exists():
        count = int(COUNTER.read_text(encoding="utf-8").strip()) + 1
    COUNTER.write_text(str(count), encoding="utf-8")

    if MODE == "force_mismatch" and count == 1:
        shutil.copyfile(DECOY_CERT, ACTIVE_CERT)

    subprocess.run(
        ["docker", "rm", "-f", CONTAINER],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    result = subprocess.run(
        RUN_ARGS,
        check=False,
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if result.returncode != 0 or not wait_tls_matches_file():
        raise SystemExit(1)
    raise SystemExit(0)

raise SystemExit(64)
"""
    _write(shim, code, 0o755)
    return shim

def _parse_lifecycle_output(result: subprocess.CompletedProcess[str]) -> dict[str, object]:
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not lines:
        raise LabError("lifecycle_output_missing")
    try:
        document = json.loads(lines[-1])
    except json.JSONDecodeError as error:
        raise LabError("lifecycle_output_invalid") from error
    if not isinstance(document, dict):
        raise LabError("lifecycle_output_invalid")
    return document


def _run_case(
    lab_root: Path,
    case_name: str,
    mode: str,
    production: dict[str, object],
    mosquitto_binary: str,
) -> dict[str, object]:
    case_root = lab_root / case_name
    case_root.mkdir(mode=0o700)
    uid = int(production["broker_uid"])
    gid = int(production["broker_gid"])
    pki = _prepare_pki(case_root, uid, gid)
    config = _write_mosquitto_config(case_root, uid, gid)

    initial_fingerprint = _certificate_fingerprint(pki["server_cert"])
    initial_not_after = _certificate_not_after(pki["server_cert"])
    initial_key_sha256 = _sha256(pki["server_key"])
    initial_ca_sha256 = _sha256(pki["ca_cert"])

    container = f"n3w-kf100-renew-lab-{case_name}-{os.getpid()}"
    port = _allocate_loopback_port()
    run_args = _container_run_args(
        container,
        str(production["image"]),
        mosquitto_binary,
        config,
        pki,
        port,
    )
    try:
        _start_lab_container(run_args)
        _wait_lab_tls(port, pki["ca_cert"], initial_fingerprint)
        _write_systemctl_shim(pki, container, port, mode, run_args)

        status_file = pki["status"] / "status.json"
        env = dict(os.environ)
        env["PATH"] = str(pki["bin"]) + os.pathsep + env.get("PATH", "")
        result = _run(
            (
                str(PRODUCTION_LIFECYCLE_TOOL),
                "auto-renew",
                "--server-cert",
                str(pki["server_cert"]),
                "--server-key",
                str(pki["server_key"]),
                "--ca-cert",
                str(pki["ca_cert"]),
                "--ca-key",
                str(pki["ca_key"]),
                "--server-name",
                LAB_SERVER_NAME,
                "--status-file",
                str(status_file),
                "--allowed-root",
                str(case_root),
                "--activation-unit",
                EXPECTED_ACTIVATION_UNIT,
                "--probe-host",
                "127.0.0.1",
                "--probe-port",
                str(port),
            ),
            timeout=240,
            env=env,
            allow_failure=True,
        )
        document = _parse_lifecycle_output(result)
        diagnostic = {
            "lifecycle_rc": result.returncode,
            "lifecycle_result": document.get("result"),
            "renewal_attempted": document.get("renewal_attempted"),
            "rollback_attempted": document.get("rollback_attempted"),
        }

        final_fingerprint = _certificate_fingerprint(pki["server_cert"])
        final_not_after = _certificate_not_after(pki["server_cert"])
        key_unchanged = _sha256(pki["server_key"]) == initial_key_sha256
        ca_unchanged = _sha256(pki["ca_cert"]) == initial_ca_sha256

        if mode == "success":
            expected = {
                "result": "renewed",
                "action": "renew_server_certificate",
                "renewal_attempted": True,
                "rollback_attempted": False,
                "server_state": "HEALTHY",
            }
            if result.returncode != 0:
                raise LabError("success_case_lifecycle_rc", diagnostic)
            for key, value in expected.items():
                if document.get(key) != value:
                    raise LabError(f"success_case_{key}_unexpected", diagnostic)
            _wait_lab_tls(port, pki["ca_cert"], final_fingerprint)
            if final_fingerprint == initial_fingerprint:
                raise LabError("success_case_certificate_not_replaced", diagnostic)
            if final_not_after == initial_not_after:
                raise LabError("success_case_validity_not_extended", diagnostic)
            if not key_unchanged or not ca_unchanged:
                raise LabError("success_case_key_or_ca_changed", diagnostic)
            return {
                "result": "PASS",
                "lifecycle_result": document.get("result"),
                "initial_server_state": "CRITICAL",
                "renewal_attempted": True,
                "rollback_attempted": False,
                "certificate_replaced": True,
                "certificate_fingerprint_changed": True,
                "server_key_unchanged": True,
                "ca_certificate_unchanged": True,
                "live_tls_uses_new_certificate": True,
                "activation_recreate_count": 1,
                "initial_not_after": initial_not_after,
                "renewed_not_after": final_not_after,
            }

        if mode == "force_mismatch":
            expected = {
                "result": "renewal_failed_rolled_back",
                "action": "renew_server_certificate",
                "renewal_attempted": True,
                "rollback_attempted": True,
            }
            if result.returncode != 2:
                raise LabError("rollback_case_lifecycle_rc", diagnostic)
            for key, value in expected.items():
                if document.get(key) != value:
                    raise LabError(f"rollback_case_{key}_unexpected", diagnostic)
            _wait_lab_tls(port, pki["ca_cert"], initial_fingerprint)
            if final_fingerprint != initial_fingerprint:
                raise LabError("rollback_case_original_certificate_not_restored", diagnostic)
            if not key_unchanged or not ca_unchanged:
                raise LabError("rollback_case_key_or_ca_changed", diagnostic)
            return {
                "result": "PASS",
                "lifecycle_result": document.get("result"),
                "initial_server_state": "CRITICAL",
                "renewal_attempted": True,
                "rollback_attempted": True,
                "forced_postrenew_mismatch": True,
                "original_certificate_restored": True,
                "server_key_unchanged": True,
                "ca_certificate_unchanged": True,
                "live_tls_restored_to_original_certificate": True,
                "activation_recreate_count": 2,
                "initial_not_after": initial_not_after,
                "restored_not_after": final_not_after,
            }

        raise LabError("case_mode_invalid", diagnostic)
    finally:
        _run(("docker", "rm", "-f", container), timeout=30, allow_failure=True)

def main() -> int:
    if os.geteuid() != 0:
        print(json.dumps({"schema": SCHEMA, "result": "STOP", "reason": "root_required"}))
        return 2

    lab_root: Path | None = None
    production: dict[str, object] | None = None
    try:
        _progress("production_preflight")
        production = _production_snapshot()
        if production["timer_enabled"] != "enabled" or production["timer_active"] != "active":
            raise LabError("production_timer_not_healthy")
        if production["service_active"] in {"active", "activating"}:
            raise LabError("production_lifecycle_service_busy")

        _progress("prepare_isolated_lab")
        lab_root = Path(
            tempfile.mkdtemp(prefix="n3w-kf100-renewal-lab.", dir="/var/tmp")
        )
        os.chmod(lab_root, 0o700)
        mosquitto_binary = _mosquitto_binary(str(production["container"]))

        _progress("success_path")
        success = _run_case(
            lab_root,
            "success",
            "success",
            production,
            mosquitto_binary,
        )

        _progress("rollback_path")
        rollback = _run_case(
            lab_root,
            "rollback",
            "force_mismatch",
            production,
            mosquitto_binary,
        )

        _progress("production_postcheck")
        _assert_production_unchanged(production)

        document = {
            "schema": SCHEMA,
            "result": "PASS",
            "isolated_lab": True,
            "production_certificate_mutation": False,
            "production_broker_restart": False,
            "production_status_unchanged": True,
            "production_timer_preserved": True,
            "success_path": success,
            "rollback_path": rollback,
            "lab_cleanup": True,
        }
        _progress("complete", result="PASS")
        print(json.dumps(document, sort_keys=True, separators=(",", ":")))
        return 0
    except LabError as error:
        if production is not None:
            try:
                _assert_production_unchanged(production)
                production_preserved: bool | str = True
            except Exception:
                production_preserved = "UNPROVEN"
        else:
            production_preserved = "UNPROVEN"
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "result": "STOP",
                    "reason": error.code,
                    "diagnostic": error.details,
                    "production_preserved": production_preserved,
                    "production_certificate_mutation": False,
                    "production_broker_restart": False,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 2
    finally:
        if lab_root is not None:
            shutil.rmtree(lab_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
