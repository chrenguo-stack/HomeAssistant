from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import shutil
import sys
import tarfile
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .dynsec_api import CONTROL_TOPIC, DynsecError
from .dynsec_plan import NodeCredentials
from .service_identity_plan import ServiceCredentials
from .t1_backup import BackupError, _extract_verified
from .t1_migration_package import (
    MigrationPackageError,
    verify_migration_package,
)
from .t1_shadow import (
    CommandRunner,
    ShadowError,
    SubprocessRunner,
    _candidate_diagnostic,
    _mount,
    _prepare_snapshot_directories,
    _require_success,
    _wait_for_file,
    prepare_shadow_config,
)
from .t1_shadow_services import (
    MosquittoRRTransport,
    _assert_control_denied,
    _assert_dynsec_object_missing,
    _assert_publish_allowed,
    _assert_publish_denied,
    _assert_subscription_denied,
    _assert_wrong_client_id_rejected,
    _copy_client_config,
    _subscribe_once,
)

PACKAGE_REHEARSAL_SCHEMA = "gh.m2.t1-auth-migration-rehearsal/1"


@dataclass(frozen=True, slots=True)
class PackageMaterial:
    system_id: str
    node_id: str
    generation: int
    node_credentials: NodeCredentials
    service_credentials: dict[str, ServiceCredentials]
    commands: tuple[dict[str, Any], ...]


VerificationExecutor = Callable[
    [
        CommandRunner,
        str,
        Path,
        MosquittoRRTransport,
        PackageMaterial,
        str,
    ],
    dict[str, bool],
]


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _extract_verified_migration_package(
    path: Path,
    destination: Path,
) -> dict[str, Any]:
    manifest = verify_migration_package(path)
    with tarfile.open(path, mode="r:gz") as package:
        for member in package.getmembers():
            stream = package.extractfile(member)
            if stream is None:
                raise MigrationPackageError(
                    "migration package member cannot be extracted"
                )
            target = destination / member.name
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with target.open("wb") as output:
                shutil.copyfileobj(stream, output)
            target.chmod(member.mode & 0o777)
    return manifest


def _read_json(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise MigrationPackageError(
            f"migration package JSON is invalid: {path.name}"
        ) from error
    if not isinstance(document, dict):
        raise MigrationPackageError(
            f"migration package JSON must be an object: {path.name}"
        )
    return document


def _read_secret(path: Path) -> str:
    try:
        value = path.read_text(encoding="utf-8").rstrip("\r\n")
    except (OSError, UnicodeError) as error:
        raise MigrationPackageError(
            f"migration package secret cannot be read: {path.name}"
        ) from error
    if not value or "\n" in value or "\r" in value or "\x00" in value:
        raise MigrationPackageError(
            f"migration package secret is malformed: {path.name}"
        )
    return value


def _parse_key_value_file(path: Path, separator: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        key, found, value = line.partition(separator)
        if not found or not key or not value or key in values:
            raise MigrationPackageError(
                f"migration package key/value file is invalid: {path.name}"
            )
        values[key] = value
    return values


def _parse_mosquitto_config(path: Path) -> dict[str, str]:
    values = _parse_key_value_file(path, " ")
    required = {"-u", "-P", "-i"}
    if required - values.keys():
        raise MigrationPackageError(
            f"migration package client config is incomplete: {path.name}"
        )
    return values


def _identity_records(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw = manifest.get("identities")
    if not isinstance(raw, list):
        raise MigrationPackageError("migration package identity inventory is missing")
    records: dict[str, dict[str, Any]] = {}
    for item in raw:
        if not isinstance(item, dict):
            raise MigrationPackageError(
                "migration package identity inventory is invalid"
            )
        label = item.get("label")
        if not isinstance(label, str) or label in records:
            raise MigrationPackageError(
                "migration package identity labels are invalid"
            )
        records[label] = item
    if set(records) != {"provisioning", "manager", "homeassistant", "node"}:
        raise MigrationPackageError(
            "migration package identity inventory does not match the frozen profile"
        )
    return records


def _validate_credential_record(
    label: str,
    credential: NodeCredentials | ServiceCredentials,
    records: dict[str, dict[str, Any]],
) -> None:
    record = records[label]
    expected = (
        str(record.get("username")),
        str(record.get("client_id")),
        int(record.get("generation", -1)),
    )
    actual = (
        credential.username,
        credential.client_id,
        credential.generation,
    )
    if actual != expected:
        raise MigrationPackageError(
            f"migration package credential metadata mismatch: {label}"
        )


def _load_package_material(
    package_root: Path,
    manifest: dict[str, Any],
) -> PackageMaterial:
    system_id = str(manifest.get("system_id", ""))
    node_id = str(manifest.get("node_id", ""))
    generation = int(manifest.get("generation", 0))
    if not system_id or not node_id or generation < 1:
        raise MigrationPackageError(
            "migration package identity scope is invalid"
        )
    records = _identity_records(manifest)

    provisioning = _parse_mosquitto_config(
        package_root / "provisioning/mosquitto-client.conf"
    )
    provisioning_credentials = ServiceCredentials(
        username=provisioning["-u"],
        password=provisioning["-P"],
        client_id=provisioning["-i"],
        generation=generation,
    )

    manager_env = _parse_key_value_file(
        package_root / "manager/manager.env",
        "=",
    )
    if (
        manager_env.get("GH_MQTT_PASSWORD_FILE")
        != "/run/secrets/gh_manager_mqtt_password"
    ):
        raise MigrationPackageError(
            "migration package manager password-file contract is invalid"
        )
    manager_credentials = ServiceCredentials(
        username=manager_env.get("GH_MQTT_USERNAME", ""),
        password=_read_secret(package_root / "manager/password"),
        client_id=manager_env.get("GH_MQTT_CLIENT_ID", ""),
        generation=generation,
    )

    homeassistant = _read_json(
        package_root / "homeassistant/mqtt-update.json"
    )
    homeassistant_credentials = ServiceCredentials(
        username=str(homeassistant.get("username", "")),
        password=str(homeassistant.get("password", "")),
        client_id=str(homeassistant.get("required_client_id", "")),
        generation=int(homeassistant.get("generation", 0)),
    )

    node = _read_json(
        package_root / f"node/{node_id}/mqtt-credentials.json"
    )
    if (
        node.get("node_id") != node_id
        or node.get("system_id") != system_id
    ):
        raise MigrationPackageError(
            "migration package node credential scope is invalid"
        )
    node_credentials = NodeCredentials(
        username=str(node.get("username", "")),
        password=str(node.get("password", "")),
        client_id=str(node.get("client_id", "")),
        generation=int(node.get("generation", 0)),
    )

    service_credentials = {
        "provisioning": provisioning_credentials,
        "manager": manager_credentials,
        "homeassistant": homeassistant_credentials,
    }
    for label, credential in (
        ("provisioning", provisioning_credentials),
        ("manager", manager_credentials),
        ("homeassistant", homeassistant_credentials),
        ("node", node_credentials),
    ):
        _validate_credential_record(label, credential, records)
        if not credential.password:
            raise MigrationPackageError(
                f"migration package password is empty: {label}"
            )

    passwords = {
        node_credentials.password,
        *(credential.password for credential in service_credentials.values()),
    }
    if len(passwords) != 4:
        raise MigrationPackageError(
            "migration package identity passwords are not unique"
        )

    request = _read_json(package_root / "broker/dynsec-request.json")
    raw_commands = request.get("commands")
    if not isinstance(raw_commands, list) or not raw_commands:
        raise MigrationPackageError(
            "migration package Dynamic Security request is missing"
        )
    commands: list[dict[str, Any]] = []
    for command in raw_commands:
        if not isinstance(command, dict) or not isinstance(
            command.get("command"), str
        ):
            raise MigrationPackageError(
                "migration package Dynamic Security command is invalid"
            )
        commands.append(command)

    expected_credentials = {
        credential.username: credential
        for credential in (
            provisioning_credentials,
            manager_credentials,
            homeassistant_credentials,
            node_credentials,
        )
    }
    create_clients = {
        str(command.get("username")): command
        for command in commands
        if command.get("command") == "createClient"
    }
    if set(create_clients) != set(expected_credentials):
        raise MigrationPackageError(
            "migration package Dynamic Security clients do not match handoff files"
        )
    for username, credential in expected_credentials.items():
        command = create_clients[username]
        if (
            command.get("password") != credential.password
            or command.get("clientid") != credential.client_id
        ):
            raise MigrationPackageError(
                "migration package Dynamic Security credentials are inconsistent"
            )
        record = records[
            "node"
            if isinstance(credential, NodeCredentials)
            else next(
                label
                for label, service_credential in service_credentials.items()
                if service_credential is credential
            )
        ]
        if command.get("roles") != [
            {"rolename": record.get("role"), "priority": 100}
        ]:
            raise MigrationPackageError(
                "migration package Dynamic Security role binding is inconsistent"
            )

    command_names = [str(command["command"]) for command in commands]
    if "setDefaultACLAccess" not in command_names or "setAnonymousGroup" not in command_names:
        raise MigrationPackageError(
            "migration package Dynamic Security baseline is incomplete"
        )

    return PackageMaterial(
        system_id=system_id,
        node_id=node_id,
        generation=generation,
        node_credentials=node_credentials,
        service_credentials=service_credentials,
        commands=tuple(commands),
    )


def _require_source_binding(
    rollback_path: Path,
    rollback_manifest: dict[str, Any],
    package_manifest: dict[str, Any],
) -> None:
    source = package_manifest.get("source_rollback")
    if not isinstance(source, dict):
        raise MigrationPackageError(
            "migration package rollback binding is missing"
        )
    expected = (
        rollback_path.name,
        _sha256_path(rollback_path),
        rollback_manifest.get("schema"),
        rollback_manifest.get("sources", {})
        .get("mosquitto", {})
        .get("image_id"),
    )
    actual = (
        source.get("archive"),
        source.get("sha256"),
        source.get("schema"),
        source.get("mosquitto_image_id"),
    )
    if actual != expected:
        raise MigrationPackageError(
            "migration package does not match the selected rollback archive"
        )


def _run_package_verification(
    runner: CommandRunner,
    container_id: str,
    staging: Path,
    bootstrap_transport: MosquittoRRTransport,
    material: PackageMaterial,
    expected_retained_topic: str,
) -> dict[str, bool]:
    node_config = _copy_client_config(
        runner,
        container_id,
        staging,
        label="gh-m2-package-node",
        username=material.node_credentials.username,
        password=material.node_credentials.password,
        client_id=material.node_credentials.client_id,
    )
    service_configs = {
        service: _copy_client_config(
            runner,
            container_id,
            staging,
            label=f"gh-m2-package-{service}",
            username=credentials.username,
            password=credentials.password,
            client_id=credentials.client_id,
        )
        for service, credentials in material.service_credentials.items()
    }
    provisioning_transport = MosquittoRRTransport(
        runner,
        container_id,
        service_configs["provisioning"],
    )
    responses = provisioning_transport.execute(({"command": "listClients"},))
    if not responses or responses[0].get("command") != "listClients":
        raise ShadowError(
            "migration package provisioning identity could not manage the candidate"
        )

    provisioning_transport.execute(
        ({"command": "deleteClient", "username": "admin"},)
    )
    _assert_dynsec_object_missing(
        provisioning_transport,
        command="getClient",
        key="username",
        value="admin",
    )
    try:
        bootstrap_transport.execute(({"command": "listClients"},))
    except DynsecError:
        pass
    else:
        raise ShadowError(
            "migration package bootstrap admin remained usable after removal"
        )
    responses = provisioning_transport.execute(({"command": "listClients"},))
    if not responses or responses[0].get("command") != "listClients":
        raise ShadowError(
            "migration package provisioning identity failed after admin removal"
        )

    token = secrets.token_hex(6)
    system_id = material.system_id
    node_id = material.node_id
    node_ingress = f"gh/v1/{system_id}/ingress/node/{node_id}/telemetry"
    other_ingress = (
        f"gh/v1/{system_id}/ingress/node/gh-package-other-{token}/telemetry"
    )
    canonical_topic = f"gh/v1/{system_id}/state/gh-package-{token}/telemetry"
    discovery_topics = (
        f"homeassistant/device/gh-package-{token}/config",
        f"homeassistant/binary_sensor/gh-package-{token}_connectivity/config",
    )

    _assert_publish_allowed(
        runner,
        container_id,
        node_config,
        service_configs["manager"],
        node_ingress,
        f"package-node-{token}",
    )
    _assert_publish_denied(
        runner,
        container_id,
        node_config,
        other_ingress,
        f"package-cross-node-{token}",
    )
    _assert_publish_allowed(
        runner,
        container_id,
        service_configs["manager"],
        service_configs["homeassistant"],
        canonical_topic,
        f"package-canonical-{token}",
    )
    for topic in discovery_topics:
        _assert_publish_allowed(
            runner,
            container_id,
            service_configs["manager"],
            service_configs["homeassistant"],
            topic,
            f"package-discovery-{token}",
        )
    _assert_publish_allowed(
        runner,
        container_id,
        service_configs["homeassistant"],
        None,
        "homeassistant/status",
        f"package-ha-status-{token}",
    )

    for config_path, topic, payload in (
        (
            service_configs["manager"],
            "homeassistant/status",
            f"package-manager-status-{token}",
        ),
        (
            service_configs["manager"],
            node_ingress,
            f"package-manager-ingress-{token}",
        ),
        (
            service_configs["homeassistant"],
            canonical_topic + "/write",
            f"package-ha-canonical-{token}",
        ),
        (
            service_configs["homeassistant"],
            node_ingress + "/write",
            f"package-ha-ingress-{token}",
        ),
    ):
        _assert_publish_denied(
            runner,
            container_id,
            config_path,
            topic,
            payload,
        )

    provisioning_probe = f"gh/m2/package/provisioning-{token}"
    _assert_publish_denied(
        runner,
        container_id,
        service_configs["provisioning"],
        provisioning_probe,
        f"package-provisioning-write-{token}",
    )
    _assert_subscription_denied(
        runner,
        container_id,
        service_configs["provisioning"],
        provisioning_probe + "/read",
        f"package-provisioning-read-{token}",
    )

    credentials_by_label: dict[
        str, NodeCredentials | ServiceCredentials
    ] = {
        "node": material.node_credentials,
        **material.service_credentials,
    }
    allowed_topics = {
        "node": node_ingress,
        "manager": canonical_topic,
        "homeassistant": "homeassistant/status",
        "provisioning": CONTROL_TOPIC,
    }
    for label, credentials in credentials_by_label.items():
        _assert_wrong_client_id_rejected(
            runner,
            container_id,
            staging,
            label=f"package-{label}",
            credentials=credentials,
            allowed_topic=allowed_topics[label],
            control_identity=label == "provisioning",
        )

    for label, config_path in (
        ("node", node_config),
        ("manager", service_configs["manager"]),
        ("homeassistant", service_configs["homeassistant"]),
    ):
        _assert_control_denied(
            runner,
            container_id,
            config_path,
            provisioning_transport,
            canary_username=f"gh-package-{label}-control-{token}",
        )

    return_code, retained = _subscribe_once(
        runner,
        container_id,
        None,
        expected_retained_topic,
        timeout_s=5,
    )
    if return_code != 0 or not retained.strip():
        raise ShadowError(
            "migration package candidate did not recover retained state"
        )
    _assert_control_denied(
        runner,
        container_id,
        None,
        provisioning_transport,
        canary_username=f"gh-package-anonymous-control-{token}",
    )
    _assert_publish_allowed(
        runner,
        container_id,
        None,
        None,
        f"gh/m2/package/legacy-after-admin-removal-{token}",
        f"package-legacy-{token}",
    )

    return {
        "exact_package_identity_matrix": True,
        "client_id_binding": True,
        "provisioning_control_only": True,
        "bootstrap_admin_removed": True,
        "provisioning_after_admin_removal": True,
        "legacy_anonymous_after_admin_removal": True,
        "anonymous_control_denied": True,
        "retained_state_recovered": True,
    }


def run_migration_package_rehearsal(
    rollback_archive: str | Path,
    migration_package: str | Path,
    *,
    expected_retained_topic: str,
    runner: CommandRunner | None = None,
    name_factory: Callable[[], str] | None = None,
    verification_executor: VerificationExecutor | None = None,
) -> dict[str, object]:
    if not expected_retained_topic.startswith("gh/"):
        raise ValueError(
            "expected retained topic must be in the gh namespace"
        )
    command_runner = runner or SubprocessRunner()
    execute_verification = (
        verification_executor or _run_package_verification
    )
    rollback_path = Path(rollback_archive).expanduser().resolve()
    package_path = Path(migration_package).expanduser().resolve()
    candidate_name = (
        name_factory()
        if name_factory
        else f"gh-m2-package-rehearsal-{secrets.token_hex(4)}"
    )

    container_id = candidate_name
    created = False
    with tempfile.TemporaryDirectory(
        prefix="gh-m2-package-rehearsal-"
    ) as temporary:
        staging = Path(temporary)
        staging.chmod(0o700)
        snapshot_root = staging / "snapshot"
        package_root = staging / "package"
        snapshot_root.mkdir(mode=0o700)
        package_root.mkdir(mode=0o700)

        rollback_manifest = _extract_verified(
            rollback_path,
            snapshot_root,
        )
        package_manifest = _extract_verified_migration_package(
            package_path,
            package_root,
        )
        _require_source_binding(
            rollback_path,
            rollback_manifest,
            package_manifest,
        )
        material = _load_package_material(
            package_root,
            package_manifest,
        )

        config_dir = snapshot_root / "mosquitto-config"
        data_dir = snapshot_root / "mosquitto-data"
        config_path = config_dir / "mosquitto.conf"
        if not config_path.is_file() or not data_dir.is_dir():
            raise ShadowError(
                "rollback snapshot is missing Mosquitto configuration or data"
            )
        prepare_shadow_config(config_path)
        _prepare_snapshot_directories(config_dir, data_dir)
        dynsec_path = data_dir / "dynamic-security.json"
        if dynsec_path.exists():
            raise ShadowError(
                "rollback snapshot already contains Dynamic Security state"
            )

        bootstrap_password = _read_secret(
            package_root / "bootstrap/dynsec-password-init"
        )
        password_init_path = config_dir / "dynsec-password-init"
        password_init_path.write_text(
            bootstrap_password + "\n",
            encoding="utf-8",
        )
        password_init_path.chmod(0o644)

        image_id = rollback_manifest["sources"]["mosquitto"]["image_id"]
        data_stat = data_dir.stat()
        output = _require_success(
            command_runner,
            (
                "docker",
                "create",
                "--network",
                "none",
                "--name",
                candidate_name,
                "--mount",
                _mount(config_dir, "/mosquitto/config"),
                "--mount",
                _mount(data_dir, "/mosquitto/data"),
                image_id,
            ),
            "migration package rehearsal container could not be created",
        )
        created = True
        container_id = output or candidate_name
        try:
            _require_success(
                command_runner,
                ("docker", "start", container_id),
                "migration package rehearsal broker did not start",
            )
            state = _require_success(
                command_runner,
                (
                    "docker",
                    "inspect",
                    "-f",
                    "{{.State.Status}}",
                    container_id,
                ),
                "migration package rehearsal state could not be inspected",
            )
            if state != "running":
                raise ShadowError(
                    "migration package rehearsal broker is not running"
                )
            if not _wait_for_file(dynsec_path):
                final_state = _require_success(
                    command_runner,
                    (
                        "docker",
                        "inspect",
                        "-f",
                        "{{.State.Status}} exit={{.State.ExitCode}}",
                        container_id,
                    ),
                    "migration package rehearsal final state could not be inspected",
                )
                raise ShadowError(
                    "migration package Dynamic Security state was not created "
                    f"within 10 seconds ({final_state}); "
                    + _candidate_diagnostic(
                        command_runner,
                        container_id,
                        secret=bootstrap_password,
                    )
                )
            os.chown(dynsec_path, data_stat.st_uid, data_stat.st_gid)
            dynsec_path.chmod(0o600)
            password_init_path.unlink(missing_ok=True)

            admin_config_path = "/tmp/gh-m2-package-admin.conf"
            _require_success(
                command_runner,
                (
                    "docker",
                    "cp",
                    "--archive",
                    str(package_root / "bootstrap/admin-client.conf"),
                    f"{container_id}:{admin_config_path}",
                ),
                "migration package bootstrap admin config copy failed",
            )
            bootstrap_transport = MosquittoRRTransport(
                command_runner,
                container_id,
                admin_config_path,
            )
            bootstrap_transport.execute(material.commands)
            verification_result = execute_verification(
                command_runner,
                container_id,
                staging,
                bootstrap_transport,
                material,
                expected_retained_topic,
            )
        finally:
            if created:
                command_runner.run(
                    ("docker", "rm", "-f", container_id)
                )

    return {
        "schema": PACKAGE_REHEARSAL_SCHEMA,
        "archive": rollback_path.name,
        "package": package_path.name,
        "package_sha256": _sha256_path(package_path),
        "network": "none",
        "source_binding": True,
        "exact_package_request_applied": True,
        **verification_result,
        "current_services_modified": False,
    }


def main(
    argv: Sequence[str] | None = None,
    *,
    runner: CommandRunner | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Apply an exact private migration package only to a "
            "--network none T1 snapshot candidate."
        )
    )
    parser.add_argument("rollback_archive")
    parser.add_argument("migration_package")
    parser.add_argument("--expected-retained-topic", required=True)
    args = parser.parse_args(argv)
    try:
        result = run_migration_package_rehearsal(
            args.rollback_archive,
            args.migration_package,
            expected_retained_topic=args.expected_retained_topic,
            runner=runner,
        )
    except (
        BackupError,
        DynsecError,
        MigrationPackageError,
        ShadowError,
        OSError,
        ValueError,
    ) as error:
        print(
            f"T1 migration package rehearsal failed: {error}",
            file=sys.stderr,
        )
        return 2
    json.dump(
        result,
        sys.stdout,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
