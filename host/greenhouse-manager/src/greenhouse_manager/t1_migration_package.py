from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import secrets
import sys
import tarfile
import tempfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO

from .dynsec_api import (
    baseline_commands,
    create_client_command,
    create_role_command,
    legacy_anonymous_shadow_commands,
)
from .dynsec_plan import (
    NodeCredentials,
    NodeProvisioningPlan,
    build_node_provisioning_plan,
    generate_node_credentials,
)
from .service_identity_plan import (
    ServiceCredentials,
    ServiceIdentityPlan,
    build_service_identity_plan,
    generate_service_credentials,
)
from .t1_backup import BackupError, verify_backup

MANIFEST_NAME = "manifest.json"
PACKAGE_SCHEMA = "gh.m2.t1-auth-migration/1"
REPORT_SCHEMA = "gh.m2.t1-auth-migration-report/1"
_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{4,32}$")

IdentityPlan = NodeProvisioningPlan | ServiceIdentityPlan
IdentityCredentials = NodeCredentials | ServiceCredentials


class MigrationPackageError(RuntimeError):
    pass


def _private_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.stat().st_mode & 0o077:
        raise MigrationPackageError(
            "migration package directory must not be accessible by group or other"
        )


def _sha256_stream(stream: BinaryIO) -> str:
    digest = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(chunk)
    return digest.hexdigest()


def _sha256_path(path: Path) -> str:
    with path.open("rb") as stream:
        return _sha256_stream(stream)


def _safe_member_name(name: str) -> bool:
    path = PurePosixPath(name)
    return not path.is_absolute() and ".." not in path.parts


def _tar_filter(info: tarfile.TarInfo) -> tarfile.TarInfo:
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.mode = 0o600
    return info


def _json_text(document: Any) -> str:
    return json.dumps(
        document,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ) + "\n"


def _write_private_file(
    root: Path,
    relative: str,
    payload: str,
    *,
    contains_secret: bool,
    records: list[dict[str, Any]],
) -> Path:
    if not _safe_member_name(relative):
        raise MigrationPackageError("migration package file path is unsafe")
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    target.write_text(payload, encoding="utf-8")
    target.chmod(0o600)
    records.append(
        {
            "path": relative,
            "size": target.stat().st_size,
            "sha256": _sha256_path(target),
            "mode": 0o600,
            "contains_secret": contains_secret,
        }
    )
    return target


def _new_password(random_bytes: Callable[[int], bytes]) -> str:
    material = random_bytes(32)
    if len(material) != 32:
        raise MigrationPackageError("password generator must return exactly 32 bytes")
    return base64.urlsafe_b64encode(material).rstrip(b"=").decode("ascii")


def _identity_record(label: str, plan: IdentityPlan) -> dict[str, Any]:
    record: dict[str, Any] = {
        "label": label,
        "username": plan.username,
        "client_id": plan.client_id,
        "role": plan.role_name,
        "generation": plan.generation,
    }
    if isinstance(plan, NodeProvisioningPlan):
        record["kind"] = "node"
        record["node_id"] = plan.node_id
    else:
        record["kind"] = "service"
        record["service"] = plan.service
    return record


def _client_config(
    *,
    username: str,
    password: str,
    client_id: str,
    host: str = "127.0.0.1",
) -> str:
    return (
        f"-h {host}\n"
        f"-u {username}\n"
        f"-P {password}\n"
        f"-i {client_id}\n"
        "-V 5\n"
    )


def _build_material(
    *,
    system_id: str,
    node_id: str,
    generation: int,
    random_bytes: Callable[[int], bytes],
) -> tuple[
    list[tuple[str, IdentityPlan, IdentityCredentials]],
    str,
]:
    node_plan = build_node_provisioning_plan(
        system_id=system_id,
        node_id=node_id,
        generation=generation,
    )
    service_plans = {
        service: build_service_identity_plan(
            system_id=system_id,
            service=service,  # type: ignore[arg-type]
            generation=generation,
        )
        for service in ("provisioning", "manager", "homeassistant")
    }
    node_credentials = generate_node_credentials(
        node_plan,
        random_bytes=random_bytes,
    )
    service_credentials = {
        service: generate_service_credentials(plan, random_bytes=random_bytes)
        for service, plan in service_plans.items()
    }
    identities: list[tuple[str, IdentityPlan, IdentityCredentials]] = [
        (
            "provisioning",
            service_plans["provisioning"],
            service_credentials["provisioning"],
        ),
        ("manager", service_plans["manager"], service_credentials["manager"]),
        (
            "homeassistant",
            service_plans["homeassistant"],
            service_credentials["homeassistant"],
        ),
        ("node", node_plan, node_credentials),
    ]
    bootstrap_password = _new_password(random_bytes)
    passwords = [credentials.password for _label, _plan, credentials in identities]
    passwords.append(bootstrap_password)
    if len(set(passwords)) != len(passwords):
        raise MigrationPackageError("generated migration passwords must be unique")
    return identities, bootstrap_password


def _migration_steps() -> list[dict[str, Any]]:
    return [
        {
            "order": 1,
            "stage": "install_dynamic_security_candidate",
            "automatic": False,
            "requires_explicit_gate": True,
            "preserve_anonymous": True,
        },
        {
            "order": 2,
            "stage": "provision_service_and_node_identities",
            "automatic": False,
            "requires_explicit_gate": True,
        },
        {
            "order": 3,
            "stage": "verify_provisioning_identity_then_remove_bootstrap_admin",
            "automatic": False,
            "requires_explicit_gate": True,
        },
        {
            "order": 4,
            "stage": "migrate_greenhouse_manager",
            "automatic": False,
            "requires_explicit_gate": True,
        },
        {
            "order": 5,
            "stage": "migrate_home_assistant_mqtt_entry",
            "automatic": False,
            "requires_explicit_gate": True,
        },
        {
            "order": 6,
            "stage": "migrate_node_credentials",
            "automatic": False,
            "requires_explicit_gate": True,
        },
        {
            "order": 7,
            "stage": "observe_authenticated_stability_and_rollback_readiness",
            "automatic": False,
            "requires_explicit_gate": True,
        },
        {
            "order": 8,
            "stage": "close_anonymous_access",
            "automatic": False,
            "requires_explicit_gate": True,
            "blocked_until_all_authenticated": True,
        },
    ]


def create_migration_package(
    rollback_archive: str | Path,
    output_directory: str | Path,
    *,
    system_id: str = "greenhouse",
    node_id: str = "gh-n1-a9f2f8",
    generation: int = 1,
    now: datetime | None = None,
    random_bytes: Callable[[int], bytes] = secrets.token_bytes,
    token_factory: Callable[[], str] | None = None,
) -> Path:
    archive_path = Path(rollback_archive).expanduser().resolve()
    output = Path(output_directory).expanduser().resolve()
    _private_directory(output)
    try:
        rollback_manifest = verify_backup(archive_path)
    except (OSError, BackupError) as error:
        raise MigrationPackageError("verified rollback archive is required") from error

    token = token_factory() if token_factory else secrets.token_hex(4)
    if _TOKEN_PATTERN.fullmatch(token) is None:
        raise MigrationPackageError("package token contains unsupported characters")
    observed_at = (now or datetime.now(UTC)).astimezone(UTC)
    filename = (
        "greenhouse-t1-auth-migration-"
        + observed_at.strftime("%Y%m%dT%H%M%SZ")
        + "-"
        + token
        + ".tar.gz"
    )
    destination = output / filename
    identities, bootstrap_password = _build_material(
        system_id=system_id,
        node_id=node_id,
        generation=generation,
        random_bytes=random_bytes,
    )
    identity_by_label = {
        label: (plan, credentials) for label, plan, credentials in identities
    }

    with tempfile.TemporaryDirectory(prefix=".gh-auth-migration-", dir=output) as temporary:
        staging = Path(temporary)
        staging.chmod(0o700)
        records: list[dict[str, Any]] = []

        commands: list[dict[str, Any]] = [
            *baseline_commands(identities[0][1]),
            *legacy_anonymous_shadow_commands(),
        ]
        for _label, plan, credentials in identities:
            commands.append(create_role_command(plan))
            commands.append(create_client_command(plan, credentials))

        _write_private_file(
            staging,
            "broker/dynsec-request.json",
            _json_text({"commands": commands}),
            contains_secret=True,
            records=records,
        )
        _write_private_file(
            staging,
            "broker/mosquitto-plugin.conf",
            "# M2 authenticated migration candidate; do not apply automatically\n"
            "plugin /usr/lib/mosquitto_dynamic_security.so\n"
            "plugin_opt_config_file /mosquitto/data/dynamic-security.json\n"
            "plugin_opt_password_init_file /mosquitto/config/dynsec-password-init\n",
            contains_secret=False,
            records=records,
        )
        _write_private_file(
            staging,
            "bootstrap/dynsec-password-init",
            bootstrap_password + "\n",
            contains_secret=True,
            records=records,
        )
        _write_private_file(
            staging,
            "bootstrap/admin-client.conf",
            _client_config(
                username="admin",
                password=bootstrap_password,
                client_id="gh-m2-bootstrap-admin",
            ),
            contains_secret=True,
            records=records,
        )

        provisioning_plan, provisioning_credentials = identity_by_label["provisioning"]
        _write_private_file(
            staging,
            "provisioning/mosquitto-client.conf",
            _client_config(
                username=provisioning_credentials.username,
                password=provisioning_credentials.password,
                client_id=provisioning_credentials.client_id,
            ),
            contains_secret=True,
            records=records,
        )
        _write_private_file(
            staging,
            "provisioning/identity.json",
            _json_text(_identity_record("provisioning", provisioning_plan)),
            contains_secret=False,
            records=records,
        )

        manager_plan, manager_credentials = identity_by_label["manager"]
        _write_private_file(
            staging,
            "manager/manager.env",
            f"GH_MQTT_USERNAME={manager_credentials.username}\n"
            "GH_MQTT_PASSWORD_FILE=/run/secrets/gh_manager_mqtt_password\n"
            f"GH_MQTT_CLIENT_ID={manager_credentials.client_id}\n",
            contains_secret=False,
            records=records,
        )
        _write_private_file(
            staging,
            "manager/password",
            manager_credentials.password + "\n",
            contains_secret=True,
            records=records,
        )
        _write_private_file(
            staging,
            "manager/compose-secret-fragment.yaml",
            "services:\n"
            "  greenhouse-manager:\n"
            "    environment:\n"
            f"      GH_MQTT_USERNAME: {manager_credentials.username}\n"
            "      GH_MQTT_PASSWORD_FILE: /run/secrets/gh_manager_mqtt_password\n"
            f"      GH_MQTT_CLIENT_ID: {manager_credentials.client_id}\n"
            "    volumes:\n"
            "      - type: bind\n"
            "        source: /opt/greenhouse-secrets/mqtt/manager/password\n"
            "        target: /run/secrets/gh_manager_mqtt_password\n"
            "        read_only: true\n",
            contains_secret=False,
            records=records,
        )

        ha_plan, ha_credentials = identity_by_label["homeassistant"]
        _write_private_file(
            staging,
            "homeassistant/mqtt-update.json",
            _json_text(
                {
                    "schema": "gh.m2.homeassistant-mqtt-update/1",
                    "automatic_apply": False,
                    "operation": "update_existing_mqtt_config_entry",
                    "broker": "mosquitto",
                    "port": 1883,
                    "username": ha_credentials.username,
                    "password": ha_credentials.password,
                    "required_client_id": ha_credentials.client_id,
                    "generation": ha_credentials.generation,
                    "preserve_discovery": True,
                }
            ),
            contains_secret=True,
            records=records,
        )
        _write_private_file(
            staging,
            "homeassistant/identity.json",
            _json_text(_identity_record("homeassistant", ha_plan)),
            contains_secret=False,
            records=records,
        )

        node_plan, node_credentials = identity_by_label["node"]
        _write_private_file(
            staging,
            f"node/{node_id}/mqtt-credentials.json",
            _json_text(
                {
                    "schema": "gh.m2.node-mqtt-credentials/1",
                    "automatic_apply": False,
                    "node_id": node_id,
                    "system_id": system_id,
                    "username": node_credentials.username,
                    "password": node_credentials.password,
                    "client_id": node_credentials.client_id,
                    "generation": node_credentials.generation,
                }
            ),
            contains_secret=True,
            records=records,
        )
        _write_private_file(
            staging,
            f"node/{node_id}/identity.json",
            _json_text(_identity_record("node", node_plan)),
            contains_secret=False,
            records=records,
        )

        _write_private_file(
            staging,
            "apply-plan.json",
            _json_text(
                {
                    "schema": "gh.m2.t1-auth-apply-plan/1",
                    "apply_enabled": False,
                    "current_services_modified": False,
                    "steps": _migration_steps(),
                }
            ),
            contains_secret=False,
            records=records,
        )
        _write_private_file(
            staging,
            "rollback/plan.json",
            _json_text(
                {
                    "schema": "gh.m2.t1-auth-rollback-plan/1",
                    "automatic_restore": False,
                    "source_archive": archive_path.name,
                    "source_archive_sha256": _sha256_path(archive_path),
                    "services": ["mosquitto", "greenhouse-manager", "homeassistant"],
                    "required_precondition": "stop migration and preserve current rollback archive",
                }
            ),
            contains_secret=False,
            records=records,
        )
        _write_private_file(
            staging,
            "README.txt",
            "This archive contains live MQTT credentials and must remain local to the T1.\n"
            "Do not commit, upload, email, print, or copy it to Home Assistant storage.\n"
            "Generation does not modify any running service. apply-plan.json is disabled.\n"
            "The bootstrap admin must be removed only after the provisioning identity is verified.\n"
            "Anonymous access must remain enabled until manager, Home Assistant and the node "
            "are authenticated.\n",
            contains_secret=False,
            records=records,
        )

        identity_records = [
            _identity_record(label, plan) for label, plan, _credentials in identities
        ]
        manifest = {
            "schema": PACKAGE_SCHEMA,
            "created_at": observed_at.isoformat(timespec="milliseconds").replace(
                "+00:00", "Z"
            ),
            "classification": "secret-local-migration",
            "portable_off_host": False,
            "apply_enabled": False,
            "current_services_modified": False,
            "source_rollback": {
                "archive": archive_path.name,
                "sha256": _sha256_path(archive_path),
                "schema": rollback_manifest["schema"],
                "mosquitto_image_id": rollback_manifest["sources"]["mosquitto"][
                    "image_id"
                ],
            },
            "system_id": system_id,
            "node_id": node_id,
            "generation": generation,
            "identities": identity_records,
            "host_secret_layout": {
                "root": "/opt/greenhouse-secrets/mqtt",
                "directory_mode": "0700",
                "file_mode": "0600",
                "manager_password": "manager/password",
            },
            "files": records,
        }
        manifest_path = staging / MANIFEST_NAME
        manifest_path.write_text(_json_text(manifest), encoding="utf-8")
        manifest_path.chmod(0o600)

        file_descriptor = os.open(
            destination,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        try:
            with (
                os.fdopen(file_descriptor, "wb") as raw,
                tarfile.open(fileobj=raw, mode="w:gz") as package,
            ):
                package.add(
                    manifest_path,
                    arcname=MANIFEST_NAME,
                    recursive=False,
                    filter=_tar_filter,
                )
                for record in records:
                    path = staging / record["path"]
                    package.add(
                        path,
                        arcname=record["path"],
                        recursive=False,
                        filter=_tar_filter,
                    )
        except Exception:
            destination.unlink(missing_ok=True)
            raise

    verify_migration_package(destination)
    return destination


def verify_migration_package(path: str | Path) -> dict[str, Any]:
    archive_path = Path(path)
    if archive_path.stat().st_mode & 0o077:
        raise MigrationPackageError("migration package permissions are not private")
    with tarfile.open(archive_path, mode="r:gz") as package:
        members = package.getmembers()
        if any(
            not member.isfile() or not _safe_member_name(member.name)
            for member in members
        ):
            raise MigrationPackageError("migration package contains an unsafe member")
        by_name = {member.name: member for member in members}
        manifest_member = by_name.get(MANIFEST_NAME)
        if manifest_member is None:
            raise MigrationPackageError("migration package manifest is missing")
        stream = package.extractfile(manifest_member)
        if stream is None:
            raise MigrationPackageError("migration package manifest cannot be read")
        try:
            manifest = json.load(stream)
        except json.JSONDecodeError as error:
            raise MigrationPackageError("migration package manifest is invalid") from error
        if manifest.get("schema") != PACKAGE_SCHEMA:
            raise MigrationPackageError("migration package schema is unsupported")
        if manifest.get("apply_enabled") is not False:
            raise MigrationPackageError("migration package must be disabled by default")
        if manifest.get("current_services_modified") is not False:
            raise MigrationPackageError("migration package cannot report service modification")
        expected = {record["path"]: record for record in manifest.get("files", [])}
        if set(by_name) != set(expected) | {MANIFEST_NAME}:
            raise MigrationPackageError("migration package inventory does not match manifest")
        for name, record in expected.items():
            member = by_name[name]
            if member.mode & 0o777 != 0o600 or record.get("mode") != 0o600:
                raise MigrationPackageError("migration package file permissions are unsafe")
            member_stream = package.extractfile(member)
            if member_stream is None:
                raise MigrationPackageError("migration package file cannot be read")
            if _sha256_stream(member_stream) != record.get("sha256"):
                raise MigrationPackageError("migration package checksum verification failed")
            if member.size != record.get("size"):
                raise MigrationPackageError("migration package size verification failed")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate a disabled, private T1 authenticated MQTT migration package."
    )
    parser.add_argument("rollback_archive")
    parser.add_argument("output_directory")
    parser.add_argument("--system-id", default="greenhouse")
    parser.add_argument("--node-id", default="gh-n1-a9f2f8")
    parser.add_argument("--generation", type=int, default=1)
    arguments = parser.parse_args(argv)
    try:
        package = create_migration_package(
            arguments.rollback_archive,
            arguments.output_directory,
            system_id=arguments.system_id,
            node_id=arguments.node_id,
            generation=arguments.generation,
        )
        manifest = verify_migration_package(package)
    except (MigrationPackageError, OSError, ValueError) as error:
        print(f"T1 authenticated migration package failed: {error}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "schema": REPORT_SCHEMA,
                "package": package.name,
                "source_archive": manifest["source_rollback"]["archive"],
                "apply_enabled": False,
                "current_services_modified": False,
            },
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
