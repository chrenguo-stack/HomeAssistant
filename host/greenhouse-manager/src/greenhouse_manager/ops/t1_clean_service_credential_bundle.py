from __future__ import annotations

import hashlib
import json
import os
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

from greenhouse_manager.runtime.service_identity_plan import (
    ServiceCredentials,
    ServiceIdentityPlan,
    build_service_identity_plan,
    generate_service_credentials,
)

SCHEMA = "gh.n3w.t1-clean-service-credential-bundle/1"
HA_BOOTSTRAP_SCHEMA = "gh.n3w.t1-clean-homeassistant-mqtt-bootstrap/1"
_SERVICES = ("manager", "provisioning", "homeassistant")
_MANAGER_TARGET = "/run/secrets/gh_manager_mqtt_password"
_PROVISIONING_TARGET = "/run/secrets/gh_n3w_provisioning_mqtt_password"
_HA_PASSWORD_TARGET = "/run/secrets/gh_homeassistant_mqtt_password"
_HA_BOOTSTRAP_TARGET = "/run/n3w/ha-mqtt-bootstrap.json"


class CleanServiceCredentialBundleError(RuntimeError):
    pass


def _json_text(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ) + "\n"


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _path_contains_symlink(path: Path) -> bool:
    current = path
    while True:
        if current.is_symlink():
            return True
        if current == current.parent:
            return False
        current = current.parent


def _make_private_directory(path: Path) -> None:
    path.mkdir(mode=0o700)
    os.chmod(path, 0o700)
    if path.is_symlink() or path.stat().st_mode & 0o777 != 0o700:
        raise CleanServiceCredentialBundleError("private directory creation failed")


def _write_private(path: Path, value: str) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
    except OSError as error:
        raise CleanServiceCredentialBundleError(
            "private file creation failed"
        ) from error
    try:
        payload = value.encode("utf-8")
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        path.unlink(missing_ok=True)
        raise
    os.chmod(path, 0o600)
    if path.is_symlink() or path.stat().st_mode & 0o777 != 0o600:
        raise CleanServiceCredentialBundleError("private file mode invalid")


def _identity_record(
    plan: ServiceIdentityPlan,
) -> dict[str, object]:
    return {
        "service": plan.service,
        "system_id": plan.system_id,
        "generation": plan.generation,
        "username": plan.username,
        "client_id": plan.client_id,
        "role_name": plan.role_name,
        "acl_count": len(plan.acls),
        "defaults": {
            "publishClientSend": plan.defaults.publish_client_send,
            "publishClientReceive": plan.defaults.publish_client_receive,
            "subscribe": plan.defaults.subscribe,
            "unsubscribe": plan.defaults.unsubscribe,
        },
    }


def _file_record(
    path: Path,
    root: Path,
    *,
    contains_secret: bool,
) -> dict[str, object]:
    return {
        "path": path.relative_to(root).as_posix(),
        "mode": path.stat().st_mode & 0o777,
        "size": path.stat().st_size,
        "sha256": _sha256_path(path),
        "contains_secret": contains_secret,
    }


def _manager_environment(
    manager: ServiceIdentityPlan,
    provisioning: ServiceIdentityPlan,
) -> str:
    return (
        f"GH_MQTT_USERNAME={manager.username}\n"
        f"GH_MQTT_PASSWORD_FILE={_MANAGER_TARGET}\n"
        f"GH_MQTT_CLIENT_ID={manager.client_id}\n"
        f"GH_N3W_PROVISIONING_USERNAME={provisioning.username}\n"
        f"GH_N3W_PROVISIONING_PASSWORD_FILE={_PROVISIONING_TARGET}\n"
        f"GH_N3W_PROVISIONING_CLIENT_ID={provisioning.client_id}\n"
    )


def _manager_compose_fragment(
    root: Path,
    manager: ServiceIdentityPlan,
    provisioning: ServiceIdentityPlan,
) -> str:
    manager_source = (root / "manager/password").as_posix()
    provisioning_source = (root / "provisioning/password").as_posix()
    return (
        "services:\n"
        "  greenhouse-manager:\n"
        "    environment:\n"
        f"      GH_MQTT_USERNAME: {manager.username}\n"
        f"      GH_MQTT_PASSWORD_FILE: {_MANAGER_TARGET}\n"
        f"      GH_MQTT_CLIENT_ID: {manager.client_id}\n"
        f"      GH_N3W_PROVISIONING_USERNAME: {provisioning.username}\n"
        f"      GH_N3W_PROVISIONING_PASSWORD_FILE: {_PROVISIONING_TARGET}\n"
        f"      GH_N3W_PROVISIONING_CLIENT_ID: {provisioning.client_id}\n"
        "    volumes:\n"
        "      - type: bind\n"
        f"        source: {manager_source}\n"
        f"        target: {_MANAGER_TARGET}\n"
        "        read_only: true\n"
        "      - type: bind\n"
        f"        source: {provisioning_source}\n"
        f"        target: {_PROVISIONING_TARGET}\n"
        "        read_only: true\n"
    )


def _homeassistant_bootstrap(
    plan: ServiceIdentityPlan,
) -> dict[str, object]:
    return {
        "schema": HA_BOOTSTRAP_SCHEMA,
        "service": "homeassistant",
        "broker": "127.0.0.1",
        "port": 1883,
        "protocol": "5",
        "username": plan.username,
        "client_id": plan.client_id,
        "generation": plan.generation,
        "password_file": _HA_PASSWORD_TARGET,
        "official_config_flow_only": True,
        "direct_storage_edit_forbidden": True,
        "automatic_apply": True,
        "operator_plaintext_copy_required": False,
        "runtime_verified": False,
    }


def _homeassistant_compose_fragment(
    root: Path,
) -> str:
    password_source = (
        root / "homeassistant/password"
    ).as_posix()
    bootstrap_source = (
        root / "homeassistant/mqtt-bootstrap.json"
    ).as_posix()
    return (
        "services:\n"
        "  homeassistant:\n"
        "    volumes:\n"
        "      - type: bind\n"
        f"        source: {password_source}\n"
        f"        target: {_HA_PASSWORD_TARGET}\n"
        "        read_only: true\n"
        "      - type: bind\n"
        f"        source: {bootstrap_source}\n"
        f"        target: {_HA_BOOTSTRAP_TARGET}\n"
        "        read_only: true\n"
    )


def create_clean_service_credential_bundle(
    destination: str | Path,
    *,
    system_id: str,
    generation: int = 1,
    random_bytes: Callable[[int], bytes] | None = None,
) -> dict[str, object]:
    requested = Path(destination).expanduser()
    if requested.exists() or requested.is_symlink():
        raise CleanServiceCredentialBundleError(
            "credential bundle destination already exists"
        )
    parent = requested.parent
    if (
        not parent.is_dir()
        or _path_contains_symlink(parent)
    ):
        raise CleanServiceCredentialBundleError(
            "credential bundle parent is unavailable"
        )
    root = parent.resolve() / requested.name

    random_source = random_bytes
    plans: dict[str, ServiceIdentityPlan] = {}
    credentials: dict[str, ServiceCredentials] = {}

    try:
        _make_private_directory(root)
        for service in _SERVICES:
            service_dir = root / service
            _make_private_directory(service_dir)
            plan = build_service_identity_plan(
                system_id=system_id,
                service=service,
                generation=generation,
            )
            credential = generate_service_credentials(
                plan,
                **(
                    {"random_bytes": random_source}
                    if random_source is not None
                    else {}
                ),
            )
            plans[service] = plan
            credentials[service] = credential
            _write_private(
                service_dir / "password",
                credential.password + "\n",
            )
            _write_private(
                service_dir / "identity.json",
                _json_text(_identity_record(plan)),
            )

        passwords = {
            credentials[service].password
            for service in _SERVICES
        }
        if len(passwords) != len(_SERVICES):
            raise CleanServiceCredentialBundleError(
                "service credentials are not independent"
            )

        _write_private(
            root / "manager/runtime.env",
            _manager_environment(
                plans["manager"],
                plans["provisioning"],
            ),
        )
        _write_private(
            root / "manager/compose-secret-fragment.yaml",
            _manager_compose_fragment(
                root,
                plans["manager"],
                plans["provisioning"],
            ),
        )
        _write_private(
            root / "homeassistant/mqtt-bootstrap.json",
            _json_text(
                _homeassistant_bootstrap(
                    plans["homeassistant"],
                )
            ),
        )
        _write_private(
            root / "homeassistant/compose-secret-fragment.yaml",
            _homeassistant_compose_fragment(root),
        )

        records: list[dict[str, object]] = []
        for path in sorted(
            item
            for item in root.rglob("*")
            if item.is_file()
        ):
            records.append(
                _file_record(
                    path,
                    root,
                    contains_secret=(
                        path.name == "password"
                    ),
                )
            )

        manifest = {
            "schema": SCHEMA,
            "system_id": system_id,
            "generation": generation,
            "service_count": 3,
            "service_names": list(_SERVICES),
            "node_credential_count": 0,
            "node_precreation_forbidden": True,
            "manager_runtime": {
                "consumer": "greenhouse-manager",
                "runtime_uid_gid_binding_required": True,
                "manager_password_target": _MANAGER_TARGET,
                "provisioning_password_target": _PROVISIONING_TARGET,
                "password_mounts_read_only": True,
                "inline_password_environment_forbidden": True,
            },
            "homeassistant": {
                "consumer": "n3w_mqtt_bootstrap_to_homeassistant_mqtt",
                "official_config_flow_only": True,
                "direct_storage_edit_forbidden": True,
                "automatic_apply": True,
                "password_target": _HA_PASSWORD_TARGET,
                "bootstrap_target": _HA_BOOTSTRAP_TARGET,
                "fresh_product_consumer_source_defined": True,
                "runtime_verified": False,
            },
            "files": records,
            "secret_values_included": False,
        }
        _write_private(
            root / "manifest.json",
            _json_text(manifest),
        )
        verify_clean_service_credential_bundle(root)
        return manifest
    except Exception:
        shutil.rmtree(root, ignore_errors=True)
        raise


def verify_clean_service_credential_bundle(
    directory: str | Path,
) -> dict[str, object]:
    requested = Path(directory).expanduser()
    if _path_contains_symlink(requested):
        raise CleanServiceCredentialBundleError(
            "credential bundle root is unsafe"
        )
    root = requested.resolve()
    if (
        not root.is_dir()
        or root.stat().st_mode & 0o777 != 0o700
    ):
        raise CleanServiceCredentialBundleError(
            "credential bundle root is unsafe"
        )

    expected = {
        "manager/password",
        "manager/identity.json",
        "manager/runtime.env",
        "manager/compose-secret-fragment.yaml",
        "provisioning/password",
        "provisioning/identity.json",
        "homeassistant/password",
        "homeassistant/identity.json",
        "homeassistant/mqtt-bootstrap.json",
        "homeassistant/compose-secret-fragment.yaml",
        "manifest.json",
    }
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    }
    if actual != expected:
        raise CleanServiceCredentialBundleError(
            "credential bundle inventory is invalid"
        )

    for directory_name in _SERVICES:
        service_dir = root / directory_name
        if (
            not service_dir.is_dir()
            or service_dir.is_symlink()
            or service_dir.stat().st_mode & 0o777 != 0o700
        ):
            raise CleanServiceCredentialBundleError(
                "service credential directory is unsafe"
            )

    for relative in expected:
        path = root / relative
        if (
            not path.is_file()
            or path.is_symlink()
            or path.stat().st_mode & 0o777 != 0o600
        ):
            raise CleanServiceCredentialBundleError(
                "credential bundle file is unsafe"
            )

    try:
        manifest = json.loads(
            (root / "manifest.json").read_text(
                encoding="utf-8"
            )
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise CleanServiceCredentialBundleError(
            "credential bundle manifest is invalid"
        ) from error

    if (
        not isinstance(manifest, dict)
        or manifest.get("schema") != SCHEMA
        or manifest.get("service_count") != 3
        or manifest.get("service_names") != list(_SERVICES)
        or manifest.get("node_credential_count") != 0
        or manifest.get("node_precreation_forbidden") is not True
        or manifest.get("secret_values_included") is not False
    ):
        raise CleanServiceCredentialBundleError(
            "credential bundle manifest contract is invalid"
        )

    records = manifest.get("files")
    if not isinstance(records, list):
        raise CleanServiceCredentialBundleError(
            "credential bundle manifest inventory is invalid"
        )
    expected_records = expected - {"manifest.json"}
    record_paths: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            raise CleanServiceCredentialBundleError(
                "credential bundle manifest inventory is invalid"
            )
        relative = record.get("path")
        if (
            not isinstance(relative, str)
            or relative not in expected_records
            or relative in record_paths
        ):
            raise CleanServiceCredentialBundleError(
                "credential bundle manifest inventory is invalid"
            )
        target = root / relative
        if (
            record.get("mode") != 0o600
            or record.get("size") != target.stat().st_size
            or record.get("sha256") != _sha256_path(target)
            or not isinstance(record.get("contains_secret"), bool)
        ):
            raise CleanServiceCredentialBundleError(
                "credential bundle manifest file binding is invalid"
            )
        record_paths.add(relative)
    if record_paths != expected_records:
        raise CleanServiceCredentialBundleError(
            "credential bundle manifest inventory is incomplete"
        )
    secret_paths = {
        str(record["path"])
        for record in records
        if record.get("contains_secret") is True
    }
    if secret_paths != {
        "manager/password",
        "provisioning/password",
        "homeassistant/password",
    }:
        raise CleanServiceCredentialBundleError(
            "credential bundle secret inventory is invalid"
        )

    homeassistant = manifest.get("homeassistant")
    if (
        not isinstance(homeassistant, dict)
        or homeassistant.get("official_config_flow_only") is not True
        or homeassistant.get("direct_storage_edit_forbidden") is not True
        or homeassistant.get("automatic_apply") is not True
        or homeassistant.get("fresh_product_consumer_source_defined") is not True
        or homeassistant.get("runtime_verified") is not False
        or homeassistant.get("password_target") != _HA_PASSWORD_TARGET
        or homeassistant.get("bootstrap_target") != _HA_BOOTSTRAP_TARGET
    ):
        raise CleanServiceCredentialBundleError(
            "Home Assistant bootstrap contract is invalid"
        )

    passwords = {
        (root / f"{service}/password").read_text(
            encoding="utf-8"
        ).rstrip("\r\n")
        for service in _SERVICES
    }
    if len(passwords) != len(_SERVICES) or any(
        not password
        for password in passwords
    ):
        raise CleanServiceCredentialBundleError(
            "service password set is invalid"
        )

    runtime_env = (
        root / "manager/runtime.env"
    ).read_text(encoding="utf-8")
    if (
        f"GH_MQTT_PASSWORD_FILE={_MANAGER_TARGET}"
        not in runtime_env
        or (
            "GH_N3W_PROVISIONING_PASSWORD_FILE="
            f"{_PROVISIONING_TARGET}"
        )
        not in runtime_env
        or "GH_MQTT_PASSWORD=" in runtime_env
    ):
        raise CleanServiceCredentialBundleError(
            "manager runtime password-file contract is invalid"
        )

    compose = (
        root / "manager/compose-secret-fragment.yaml"
    ).read_text(encoding="utf-8")
    if (
        compose.count("read_only: true") != 2
        or _MANAGER_TARGET not in compose
        or _PROVISIONING_TARGET not in compose
    ):
        raise CleanServiceCredentialBundleError(
            "manager Compose secret contract is invalid"
        )

    try:
        ha_bootstrap = json.loads(
            (
                root
                / "homeassistant/mqtt-bootstrap.json"
            ).read_text(encoding="utf-8")
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise CleanServiceCredentialBundleError(
            "Home Assistant bootstrap metadata is invalid"
        ) from error
    if (
        not isinstance(ha_bootstrap, dict)
        or ha_bootstrap.get("schema") != HA_BOOTSTRAP_SCHEMA
        or ha_bootstrap.get("broker") != "127.0.0.1"
        or ha_bootstrap.get("port") != 1883
        or ha_bootstrap.get("protocol") != "5"
        or ha_bootstrap.get("password_file") != _HA_PASSWORD_TARGET
        or ha_bootstrap.get("automatic_apply") is not True
        or ha_bootstrap.get("direct_storage_edit_forbidden") is not True
        or ha_bootstrap.get("runtime_verified") is not False
        or "password" in ha_bootstrap
    ):
        raise CleanServiceCredentialBundleError(
            "Home Assistant bootstrap metadata is unsafe"
        )

    ha_compose = (
        root / "homeassistant/compose-secret-fragment.yaml"
    ).read_text(encoding="utf-8")
    if (
        ha_compose.count("read_only: true") != 2
        or _HA_PASSWORD_TARGET not in ha_compose
        or _HA_BOOTSTRAP_TARGET not in ha_compose
    ):
        raise CleanServiceCredentialBundleError(
            "Home Assistant Compose secret contract is invalid"
        )

    return manifest
