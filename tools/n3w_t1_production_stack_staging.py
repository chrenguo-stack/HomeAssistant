#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import stat
import subprocess
from pathlib import Path
from typing import Any, Sequence

AUTHORIZATION_ID = "N3W_T1_PRODUCTION_STACK_STAGING_LIVE_APPLY_20261011_01"
SCHEMA = "gh.n3w-t1-production-stack-staging/1"
EXPECTED_ARCH = "aarch64"
EXPECTED_VOLUME_COUNT = 45
EXPECTED_VOLUME_SET_SHA256 = (
    "20fc845741d31da34f1d1e563e5057c78ec5dc7c4cfd3a495a5f3a4f2bfd011b"
)
EXPECTED_DYNSEC_SHA256 = (
    "95d99839ec9a6b8003e1375883a3f9263a92e0dbc49c8ca5478196027081a90a"
)
EXPECTED_SYSTEM_ID_SHA256 = (
    "f300f10844ecfc75f12a0deb789ce9ddb41209c38307e65436e81d43ad4658d9"
)
EXPECTED_MANAGER_IMAGE = "local/greenhouse-manager:s20-511db028"
EXPECTED_MANAGER_IMAGE_ID = (
    "sha256:ef0f28c2fd339430a85acb6cb65158c71c61cd8fc3c6330c375da27d0f2440f1"
)
EXPECTED_MANAGER_TAR_SHA256 = (
    "2ef0421d483334f6ef81c92beb1b6784174f069a4bde179ba615ce0b70435081"
)
EXPECTED_HA_IMAGE = (
    "ghcr.io/home-assistant/home-assistant:2026.10.0@"
    "sha256:0c73235a9140a9b02e4bf618d06d8c496b12ae70656ecddb0e02ad31ad122be4"
)
EXPECTED_HA_IMAGE_ID = (
    "sha256:b0e1ee82adfb19fa1ff3049034535633b1c4f0df6606721c0e77383854b99879"
)
EXPECTED_BROKER_IMAGE = (
    "m.daocloud.io/docker.io/library/eclipse-mosquitto:2.1.2-alpine@"
    "sha256:3184566df484a083411a0e70e92c87a264b8f0648df632f10eb23d54d99f4549"
)
EXPECTED_BROKER_IMAGE_ID = (
    "sha256:4c199d7c9d377d018313a2199f6839978f6fd2219c405ad664d0a830c14b9c7b"
)
MIN_ROOT_AVAILABLE_BYTES = 5 * 1024 * 1024 * 1024

PORTS_TCP = (1883, 8883, 18883, 8123, 47112)
PORTS_UDP = (47111,)
NETWORKS = ("n3wfc4-private", "n3wfc4-services")
ACTIVATION_UNITS = (
    "n3wfc4-broker-activation.service",
    "n3wfc4-services-activation.service",
)
DISPATCHER = Path("/etc/NetworkManager/dispatcher.d/90-n3wfc4-broker-ingress-guard")

MANAGER_ROOT = Path("/var/lib/greenhouse-manager")
MANAGER_DIR = MANAGER_ROOT / "manager"
MANAGER_DB = MANAGER_DIR / "manager-state.sqlite3"
LEGACY_COLLISION = MANAGER_DIR / "registration.sqlite3"
N3W_ROOT = MANAGER_ROOT / "n3w"
HA_ROOT = Path("/var/lib/n3wfc4-homeassistant")
SYSTEM_IDENTITY = MANAGER_ROOT / "system-identity.json"
DYNSEC_PATH = Path("/var/lib/n3wfc4-broker/dynamic-security.json")
SECRET_ROOT = Path("/opt/greenhouse-secrets/mqtt")
TRANSACTION_DIR = Path("/etc/n3wfc4/private/.s20-three-service-transaction")
OPT_ROOT = Path("/opt/HomeAssistant")

EXPECTED_MANAGER_TABLES = frozenset(
    {
        "credential_assignments",
        "h0h1_legacy_adoption_provenance",
        "node_id_leases",
        "pairing_sessions",
        "registration_events",
        "registration_node_history",
        "registrations",
        "retirement_outbox",
    }
)
BUSINESS_TABLES = (
    "credential_assignments",
    "node_id_leases",
    "pairing_sessions",
    "registration_events",
    "registration_node_history",
    "registrations",
    "retirement_outbox",
)

SOURCE_FILES: dict[str, tuple[str, int, str]] = {
    "infra/n3w-t1/production/docker-compose.yml": (
        "/opt/HomeAssistant/infra/n3w-t1/production/docker-compose.yml",
        0o644,
        "45ebfa800512cf54124a489a183eb59f8a2da6f332e2041f023f6f6932005e7d",
    ),
    "infra/n3w-t1/production/image-lock.json": (
        "/opt/HomeAssistant/infra/n3w-t1/production/image-lock.json",
        0o644,
        "31b4676598fc7861593f554e7ec62ed067fc366f7f87d5a9de57c8c788c9b334",
    ),
    "infra/n3w-t1/production/homeassistant-configuration.yaml": (
        "/opt/HomeAssistant/infra/n3w-t1/production/homeassistant-configuration.yaml",
        0o644,
        "ca966d080c2ca2b5ea9cf509cc95a8e6a78987d33b0b062d00acb39ca7bd8b24",
    ),
    "infra/n3w-t1/broker/mosquitto.conf": (
        "/opt/HomeAssistant/infra/n3w-t1/broker/mosquitto.conf",
        0o644,
        "6c8d0f134c26987826cbfd3149cf393249586d74642857c8159862d0005ce59a",
    ),
    "infra/n3w-t1/homeassistant/custom_components/n3w_mqtt_bootstrap/__init__.py": (
        "/opt/HomeAssistant/infra/n3w-t1/homeassistant/custom_components/"
        "n3w_mqtt_bootstrap/__init__.py",
        0o644,
        "00754c5a2e7f3fb7ae210998565c663ee3ede0519687e167ea90692af2cf4397",
    ),
    "infra/n3w-t1/homeassistant/custom_components/n3w_mqtt_bootstrap/manifest.json": (
        "/opt/HomeAssistant/infra/n3w-t1/homeassistant/custom_components/"
        "n3w_mqtt_bootstrap/manifest.json",
        0o644,
        "c4609caa152ee2147a3a4ed4e978bfc252e2ce64bdc38e317198782c501db3c8",
    ),
    "infra/n3w-t1/broker-activation.env.example": (
        "/opt/HomeAssistant/infra/n3w-t1/broker-activation.env.example",
        0o644,
        "a6f3319a111f8e5dd0007aa7ccedf23492af5a2eded6bc9f6da7c35648dc946c",
    ),
    "infra/n3w-t1/systemd/n3wfc4-broker-activation.service": (
        "/opt/HomeAssistant/infra/n3w-t1/systemd/n3wfc4-broker-activation.service",
        0o644,
        "97cc2dad0f6239634493b430651a51ab9ab3bbc92843c1766d2540d0850c31b3",
    ),
    "infra/n3w-t1/systemd/n3wfc4-services-activation.service": (
        "/opt/HomeAssistant/infra/n3w-t1/systemd/n3wfc4-services-activation.service",
        0o644,
        "fdca7cbddbfe4c0ba53d2d3eab6f4e1daebf2e94302ee7a659932c7a0a766ef4",
    ),
    "tools/n3w_t1_broker_authenticated_readiness.py": (
        "/opt/HomeAssistant/tools/n3w_t1_broker_authenticated_readiness.py",
        0o755,
        "f5814cbbed511f0937e70c3e49050100cc60e3a30db30c3c2d696f81d0511c56",
    ),
    "tools/n3w_t1_clean_product_deployment_gate.py": (
        "/opt/HomeAssistant/tools/n3w_t1_clean_product_deployment_gate.py",
        0o755,
        "d1c42fb2abbf8433a1c1f03562abca7994a301edf9f316ad33c9f4da7f6f8acb",
    ),
    "tools/n3w_t1_production_manager_state_prepare.py": (
        "/opt/HomeAssistant/tools/n3w_t1_production_manager_state_prepare.py",
        0o755,
        "319f7c5bd884aa72184d667924e8a6233ca2ed6709325d11ad756f127531a074",
    ),
}

INSTALL_FILES: dict[str, tuple[str, int, str]] = {
    "infra/n3w-t1/production/docker-compose.yml": (
        "/etc/n3wfc4/docker-compose.yml",
        0o644,
        SOURCE_FILES["infra/n3w-t1/production/docker-compose.yml"][2],
    ),
    "infra/n3w-t1/broker-activation.env.example": (
        "/etc/n3wfc4/broker-activation.env",
        0o600,
        SOURCE_FILES["infra/n3w-t1/broker-activation.env.example"][2],
    ),
    "tools/n3w_t1_broker_authenticated_readiness.py": (
        "/usr/local/sbin/n3w-t1-broker-authenticated-readiness",
        0o755,
        SOURCE_FILES["tools/n3w_t1_broker_authenticated_readiness.py"][2],
    ),
    "infra/n3w-t1/systemd/n3wfc4-broker-activation.service": (
        "/etc/systemd/system/n3wfc4-broker-activation.service",
        0o644,
        SOURCE_FILES["infra/n3w-t1/systemd/n3wfc4-broker-activation.service"][2],
    ),
    "infra/n3w-t1/systemd/n3wfc4-services-activation.service": (
        "/etc/systemd/system/n3wfc4-services-activation.service",
        0o644,
        SOURCE_FILES["infra/n3w-t1/systemd/n3wfc4-services-activation.service"][2],
    ),
}
EMPTY_ENV = Path("/etc/n3wfc4/docker-compose.env")


class StagingError(RuntimeError):
    pass


class Runner:
    def run(
        self,
        command: Sequence[str],
        *,
        input_text: str | None = None,
        timeout: float = 300.0,
        allowed: frozenset[int] = frozenset({0}),
    ) -> str:
        completed = subprocess.run(
            tuple(command),
            input=input_text,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
        if completed.returncode not in allowed:
            reason = completed.stderr.strip() or completed.stdout.strip()
            raise StagingError(
                f"command_failed:{command[0]}:{completed.returncode}:{reason[:300]}"
            )
        return completed.stdout


def _event(phase: str, status: str) -> None:
    print(
        json.dumps(
            {"schema": SCHEMA, "event": phase, "status": status},
            sort_keys=True,
            separators=(",", ":"),
        ),
        flush=True,
    )


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _require_regular(path: Path, *, uid: int, gid: int, mode: int) -> None:
    if path.is_symlink() or not path.is_file():
        raise StagingError(f"unsafe_or_missing_file:{path}")
    info = path.stat()
    if info.st_uid != uid or info.st_gid != gid or stat.S_IMODE(info.st_mode) != mode:
        raise StagingError(f"owner_mode_drift:{path}")


def _require_directory(path: Path, *, uid: int, gid: int, mode: int) -> None:
    if path.is_symlink() or not path.is_dir():
        raise StagingError(f"unsafe_or_missing_directory:{path}")
    info = path.stat()
    if info.st_uid != uid or info.st_gid != gid or stat.S_IMODE(info.st_mode) != mode:
        raise StagingError(f"owner_mode_drift:{path}")


def _volume_set(runner: Runner) -> tuple[int, str]:
    names = sorted(
        line.strip()
        for line in runner.run(("docker", "volume", "ls", "-q")).splitlines()
        if line.strip()
    )
    payload = "".join(f"{name}\n" for name in names).encode()
    return len(names), _sha256_bytes(payload)


def _network_counts(runner: Runner) -> dict[str, int]:
    result: dict[str, int] = {}
    for name in NETWORKS:
        output = runner.run(
            ("docker", "network", "inspect", "-f", "{{len .Containers}}", name)
        ).strip()
        if not output.isdigit():
            raise StagingError("network_inventory_invalid")
        result[name] = int(output)
    return result


def _listener_count(output: str, port: int) -> int:
    pattern = re.compile(rf":{port}(?:\s|$)")
    return sum(bool(pattern.search(line)) for line in output.splitlines())


def _listener_counts(runner: Runner) -> dict[str, int]:
    tcp = runner.run(("ss", "-H", "-ltn"))
    udp = runner.run(("ss", "-H", "-lun"))
    result = {f"tcp_{port}": _listener_count(tcp, port) for port in PORTS_TCP}
    result.update({f"udp_{port}": _listener_count(udp, port) for port in PORTS_UDP})
    return result


def _guard_contract(runner: Runner) -> dict[str, bool]:
    active = runner.run(
        ("systemctl", "is-active", "n3wfc4-broker-ingress-guard.service")
    ).strip()
    enabled = runner.run(
        ("systemctl", "is-enabled", "n3wfc4-broker-ingress-guard.service")
    ).strip()
    input_rules = runner.run(("iptables", "-S", "INPUT")).splitlines()
    docker_rules = runner.run(("iptables", "-S", "DOCKER-USER")).splitlines()
    ingress_rules = runner.run(("iptables", "-S", "N3WFC4-BROKER-INGRESS")).splitlines()
    input_appends = [line for line in input_rules if line.startswith("-A INPUT ")]
    docker_appends = [
        line for line in docker_rules if line.startswith("-A DOCKER-USER ")
    ]
    ingress_appends = [
        line for line in ingress_rules if line.startswith("-A N3WFC4-BROKER-INGRESS ")
    ]
    if active != "active" or enabled != "enabled":
        raise StagingError("guard_state_drift")
    if not input_appends or "-j N3WFC4-BROKER-INGRESS" not in input_appends[0]:
        raise StagingError("guard_input_anchor_drift")
    if not docker_appends or "-j N3WFC4-BROKER-INGRESS" not in docker_appends[0]:
        raise StagingError("guard_docker_anchor_drift")
    if sum("-j N3WFC4-BROKER-INGRESS" in line for line in input_appends) != 1:
        raise StagingError("guard_input_anchor_count_drift")
    if sum("-j N3WFC4-BROKER-INGRESS" in line for line in docker_appends) != 1:
        raise StagingError("guard_docker_anchor_count_drift")
    if not ingress_appends or not ingress_appends[-1].endswith("-j DROP"):
        raise StagingError("guard_terminal_drop_drift")
    return {"active": True, "enabled": True, "exact": True}


def _manager_database_report() -> dict[str, Any]:
    _require_regular(MANAGER_DB, uid=999, gid=999, mode=0o600)
    uri = f"{MANAGER_DB.resolve().as_uri()}?mode=ro&immutable=1"
    connection = sqlite3.connect(uri, uri=True)
    try:
        quick = connection.execute("PRAGMA quick_check").fetchone()
        if quick is None or quick[0] != "ok":
            raise StagingError("manager_database_integrity_invalid")
        tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        if tables != EXPECTED_MANAGER_TABLES:
            raise StagingError("manager_database_table_set_drift")
        business_rows = sum(
            int(connection.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0])
            for name in BUSINESS_TABLES
        )
        provenance = connection.execute(
            "SELECT schema, system_id_fingerprint, "
            "structured_legacy_manager_state_imported, anonymous_nodes_reconstructed "
            "FROM h0h1_legacy_adoption_provenance"
        ).fetchall()
        if business_rows != 0 or len(provenance) != 1:
            raise StagingError("manager_database_not_clean")
        row = provenance[0]
        if (
            row[0] != "gh.h0h1.legacy-adoption-provenance/1"
            or row[1] != EXPECTED_SYSTEM_ID_SHA256
            or row[2] != 0
            or row[3] != 0
        ):
            raise StagingError("manager_database_provenance_drift")
        return {
            "sha256": _sha256_file(MANAGER_DB),
            "quick_check": "ok",
            "business_rows": 0,
            "provenance_rows": 1,
        }
    finally:
        connection.close()


def _identity_claim_count() -> int:
    if SYSTEM_IDENTITY.is_symlink() or not SYSTEM_IDENTITY.is_file():
        raise StagingError("system_identity_missing_or_unsafe")
    document = json.loads(SYSTEM_IDENTITY.read_text(encoding="utf-8"))
    system_id = document.get("system_id")
    if (
        not isinstance(system_id, str)
        or _sha256_bytes(system_id.encode()) != EXPECTED_SYSTEM_ID_SHA256
    ):
        raise StagingError("system_identity_drift")
    count = 0
    seen: set[Path] = set()
    for root in (Path("/etc"), Path("/var/lib"), Path("/opt")):
        for candidate in root.rglob("identity-claims.json"):
            if candidate in seen:
                continue
            seen.add(candidate)
            if candidate.is_symlink() or not candidate.is_file():
                continue
            try:
                claims = json.loads(candidate.read_text(encoding="utf-8")).get(
                    "claims", {}
                )
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(claims, dict) and isinstance(claims.get(system_id), dict):
                count += 1
    return count


def _secret_bundle_report() -> dict[str, Any]:
    _require_directory(SECRET_ROOT, uid=0, gid=0, mode=0o700)
    records: list[str] = []
    for path in sorted(SECRET_ROOT.rglob("*")):
        if path.is_symlink():
            raise StagingError("secret_bundle_symlink_present")
        if path.is_dir():
            continue
        if not path.is_file():
            raise StagingError("secret_bundle_special_file_present")
        info = path.stat()
        records.append(
            "|".join(
                (
                    path.relative_to(SECRET_ROOT).as_posix(),
                    str(info.st_uid),
                    str(info.st_gid),
                    f"{stat.S_IMODE(info.st_mode):03o}",
                    str(info.st_size),
                    _sha256_file(path),
                )
            )
        )
    if len(records) != 11:
        raise StagingError("secret_file_count_drift")
    payload = "".join(f"{line}\n" for line in records).encode()
    return {"file_count": 11, "aggregate_sha256": _sha256_bytes(payload)}


def _payload_report(payload_root: Path) -> dict[str, Any]:
    if payload_root.is_symlink() or not payload_root.is_dir():
        raise StagingError("payload_root_invalid")
    for relative, (_target, _mode, expected_sha) in SOURCE_FILES.items():
        source = payload_root / relative
        if source.is_symlink() or not source.is_file():
            raise StagingError(f"payload_source_missing:{relative}")
        if _sha256_file(source) != expected_sha:
            raise StagingError(f"payload_source_sha_drift:{relative}")
    manager_tar = payload_root / "artifact/greenhouse-manager-arm64.tar"
    if manager_tar.is_symlink() or not manager_tar.is_file():
        raise StagingError("manager_artifact_missing")
    if _sha256_file(manager_tar) != EXPECTED_MANAGER_TAR_SHA256:
        raise StagingError("manager_artifact_sha_drift")
    return {
        "source_file_count": len(SOURCE_FILES),
        "manager_tar_sha256": EXPECTED_MANAGER_TAR_SHA256,
    }


def _image_present(runner: Runner, image: str) -> bool:
    completed = subprocess.run(
        ("docker", "image", "inspect", image),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return completed.returncode == 0


def _image_report(runner: Runner, image: str, expected_id: str) -> dict[str, str]:
    output = runner.run(
        (
            "docker",
            "image",
            "inspect",
            "--format",
            "{{.Id}}|{{.Os}}|{{.Architecture}}",
            image,
        )
    ).strip()
    if output != f"{expected_id}|linux|arm64":
        raise StagingError(f"image_binding_drift:{image}")
    return {"id": expected_id, "platform": "linux/arm64"}


def _unit_load_state(runner: Runner, unit: str) -> str:
    return runner.run(
        ("systemctl", "show", "-p", "LoadState", "--value", unit),
        allowed=frozenset({0, 1, 3, 4}),
    ).strip()


def _verify_targets_absent(runner: Runner) -> None:
    targets = [
        OPT_ROOT,
        N3W_ROOT,
        HA_ROOT,
        EMPTY_ENV,
        *(Path(item[0]) for item in INSTALL_FILES.values()),
    ]
    for target in targets:
        if target.exists() or target.is_symlink():
            raise StagingError(f"staging_target_collision:{target}")
    if DISPATCHER.exists() or DISPATCHER.is_symlink():
        raise StagingError("dispatcher_present")
    for unit in ACTIVATION_UNITS:
        if _unit_load_state(runner, unit) != "not-found":
            raise StagingError(f"activation_unit_already_loaded:{unit}")


def _verify_collision_directory() -> None:
    _require_directory(LEGACY_COLLISION, uid=0, gid=0, mode=0o755)
    if any(LEGACY_COLLISION.iterdir()):
        raise StagingError("legacy_collision_not_empty")


def preflight(runner: Runner, payload_root: Path) -> dict[str, Any]:
    if os.geteuid() != 0:
        raise StagingError("root_required")
    if runner.run(("uname", "-m")).strip() != EXPECTED_ARCH:
        raise StagingError("architecture_drift")
    containers = [
        line for line in runner.run(("docker", "ps", "-aq")).splitlines() if line
    ]
    if containers:
        raise StagingError("container_count_drift")
    volume_count, volume_sha = _volume_set(runner)
    if (
        volume_count != EXPECTED_VOLUME_COUNT
        or volume_sha != EXPECTED_VOLUME_SET_SHA256
    ):
        raise StagingError("docker_volume_set_drift")
    networks = _network_counts(runner)
    if any(networks.values()):
        raise StagingError("project_network_not_empty")
    listeners = _listener_counts(runner)
    if any(listeners.values()):
        raise StagingError("production_listener_present")
    guard = _guard_contract(runner)
    if DYNSEC_PATH.is_symlink() or not DYNSEC_PATH.is_file():
        raise StagingError("dynsec_missing_or_unsafe")
    if _sha256_file(DYNSEC_PATH) != EXPECTED_DYNSEC_SHA256:
        raise StagingError("dynsec_sha_drift")
    secrets = _secret_bundle_report()
    if TRANSACTION_DIR.exists() or TRANSACTION_DIR.is_symlink():
        raise StagingError("prior_transaction_directory_present")
    _require_directory(MANAGER_DIR, uid=999, gid=999, mode=0o700)
    manager = _manager_database_report()
    _verify_collision_directory()
    if _identity_claim_count() != 1:
        raise StagingError("identity_claim_count_drift")
    _verify_targets_absent(runner)
    for image in (EXPECTED_MANAGER_IMAGE, EXPECTED_HA_IMAGE, EXPECTED_BROKER_IMAGE):
        if _image_present(runner, image):
            raise StagingError(f"production_image_already_present:{image}")
    free_bytes = shutil.disk_usage("/").free
    if free_bytes < MIN_ROOT_AVAILABLE_BYTES:
        raise StagingError("root_capacity_insufficient")
    payload = _payload_report(payload_root)
    return {
        "status": "PASS",
        "authorization_id": AUTHORIZATION_ID,
        "docker_container_count": 0,
        "docker_volume_count": volume_count,
        "docker_volume_set_sha256": volume_sha,
        "project_network_container_counts": networks,
        "listener_counts": listeners,
        "guard": guard,
        "dynsec_sha256": EXPECTED_DYNSEC_SHA256,
        "secret_bundle": secrets,
        "identity_claim_count": 1,
        "manager_database": manager,
        "legacy_collision": "empty_root_root_0755_directory",
        "n3w_state_root": "absent",
        "production_images": "absent",
        "production_services": "stopped",
        "root_available_bytes": free_bytes,
        "payload": payload,
        "live_mutation": False,
        "production_service_start": False,
        "board_access": False,
    }


def _write_new_file(source: Path, target: Path, mode: int) -> None:
    data = source.read_bytes()
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(target, flags, mode)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    os.chown(target, 0, 0)
    os.chmod(target, mode)


def _write_empty_private(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    os.close(descriptor)
    os.chown(path, 0, 0)
    os.chmod(path, 0o600)


def _run_manager_state(
    runner: Runner, payload_root: Path, phase: str
) -> dict[str, Any]:
    script = (
        payload_root / "tools/n3w_t1_production_manager_state_prepare.py"
    ).read_text(encoding="utf-8")
    output = runner.run(
        (
            "docker",
            "run",
            "--rm",
            "-i",
            "--platform",
            "linux/arm64",
            "--network",
            "none",
            "--user",
            "999:999",
            "--read-only",
            "--tmpfs",
            "/tmp:size=16m,mode=1777",
            "--mount",
            "type=bind,src=/var/lib/greenhouse-manager/manager,"
            "dst=/var/lib/greenhouse-manager/manager",
            "--mount",
            "type=bind,src=/var/lib/greenhouse-manager/n3w,"
            "dst=/var/lib/greenhouse-manager/n3w",
            "--entrypoint",
            "python",
            EXPECTED_MANAGER_IMAGE,
            "-",
            "--phase",
            phase,
            "--manager-db",
            str(MANAGER_DB),
            "--n3w-root",
            str(N3W_ROOT),
            "--expected-system-id-sha256",
            EXPECTED_SYSTEM_ID_SHA256,
        ),
        input_text=script,
        timeout=180.0,
    )
    report = json.loads(output)
    if report.get("status") != "PASS" or report.get("phase") != phase:
        raise StagingError(f"manager_state_{phase}_failed")
    return report


def _render_and_validate(runner: Runner) -> dict[str, Any]:
    compose_json = runner.run(
        (
            "docker",
            "compose",
            "--project-name",
            "n3wfc4",
            "--env-file",
            str(EMPTY_ENV),
            "-f",
            "/etc/n3wfc4/docker-compose.yml",
            "--profile",
            "application",
            "config",
            "--format",
            "json",
        )
    )
    json.loads(compose_json)
    gate = runner.run(
        (
            "python3",
            "/opt/HomeAssistant/tools/n3w_t1_clean_product_deployment_gate.py",
            "--compose-json",
            "-",
            "--image-lock-json",
            "/opt/HomeAssistant/infra/n3w-t1/production/image-lock.json",
        ),
        input_text=compose_json,
    )
    report = json.loads(gate)
    if report.get("status") != "PASS":
        raise StagingError("deployment_gate_failed")
    return report


def _verify_staged_files() -> None:
    expected_opt_files = {Path(target) for target, _mode, _sha in SOURCE_FILES.values()}
    actual_opt_files = {path for path in OPT_ROOT.rglob("*") if path.is_file()}
    if actual_opt_files != expected_opt_files:
        raise StagingError("staged_opt_file_set_drift")
    for _source, (target, mode, expected_sha) in SOURCE_FILES.items():
        path = Path(target)
        _require_regular(path, uid=0, gid=0, mode=mode)
        if _sha256_file(path) != expected_sha:
            raise StagingError(f"staged_file_sha_drift:{path}")
    for _source, (target, mode, expected_sha) in INSTALL_FILES.items():
        path = Path(target)
        _require_regular(path, uid=0, gid=0, mode=mode)
        if _sha256_file(path) != expected_sha:
            raise StagingError(f"installed_file_sha_drift:{path}")
    _require_regular(EMPTY_ENV, uid=0, gid=0, mode=0o600)
    if EMPTY_ENV.stat().st_size != 0:
        raise StagingError("compose_env_not_empty")


def _unit_stopped_disabled(runner: Runner, unit: str) -> dict[str, str]:
    active = runner.run(
        ("systemctl", "is-active", unit), allowed=frozenset({0, 1, 3, 4})
    ).strip()
    enabled = runner.run(
        ("systemctl", "is-enabled", unit), allowed=frozenset({0, 1, 3, 4})
    ).strip()
    if active != "inactive" or enabled != "disabled":
        raise StagingError(f"activation_unit_state_invalid:{unit}:{active}:{enabled}")
    return {"active": active, "enabled": enabled}


def postcheck(
    runner: Runner,
    payload_root: Path,
    *,
    manager_sha_before: str,
    secret_aggregate_before: str,
) -> dict[str, Any]:
    containers = [
        line for line in runner.run(("docker", "ps", "-aq")).splitlines() if line
    ]
    if containers:
        raise StagingError("postcheck_container_present")
    volume_count, volume_sha = _volume_set(runner)
    if (
        volume_count != EXPECTED_VOLUME_COUNT
        or volume_sha != EXPECTED_VOLUME_SET_SHA256
    ):
        raise StagingError("postcheck_volume_set_drift")
    networks = _network_counts(runner)
    if any(networks.values()):
        raise StagingError("postcheck_project_network_not_empty")
    listeners = _listener_counts(runner)
    if any(listeners.values()):
        raise StagingError("postcheck_listener_present")
    guard = _guard_contract(runner)
    if _sha256_file(DYNSEC_PATH) != EXPECTED_DYNSEC_SHA256:
        raise StagingError("postcheck_dynsec_sha_drift")
    secrets = _secret_bundle_report()
    if secrets["aggregate_sha256"] != secret_aggregate_before:
        raise StagingError("postcheck_secret_bundle_drift")
    manager = _manager_database_report()
    if manager["sha256"] != manager_sha_before:
        raise StagingError("postcheck_manager_database_mutated")
    if LEGACY_COLLISION.exists() or LEGACY_COLLISION.is_symlink():
        raise StagingError("postcheck_legacy_collision_present")
    _require_directory(N3W_ROOT, uid=999, gid=999, mode=0o700)
    manager_state = _run_manager_state(runner, payload_root, "audit")
    _require_directory(HA_ROOT, uid=0, gid=0, mode=0o700)
    if any(HA_ROOT.iterdir()):
        raise StagingError("homeassistant_state_not_empty")
    images = {
        "manager": _image_report(
            runner, EXPECTED_MANAGER_IMAGE, EXPECTED_MANAGER_IMAGE_ID
        ),
        "homeassistant": _image_report(runner, EXPECTED_HA_IMAGE, EXPECTED_HA_IMAGE_ID),
        "broker": _image_report(
            runner, EXPECTED_BROKER_IMAGE, EXPECTED_BROKER_IMAGE_ID
        ),
    }
    _verify_staged_files()
    units = {unit: _unit_stopped_disabled(runner, unit) for unit in ACTIVATION_UNITS}
    if DISPATCHER.exists() or DISPATCHER.is_symlink():
        raise StagingError("postcheck_dispatcher_present")
    deployment = _render_and_validate(runner)
    return {
        "status": "PASS",
        "authorization_id": AUTHORIZATION_ID,
        "docker_container_count": 0,
        "docker_volume_count": volume_count,
        "docker_volume_set_sha256": volume_sha,
        "project_network_container_counts": networks,
        "listener_counts": listeners,
        "guard": guard,
        "dynsec_sha256": EXPECTED_DYNSEC_SHA256,
        "secret_bundle": secrets,
        "manager_database": manager,
        "manager_state": manager_state,
        "legacy_collision_absent": True,
        "homeassistant_state_empty": True,
        "images": images,
        "source_file_count": len(SOURCE_FILES),
        "activation_units": units,
        "dispatcher_absent": True,
        "deployment_gate": deployment,
        "production_service_start": False,
        "board_access": False,
        "authorization_consumed": True,
    }


def _remove_ref(runner: Runner, image: str) -> None:
    subprocess.run(
        ("docker", "image", "rm", image),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=180,
    )


def rollback(runner: Runner, payload_root: Path) -> dict[str, Any]:
    errors: list[str] = []
    for unit in ACTIVATION_UNITS:
        subprocess.run(
            ("systemctl", "stop", unit),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    for target in [EMPTY_ENV, *(Path(item[0]) for item in INSTALL_FILES.values())]:
        try:
            if target.is_symlink():
                errors.append(f"unsafe_rollback_target:{target}")
            elif target.is_file():
                target.unlink()
        except OSError as error:
            errors.append(f"remove_failed:{target}:{type(error).__name__}")
    if OPT_ROOT.exists() and not OPT_ROOT.is_symlink():
        try:
            shutil.rmtree(OPT_ROOT)
        except OSError as error:
            errors.append(f"remove_opt_failed:{type(error).__name__}")
    elif OPT_ROOT.is_symlink():
        errors.append("unsafe_opt_root_symlink")
    if HA_ROOT.exists() and not HA_ROOT.is_symlink():
        try:
            if any(HA_ROOT.iterdir()):
                errors.append("ha_root_not_empty")
            else:
                HA_ROOT.rmdir()
        except OSError as error:
            errors.append(f"ha_root_remove_failed:{type(error).__name__}")
    elif HA_ROOT.is_symlink():
        errors.append("unsafe_ha_root_symlink")
    if N3W_ROOT.exists() and not N3W_ROOT.is_symlink():
        try:
            children = {path.name for path in N3W_ROOT.iterdir()}
            if children and children != {
                "replay.sqlite3",
                "relay-authorization.sqlite3",
                "relay-keys",
            }:
                errors.append("n3w_root_unexpected_children")
            else:
                if children and _image_present(runner, EXPECTED_MANAGER_IMAGE):
                    _run_manager_state(runner, payload_root, "audit")
                shutil.rmtree(N3W_ROOT)
        except (OSError, StagingError, json.JSONDecodeError) as error:
            errors.append(f"n3w_root_remove_failed:{type(error).__name__}")
    elif N3W_ROOT.is_symlink():
        errors.append("unsafe_n3w_root_symlink")
    if not (LEGACY_COLLISION.exists() or LEGACY_COLLISION.is_symlink()):
        try:
            LEGACY_COLLISION.mkdir(mode=0o755)
            os.chown(LEGACY_COLLISION, 0, 0)
            os.chmod(LEGACY_COLLISION, 0o755)
        except OSError as error:
            errors.append(f"collision_restore_failed:{type(error).__name__}")
    for image in (EXPECTED_BROKER_IMAGE, EXPECTED_HA_IMAGE, EXPECTED_MANAGER_IMAGE):
        _remove_ref(runner, image)
    try:
        runner.run(("systemctl", "daemon-reload"))
    except StagingError as error:
        errors.append(str(error))
    containers = subprocess.run(
        ("docker", "ps", "-aq"), capture_output=True, text=True, check=False
    ).stdout.strip()
    if containers:
        errors.append("rollback_container_present")
    try:
        if any(_listener_counts(runner).values()):
            errors.append("rollback_listener_present")
    except StagingError as error:
        errors.append(str(error))
    return {
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "production_service_start": False,
    }


def apply_staging(runner: Runner, payload_root: Path) -> dict[str, Any]:
    _event("fresh_preflight", "START")
    baseline = preflight(runner, payload_root)
    _event("fresh_preflight", "PASS")
    manager_sha = str(baseline["manager_database"]["sha256"])
    secret_aggregate = str(baseline["secret_bundle"]["aggregate_sha256"])
    mutated = False
    try:
        _event("state_root_prepare", "START")
        _verify_collision_directory()
        LEGACY_COLLISION.rmdir()
        N3W_ROOT.mkdir(mode=0o700)
        os.chown(N3W_ROOT, 999, 999)
        os.chmod(N3W_ROOT, 0o700)
        mutated = True
        _event("state_root_prepare", "PASS")

        _event("manager_image_load", "START")
        runner.run(
            (
                "docker",
                "load",
                "--input",
                str(payload_root / "artifact/greenhouse-manager-arm64.tar"),
            ),
            timeout=300,
        )
        _image_report(runner, EXPECTED_MANAGER_IMAGE, EXPECTED_MANAGER_IMAGE_ID)
        _event("manager_image_load", "PASS")

        _event("manager_state_prepare", "START")
        _run_manager_state(runner, payload_root, "prepare")
        _event("manager_state_prepare", "PASS")

        _event("production_image_pull", "START")
        runner.run(
            ("docker", "pull", "--platform", "linux/arm64", EXPECTED_HA_IMAGE),
            timeout=1200,
        )
        _image_report(runner, EXPECTED_HA_IMAGE, EXPECTED_HA_IMAGE_ID)
        runner.run(
            ("docker", "pull", "--platform", "linux/arm64", EXPECTED_BROKER_IMAGE),
            timeout=600,
        )
        _image_report(runner, EXPECTED_BROKER_IMAGE, EXPECTED_BROKER_IMAGE_ID)
        _event("production_image_pull", "PASS")

        _event("source_and_unit_stage", "START")
        OPT_ROOT.mkdir(mode=0o755)
        os.chown(OPT_ROOT, 0, 0)
        for relative, (target, mode, _sha) in SOURCE_FILES.items():
            _write_new_file(payload_root / relative, Path(target), mode)
        for relative, (target, mode, _sha) in INSTALL_FILES.items():
            _write_new_file(payload_root / relative, Path(target), mode)
        _write_empty_private(EMPTY_ENV)
        HA_ROOT.mkdir(mode=0o700)
        os.chown(HA_ROOT, 0, 0)
        os.chmod(HA_ROOT, 0o700)
        runner.run(("systemctl", "daemon-reload"))
        _event("source_and_unit_stage", "PASS")

        _event("render_and_postcheck", "START")
        result = postcheck(
            runner,
            payload_root,
            manager_sha_before=manager_sha,
            secret_aggregate_before=secret_aggregate,
        )
        _event("render_and_postcheck", "PASS")
        return result
    except BaseException as error:
        rollback_report = (
            rollback(runner, payload_root)
            if mutated
            else {
                "status": "NOT_REQUIRED",
                "errors": [],
            }
        )
        if isinstance(error, (KeyboardInterrupt, SystemExit)):
            raise
        raise StagingError(
            json.dumps(
                {
                    "reason": f"{type(error).__name__}:{error}",
                    "rollback": rollback_report,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        ) from error


def _verify_executor_binding(expected_sha256: str | None) -> None:
    if expected_sha256 is None:
        return
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise StagingError("executor_sha256_invalid")
    if _sha256_file(Path(__file__)) != expected_sha256:
        raise StagingError("executor_sha256_mismatch")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("preflight", "apply"), required=True)
    parser.add_argument("--payload-root", type=Path, required=True)
    parser.add_argument("--authorization-id")
    parser.add_argument("--expected-executor-sha256")
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        _verify_executor_binding(args.expected_executor_sha256)
        if args.phase == "apply":
            if args.authorization_id != AUTHORIZATION_ID:
                raise StagingError("authorization_id_missing_or_invalid")
            report = apply_staging(Runner(), args.payload_root)
        else:
            report = preflight(Runner(), args.payload_root)
    except (
        StagingError,
        OSError,
        json.JSONDecodeError,
        sqlite3.Error,
        subprocess.TimeoutExpired,
    ) as error:
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "phase": args.phase,
                    "status": "STOP",
                    "reason": str(error),
                    "authorization_id": AUTHORIZATION_ID,
                    "production_service_start": False,
                    "board_access": False,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 2
    print(
        json.dumps(
            {"schema": SCHEMA, "phase": args.phase, **report},
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
