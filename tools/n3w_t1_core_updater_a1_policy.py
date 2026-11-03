from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import stat
import subprocess
from pathlib import Path
from typing import Any, Protocol

from n3w_t1_core_updater_v2_common import UpdaterV2Error

MOSQUITTO_CONFIG = Path("/opt/HomeAssistant/infra/n3w-t1/broker/mosquitto.conf")
HA_CONFIG = Path("/opt/HomeAssistant/infra/n3w-t1/production/homeassistant-configuration.yaml")
CUSTOM_COMPONENT = Path(
    "/opt/HomeAssistant/infra/n3w-t1/homeassistant/custom_components/n3w_mqtt_bootstrap"
)
PERSISTENT_DIRS = {
    "manager": Path("/var/lib/greenhouse-manager/manager"),
    "n3w": Path("/var/lib/greenhouse-manager/n3w"),
    "broker": Path("/var/lib/n3wfc4-broker"),
    "homeassistant": Path("/var/lib/n3wfc4-homeassistant"),
}
EXPECTED_PERSISTENT_OWNERS = {
    "manager": (999, 999),
    "n3w": (999, 999),
    "broker": (1883, 1883),
    "homeassistant": (0, 0),
}
SQLITE_DATABASES = {
    "manager": Path("/var/lib/greenhouse-manager/manager/manager-state.sqlite3"),
    "replay": Path("/var/lib/greenhouse-manager/n3w/replay.sqlite3"),
    "relay_authorization": Path(
        "/var/lib/greenhouse-manager/n3w/relay-authorization.sqlite3"
    ),
}
FC4_CA = Path("/etc/n3wfc4/tls/ca.pem")
BROKER_SERVER_CERT = Path("/etc/n3wfc4/tls/server.pem")
SYSTEM_CA = Path("/var/lib/greenhouse-manager/identity/system-ca.pem")
DYNSEC = Path("/var/lib/n3wfc4-broker/dynamic-security.json")
MQTT_IDENTITIES = {
    "manager": Path("/opt/greenhouse-secrets/mqtt/manager/identity.json"),
    "homeassistant": Path(
        "/opt/greenhouse-secrets/mqtt/homeassistant/identity.json"
    ),
}
HA_STORAGE = Path("/var/lib/n3wfc4-homeassistant/.storage")
HA_STORAGE_FILES = {
    "config_entries": ("core.config_entries", "entries"),
    "devices": ("core.device_registry", "devices"),
    "entities": ("core.entity_registry", "entities"),
}
BROKER_TLS_SERVER_NAME = "armbian"


class A1Policy(Protocol):
    def capture(self) -> dict[str, Any]: ...
    def hard_authority(self, snapshot: dict[str, Any]) -> dict[str, Any]: ...
    def validate_baseline(
        self,
        component: str,
        snapshot: dict[str, Any],
        expected: dict[str, Any],
    ) -> None: ...
    def validate_pre(self, component: str, snapshot: dict[str, Any]) -> None: ...
    def validate_post(
        self,
        component: str,
        before: dict[str, Any],
        after: dict[str, Any],
    ) -> None: ...


def _canonical_sha(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise UpdaterV2Error(f"a1_file_invalid:{path.name}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json_file(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise UpdaterV2Error(f"a1_json_invalid:{path.name}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise UpdaterV2Error(f"a1_json_invalid:{path.name}") from error
    if not isinstance(value, dict):
        raise UpdaterV2Error(f"a1_json_invalid:{path.name}")
    return value


def _path_metadata(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_dir():
        raise UpdaterV2Error(f"a1_path_invalid:{path.name}")
    item = path.stat()
    symlink_count = 0
    for current, dirnames, filenames in os.walk(path, followlinks=False):
        base = Path(current)
        for name in list(dirnames):
            child = base / name
            if child.is_symlink():
                symlink_count += 1
                dirnames.remove(name)
        for name in filenames:
            if (base / name).is_symlink():
                symlink_count += 1
    return {
        "uid": item.st_uid,
        "gid": item.st_gid,
        "mode": format(stat.S_IMODE(item.st_mode), "04o"),
        "type": "directory",
        "symlink_count": symlink_count,
    }


def _safe_mode(mode: str) -> bool:
    try:
        value = int(mode, 8)
    except ValueError:
        return False
    return (value & 0o022) == 0


def _tree_hash(root: Path) -> str:
    if root.is_symlink() or not root.is_dir():
        raise UpdaterV2Error("a1_custom_component_invalid")
    rows: list[tuple[str, str]] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise UpdaterV2Error("a1_custom_component_symlink")
        if path.is_file():
            rows.append((path.relative_to(root).as_posix(), _sha256_file(path)))
    return _canonical_sha(rows)


def _sqlite_snapshot(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise UpdaterV2Error(f"a1_sqlite_invalid:{path.name}")
    connection = sqlite3.connect(
        f"{path.resolve().as_uri()}?mode=ro",
        uri=True,
        timeout=5,
    )
    try:
        connection.execute("PRAGMA query_only=ON")
        quick = connection.execute("PRAGMA quick_check").fetchone()
        if quick is None:
            raise UpdaterV2Error(f"a1_sqlite_quick_check_invalid:{path.name}")
        user_version = int(
            connection.execute("PRAGMA user_version").fetchone()[0]
        )
        records = [
            (str(row[0]), str(row[1] or ""))
            for row in connection.execute(
                "SELECT name, sql FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        return {
            "quick_check": str(quick[0]),
            "user_version": user_version,
            "schema_sha256": _canonical_sha(records),
        }
    finally:
        connection.close()


def _mqtt_identity(path: Path) -> str:
    document = _json_file(path)
    client_id = document.get("client_id")
    username = document.get("username")
    if not isinstance(client_id, str) or not isinstance(username, str):
        raise UpdaterV2Error("a1_mqtt_identity_invalid")
    return _canonical_sha({"client_id": client_id, "username": username})


def _dynsec_keys() -> str:
    document = _json_file(DYNSEC)
    return _canonical_sha(sorted(document))


def _ha_storage_snapshot() -> dict[str, Any]:
    result: dict[str, Any] = {}
    for label, (filename, key) in HA_STORAGE_FILES.items():
        path = HA_STORAGE / filename
        if not path.exists():
            result[label] = {"present": False, "version": None}
            continue
        document = _json_file(path)
        data = document.get("data")
        if not isinstance(data, dict) or not isinstance(data.get(key, []), list):
            raise UpdaterV2Error(f"a1_ha_storage_invalid:{label}")
        result[label] = {
            "present": True,
            "version": document.get("version"),
        }
    return result


def _tls_semantics() -> dict[str, bool]:
    if any(
        path.is_symlink() or not path.is_file()
        for path in (FC4_CA, BROKER_SERVER_CERT)
    ):
        raise UpdaterV2Error("a1_tls_material_invalid")
    verify = subprocess.run(
        ("openssl", "verify", "-CAfile", str(FC4_CA), str(BROKER_SERVER_CERT)),
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=20,
    )
    host = subprocess.run(
        (
            "openssl",
            "x509",
            "-in",
            str(BROKER_SERVER_CERT),
            "-noout",
            "-checkhost",
            BROKER_TLS_SERVER_NAME,
            "-checkend",
            "0",
        ),
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=20,
    )
    return {
        "chain_valid": verify.returncode == 0,
        "hostname_and_validity_valid": host.returncode == 0,
    }


class LocalA1Policy:
    def hard_authority(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        return {
            "fixed_config": snapshot["fixed_config"],
            "persistent_identity": {
                name: {
                    "uid": item["uid"],
                    "gid": item["gid"],
                    "type": item["type"],
                }
                for name, item in snapshot["persistent_paths"].items()
            },
            "sqlite": {
                name: {
                    "user_version": item["user_version"],
                    "schema_sha256": item["schema_sha256"],
                }
                for name, item in snapshot["sqlite"].items()
            },
            "trust": {
                "fc4_ca_sha256": snapshot["trust"]["fc4_ca_sha256"],
                "system_ca_sha256": snapshot["trust"]["system_ca_sha256"],
            },
            "dynsec_top_level_keys_sha256": snapshot[
                "dynsec_top_level_keys_sha256"
            ],
            "mqtt_identity": snapshot["mqtt_identity"],
            "ha_storage_versions": {
                label: item["version"]
                for label, item in snapshot["ha_storage"].items()
            },
        }

    def validate_baseline(
        self,
        component: str,
        snapshot: dict[str, Any],
        expected: dict[str, Any],
    ) -> None:
        del component
        if self.hard_authority(snapshot) != expected:
            raise UpdaterV2Error("a1_per_instance_baseline_drift")

    def capture(self) -> dict[str, Any]:
        return {
            "fixed_config": {
                "mosquitto": _sha256_file(MOSQUITTO_CONFIG),
                "homeassistant": _sha256_file(HA_CONFIG),
                "custom_component": _tree_hash(CUSTOM_COMPONENT),
            },
            "persistent_paths": {
                name: _path_metadata(path)
                for name, path in PERSISTENT_DIRS.items()
            },
            "sqlite": {
                name: _sqlite_snapshot(path)
                for name, path in SQLITE_DATABASES.items()
            },
            "trust": {
                "fc4_ca_sha256": _sha256_file(FC4_CA),
                "system_ca_sha256": _sha256_file(SYSTEM_CA),
                "server_cert_sha256_diagnostic": _sha256_file(
                    BROKER_SERVER_CERT
                ),
                "tls_semantics": _tls_semantics(),
            },
            "dynsec_top_level_keys_sha256": _dynsec_keys(),
            "mqtt_identity": {
                name: _mqtt_identity(path)
                for name, path in MQTT_IDENTITIES.items()
            },
            "ha_storage": _ha_storage_snapshot(),
        }

    def validate_pre(self, component: str, snapshot: dict[str, Any]) -> None:
        del component
        for name, item in snapshot["persistent_paths"].items():
            if item.get("type") != "directory":
                raise UpdaterV2Error(f"a1_path_type_invalid:{name}")
            expected_owner = EXPECTED_PERSISTENT_OWNERS[name]
            if (
                item.get("uid") != expected_owner[0]
                or item.get("gid") != expected_owner[1]
            ):
                raise UpdaterV2Error(f"a1_path_owner_invalid:{name}")
            if item.get("symlink_count") != 0:
                raise UpdaterV2Error(f"a1_path_symlink_invalid:{name}")
            if not _safe_mode(str(item.get("mode"))):
                raise UpdaterV2Error(f"a1_path_mode_unsafe:{name}")
        for name, item in snapshot["sqlite"].items():
            if item.get("quick_check") != "ok":
                raise UpdaterV2Error(f"a1_sqlite_unhealthy:{name}")
        for label, item in snapshot["ha_storage"].items():
            if item.get("present") is not True:
                raise UpdaterV2Error(f"a1_ha_storage_missing:{label}")
        tls = snapshot["trust"]["tls_semantics"]
        if (
            tls.get("chain_valid") is not True
            or tls.get("hostname_and_validity_valid") is not True
        ):
            raise UpdaterV2Error("a1_broker_tls_semantics_invalid")

    def validate_post(
        self,
        component: str,
        before: dict[str, Any],
        after: dict[str, Any],
    ) -> None:
        self.validate_pre(component, after)

        for name, baseline in before["persistent_paths"].items():
            current = after["persistent_paths"].get(name)
            for key in ("uid", "gid", "type"):
                if current.get(key) != baseline.get(key):
                    raise UpdaterV2Error(
                        f"a1_persistent_identity_drift:{name}:{key}"
                    )

        for name, baseline in before["sqlite"].items():
            current = after["sqlite"].get(name)
            if current.get("schema_sha256") != baseline.get("schema_sha256"):
                raise UpdaterV2Error(f"a1_schema_drift:{name}")
            if current.get("user_version") != baseline.get("user_version"):
                raise UpdaterV2Error(f"a1_schema_version_drift:{name}")

        for key in ("fc4_ca_sha256", "system_ca_sha256"):
            if after["trust"].get(key) != before["trust"].get(key):
                raise UpdaterV2Error(f"a1_trust_anchor_drift:{key}")

        if after["dynsec_top_level_keys_sha256"] != before[
            "dynsec_top_level_keys_sha256"
        ]:
            raise UpdaterV2Error("a1_dynsec_schema_drift")

        if after["mqtt_identity"] != before["mqtt_identity"]:
            raise UpdaterV2Error("a1_mqtt_identity_drift")

        for label, baseline in before["ha_storage"].items():
            current = after["ha_storage"].get(label)
            if current.get("version") != baseline.get("version"):
                raise UpdaterV2Error(
                    f"a1_ha_storage_version_drift:{label}"
                )

        # IMAGE_ONLY_V1 forbids configuration/custom-component migration.
        if after["fixed_config"] != before["fixed_config"]:
            raise UpdaterV2Error("a1_image_only_config_drift")
