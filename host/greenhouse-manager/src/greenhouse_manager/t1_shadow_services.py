from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .dynsec_api import (
    CONTROL_TOPIC,
    RESPONSE_TOPIC,
    DynsecError,
    DynsecProvisioner,
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
from .t1_backup import BackupError, _extract_verified
from .t1_shadow import (
    CommandRunner,
    ShadowError,
    SubprocessRunner,
    _candidate_diagnostic,
    _mount,
    _prepare_snapshot_directories,
    _require_success,
    _wait_for_file,
    legacy_shadow_ctrl_commands,
    prepare_shadow_config,
)

IdentityPlan = NodeProvisioningPlan | ServiceIdentityPlan
IdentityCredentials = NodeCredentials | ServiceCredentials
MatrixExecutor = Callable[
    [CommandRunner, str, Path, str, str],
    dict[str, bool],
]


@dataclass(frozen=True, slots=True)
class IdentityBundle:
    node_plan: NodeProvisioningPlan
    node_credentials: NodeCredentials
    service_plans: dict[str, ServiceIdentityPlan]
    service_credentials: dict[str, ServiceCredentials]


class MosquittoRRTransport:
    """Dynamic Security topic transport executed entirely inside the candidate."""

    def __init__(
        self,
        runner: CommandRunner,
        container_id: str,
        config_path: str,
        *,
        timeout_s: int = 8,
    ) -> None:
        if timeout_s <= 0:
            raise ValueError("timeout_s must be positive")
        self.runner = runner
        self.container_id = container_id
        self.config_path = config_path
        self.timeout_s = timeout_s

    def execute(
        self, commands: Sequence[dict[str, Any]]
    ) -> tuple[dict[str, Any], ...]:
        if not commands:
            raise ValueError("at least one command is required")
        payload = json.dumps(
            {"commands": list(commands)},
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return_code, output = self.runner.run(
            (
                "docker",
                "exec",
                "-i",
                self.container_id,
                "mosquitto_rr",
                "-o",
                self.config_path,
                "-q",
                "1",
                "-W",
                str(self.timeout_s),
                "-t",
                CONTROL_TOPIC,
                "-e",
                RESPONSE_TOPIC,
                "-s",
            ),
            input_text=payload,
        )
        if return_code != 0:
            raise DynsecError("Dynamic Security request failed in shadow candidate")
        try:
            document = json.loads(output)
        except json.JSONDecodeError as error:
            raise DynsecError(
                "Dynamic Security returned invalid JSON in shadow candidate"
            ) from error
        responses = document.get("responses") if isinstance(document, dict) else None
        if not isinstance(responses, list):
            raise DynsecError(
                "Dynamic Security response is missing responses in shadow candidate"
            )
        normalized: list[dict[str, Any]] = []
        for response in responses:
            if not isinstance(response, dict):
                raise DynsecError(
                    "Dynamic Security returned an invalid response entry"
                )
            if response.get("error"):
                command = response.get("command", "unknown")
                raise DynsecError(f"Dynamic Security command failed: {command}")
            normalized.append(response)
        return tuple(normalized)


class FailAfterCreateClientTransport:
    """Inject failure after a real createClient response to exercise rollback."""

    def __init__(self, delegate: MosquittoRRTransport) -> None:
        self.delegate = delegate
        self.command_names: list[str] = []
        self.failed = False

    def execute(
        self, commands: Sequence[dict[str, Any]]
    ) -> tuple[dict[str, Any], ...]:
        self.command_names.extend(command["command"] for command in commands)
        responses = self.delegate.execute(commands)
        if not self.failed and any(
            command["command"] == "createClient" for command in commands
        ):
            self.failed = True
            raise DynsecError("injected post-create failure")
        return responses


def build_identity_bundle(
    *,
    system_id: str = "greenhouse",
    node_id: str = "gh-n1-a9f2f8",
) -> IdentityBundle:
    node_plan = build_node_provisioning_plan(
        system_id=system_id,
        node_id=node_id,
        generation=1,
    )
    service_plans = {
        service: build_service_identity_plan(
            system_id=system_id,
            service=service,  # type: ignore[arg-type]
            generation=1,
        )
        for service in ("provisioning", "manager", "homeassistant")
    }
    node_credentials = generate_node_credentials(node_plan)
    service_credentials = {
        service: generate_service_credentials(plan)
        for service, plan in service_plans.items()
    }
    identities: tuple[IdentityCredentials, ...] = (
        node_credentials,
        *service_credentials.values(),
    )
    if len({identity.username for identity in identities}) != len(identities):
        raise ShadowError("candidate identity usernames are not unique")
    if len({identity.client_id for identity in identities}) != len(identities):
        raise ShadowError("candidate identity client IDs are not unique")
    return IdentityBundle(
        node_plan=node_plan,
        node_credentials=node_credentials,
        service_plans=service_plans,
        service_credentials=service_credentials,
    )


def _copy_client_config(
    runner: CommandRunner,
    container_id: str,
    staging: Path,
    *,
    label: str,
    username: str,
    password: str,
    client_id: str,
) -> str:
    host_path = staging / f"{label}.conf"
    container_path = f"/tmp/{label}.conf"
    host_path.write_text(
        "-h 127.0.0.1\n"
        f"-u {username}\n"
        f"-P {password}\n"
        f"-i {client_id}\n"
        "-V 5\n",
        encoding="utf-8",
    )
    host_path.chmod(0o600)
    try:
        _require_success(
            runner,
            (
                "docker",
                "cp",
                "--archive",
                str(host_path),
                f"{container_id}:{container_path}",
            ),
            f"candidate client configuration copy failed: {label}",
        )
    finally:
        host_path.unlink(missing_ok=True)
    return container_path


def _publish(
    runner: CommandRunner,
    container_id: str,
    config_path: str | None,
    topic: str,
    payload: str,
    *,
    retain: bool = True,
) -> tuple[int, str]:
    command: list[str] = [
        "docker",
        "exec",
        "-i",
        container_id,
        "mosquitto_pub",
    ]
    if config_path is None:
        command.extend(("-h", "127.0.0.1", "-V", "5"))
    else:
        command.extend(("-o", config_path))
    command.extend(("-q", "1"))
    if retain:
        command.append("-r")
    command.extend(("-t", topic, "-s"))
    return runner.run(tuple(command), input_text=payload)


def _subscribe_once(
    runner: CommandRunner,
    container_id: str,
    config_path: str | None,
    topic: str,
    *,
    timeout_s: int = 3,
) -> tuple[int, str]:
    command: list[str] = [
        "docker",
        "exec",
        container_id,
        "mosquitto_sub",
    ]
    if config_path is None:
        command.extend(("-h", "127.0.0.1", "-V", "5"))
    else:
        command.extend(("-o", config_path))
    command.extend(
        (
            "-C",
            "1",
            "-W",
            str(timeout_s),
            "-F",
            "%p",
            "-t",
            topic,
        )
    )
    return runner.run(tuple(command))


def _assert_publish_allowed(
    runner: CommandRunner,
    container_id: str,
    publisher_config: str | None,
    subscriber_config: str | None,
    topic: str,
    payload: str,
) -> None:
    return_code, _output = _publish(
        runner,
        container_id,
        publisher_config,
        topic,
        payload,
    )
    if return_code != 0:
        raise ShadowError(f"candidate allowed publish failed: {topic}")
    return_code, output = _subscribe_once(
        runner,
        container_id,
        subscriber_config,
        topic,
    )
    if return_code != 0 or output.strip() != payload:
        raise ShadowError(f"candidate allowed delivery failed: {topic}")


def _assert_publish_denied(
    runner: CommandRunner,
    container_id: str,
    publisher_config: str,
    topic: str,
    payload: str,
) -> None:
    _publish(
        runner,
        container_id,
        publisher_config,
        topic,
        payload,
    )
    return_code, output = _subscribe_once(
        runner,
        container_id,
        None,
        topic,
        timeout_s=1,
    )
    if return_code == 0 and output.strip() == payload:
        raise ShadowError(f"candidate unauthorized publish succeeded: {topic}")


def _assert_subscription_denied(
    runner: CommandRunner,
    container_id: str,
    subscriber_config: str,
    topic: str,
    payload: str,
) -> None:
    return_code, _output = _publish(
        runner,
        container_id,
        None,
        topic,
        payload,
    )
    if return_code != 0:
        raise ShadowError("legacy setup publish failed before subscription denial check")
    return_code, output = _subscribe_once(
        runner,
        container_id,
        subscriber_config,
        topic,
        timeout_s=1,
    )
    if return_code == 0 and output.strip() == payload:
        raise ShadowError(f"candidate unauthorized subscription succeeded: {topic}")


def _assert_wrong_client_id_rejected(
    runner: CommandRunner,
    container_id: str,
    staging: Path,
    *,
    label: str,
    credentials: IdentityCredentials,
    allowed_topic: str,
    control_identity: bool = False,
) -> None:
    wrong_config = _copy_client_config(
        runner,
        container_id,
        staging,
        label=f"{label}-wrong-id",
        username=credentials.username,
        password=credentials.password,
        client_id=f"{credentials.client_id}-wrong",
    )
    if control_identity:
        transport = MosquittoRRTransport(
            runner,
            container_id,
            wrong_config,
            timeout_s=3,
        )
        try:
            transport.execute(({"command": "listClients"},))
        except DynsecError:
            return
        raise ShadowError("candidate provisioning identity accepted wrong client ID")
    return_code, _output = _publish(
        runner,
        container_id,
        wrong_config,
        allowed_topic,
        f"wrong-id-{label}",
        retain=False,
    )
    if return_code == 0:
        raise ShadowError(f"candidate identity accepted wrong client ID: {label}")


def _assert_dynsec_object_missing(
    transport: MosquittoRRTransport,
    *,
    command: str,
    key: str,
    value: str,
) -> None:
    try:
        transport.execute(({"command": command, key: value},))
    except DynsecError:
        return
    raise ShadowError(f"candidate rollback left object behind: {command}")


def _assert_control_denied(
    runner: CommandRunner,
    container_id: str,
    config_path: str | None,
    admin_transport: MosquittoRRTransport,
    *,
    canary_username: str,
) -> None:
    payload = json.dumps(
        {
            "commands": [
                {
                    "command": "createClient",
                    "username": canary_username,
                    "password": secrets.token_urlsafe(32),
                    "clientid": canary_username,
                }
            ]
        },
        separators=(",", ":"),
    )
    _publish(
        runner,
        container_id,
        config_path,
        CONTROL_TOPIC,
        payload,
        retain=False,
    )
    _assert_dynsec_object_missing(
        admin_transport,
        command="getClient",
        key="username",
        value=canary_username,
    )


def _run_service_identity_matrix(
    runner: CommandRunner,
    container_id: str,
    staging: Path,
    admin_config_path: str,
    system_id: str,
    node_id: str,
) -> dict[str, bool]:
    bundle = build_identity_bundle(system_id=system_id, node_id=node_id)
    admin_transport = MosquittoRRTransport(
        runner,
        container_id,
        admin_config_path,
    )
    provisioner = DynsecProvisioner(admin_transport)
    provisioner.apply_baseline(bundle.node_plan)
    provisioner.provision(bundle.node_plan, bundle.node_credentials)
    for service, plan in bundle.service_plans.items():
        provisioner.provision(
            plan,
            bundle.service_credentials[service],
        )

    node_config = _copy_client_config(
        runner,
        container_id,
        staging,
        label="gh-m2-node",
        username=bundle.node_credentials.username,
        password=bundle.node_credentials.password,
        client_id=bundle.node_credentials.client_id,
    )
    service_configs = {
        service: _copy_client_config(
            runner,
            container_id,
            staging,
            label=f"gh-m2-{service}",
            username=credentials.username,
            password=credentials.password,
            client_id=credentials.client_id,
        )
        for service, credentials in bundle.service_credentials.items()
    }

    token = secrets.token_hex(6)
    node_ingress = f"gh/v1/{system_id}/ingress/node/{node_id}/telemetry"
    other_ingress = (
        f"gh/v1/{system_id}/ingress/node/gh-shadow-other-{token}/telemetry"
    )
    canonical_topic = f"gh/v1/{system_id}/state/gh-shadow-{token}/telemetry"
    discovery_device = f"homeassistant/device/gh-shadow-{token}/config"
    discovery_connectivity = (
        f"homeassistant/binary_sensor/gh-shadow-{token}_connectivity/config"
    )

    _assert_publish_allowed(
        runner,
        container_id,
        node_config,
        service_configs["manager"],
        node_ingress,
        f"node-ingress-{token}",
    )
    _assert_publish_denied(
        runner,
        container_id,
        node_config,
        other_ingress,
        f"cross-node-{token}",
    )
    _assert_publish_allowed(
        runner,
        container_id,
        service_configs["manager"],
        service_configs["homeassistant"],
        canonical_topic,
        f"canonical-{token}",
    )
    for topic in (discovery_device, discovery_connectivity):
        _assert_publish_allowed(
            runner,
            container_id,
            service_configs["manager"],
            service_configs["homeassistant"],
            topic,
            f"discovery-{token}",
        )

    _assert_publish_allowed(
        runner,
        container_id,
        service_configs["homeassistant"],
        None,
        "homeassistant/status",
        f"ha-status-{token}",
    )
    _assert_publish_denied(
        runner,
        container_id,
        service_configs["manager"],
        "homeassistant/status",
        f"manager-status-{token}",
    )
    _assert_publish_denied(
        runner,
        container_id,
        service_configs["manager"],
        node_ingress,
        f"manager-ingress-{token}",
    )
    _assert_publish_denied(
        runner,
        container_id,
        service_configs["homeassistant"],
        canonical_topic + "/ha-write",
        f"ha-canonical-{token}",
    )
    _assert_publish_denied(
        runner,
        container_id,
        service_configs["homeassistant"],
        node_ingress + "/ha-write",
        f"ha-ingress-{token}",
    )

    provisioning_probe = f"gh/m2/shadow/provisioning-{token}"
    _assert_publish_denied(
        runner,
        container_id,
        service_configs["provisioning"],
        provisioning_probe,
        f"provisioning-write-{token}",
    )
    _assert_subscription_denied(
        runner,
        container_id,
        service_configs["provisioning"],
        provisioning_probe + "/read",
        f"provisioning-read-{token}",
    )
    provisioning_transport = MosquittoRRTransport(
        runner,
        container_id,
        service_configs["provisioning"],
    )
    responses = provisioning_transport.execute(({"command": "listClients"},))
    if not responses or responses[0].get("command") != "listClients":
        raise ShadowError("candidate provisioning control response did not match")

    allowed_topics = {
        "node": node_ingress,
        "manager": canonical_topic,
        "homeassistant": "homeassistant/status",
        "provisioning": CONTROL_TOPIC,
    }
    credentials_by_label: dict[str, IdentityCredentials] = {
        "node": bundle.node_credentials,
        **bundle.service_credentials,
    }
    for label, credentials in credentials_by_label.items():
        _assert_wrong_client_id_rejected(
            runner,
            container_id,
            staging,
            label=label,
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
            admin_transport,
            canary_username=f"gh-shadow-{label}-control-{token}",
        )

    rollback_plan = build_node_provisioning_plan(
        system_id=system_id,
        node_id=f"gh-shadow-rollback-{token}",
        generation=1,
    )
    rollback_credentials = generate_node_credentials(rollback_plan)
    failing_transport = FailAfterCreateClientTransport(admin_transport)
    try:
        DynsecProvisioner(failing_transport).provision(
            rollback_plan,
            rollback_credentials,
        )
    except DynsecError:
        pass
    else:
        raise ShadowError("candidate injected provisioning failure was not raised")
    if failing_transport.command_names != [
        "createRole",
        "createClient",
        "deleteClient",
        "deleteRole",
    ]:
        raise ShadowError("candidate provisioning rollback order did not match")
    _assert_dynsec_object_missing(
        admin_transport,
        command="getClient",
        key="username",
        value=rollback_plan.username,
    )
    _assert_dynsec_object_missing(
        admin_transport,
        command="getRole",
        key="rolename",
        value=rollback_plan.role_name,
    )

    legacy_after_rollback = f"gh/m2/shadow/legacy-after-rollback-{token}"
    _assert_publish_allowed(
        runner,
        container_id,
        None,
        None,
        legacy_after_rollback,
        f"legacy-ok-{token}",
    )

    return {
        "service_identity_matrix": True,
        "client_id_binding": True,
        "provisioning_control_only": True,
        "transaction_rollback": True,
        "legacy_anonymous_after_rollback": True,
    }


def run_shadow_service_candidate(
    archive: str | Path,
    *,
    expected_retained_topic: str,
    system_id: str = "greenhouse",
    node_id: str = "gh-n1-a9f2f8",
    runner: CommandRunner | None = None,
    password_factory: Callable[[], str] | None = None,
    name_factory: Callable[[], str] | None = None,
    matrix_executor: MatrixExecutor | None = None,
) -> dict[str, object]:
    if not expected_retained_topic.startswith("gh/"):
        raise ValueError("expected retained topic must be in the gh namespace")
    command_runner = runner or SubprocessRunner()
    execute_matrix = matrix_executor or _run_service_identity_matrix
    archive_path = Path(archive).expanduser().resolve()
    candidate_name = (
        name_factory()
        if name_factory
        else f"gh-m2-shadow-services-{secrets.token_hex(4)}"
    )
    admin_password = (
        password_factory() if password_factory else secrets.token_urlsafe(32)
    )
    if len(admin_password) < 32:
        raise ValueError("candidate admin password must be at least 32 characters")

    container_id = candidate_name
    created = False
    with tempfile.TemporaryDirectory(
        prefix="gh-m2-shadow-services-"
    ) as temporary:
        staging = Path(temporary)
        staging.chmod(0o700)
        manifest = _extract_verified(archive_path, staging)
        config_dir = staging / "mosquitto-config"
        data_dir = staging / "mosquitto-data"
        config_path = config_dir / "mosquitto.conf"
        if not config_path.is_file() or not data_dir.is_dir():
            raise ShadowError(
                "snapshot is missing Mosquitto configuration or data"
            )
        prepare_shadow_config(config_path)
        _prepare_snapshot_directories(config_dir, data_dir)
        dynsec_path = data_dir / "dynamic-security.json"
        if dynsec_path.exists():
            raise ShadowError("snapshot already contains Dynamic Security state")

        image_id = manifest["sources"]["mosquitto"]["image_id"]
        data_stat = data_dir.stat()
        password_init_path = config_dir / "dynsec-password-init"
        password_init_path.write_text(
            admin_password + "\n",
            encoding="utf-8",
        )
        password_init_path.chmod(0o644)

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
            "shadow service candidate container could not be created",
        )
        created = True
        container_id = output or candidate_name
        try:
            _require_success(
                command_runner,
                ("docker", "start", container_id),
                "shadow service candidate broker did not start",
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
                "shadow service candidate state could not be inspected",
            )
            if state != "running":
                raise ShadowError(
                    "shadow service candidate broker is not running"
                )
            if not _wait_for_file(dynsec_path):
                state = _require_success(
                    command_runner,
                    (
                        "docker",
                        "inspect",
                        "-f",
                        "{{.State.Status}} exit={{.State.ExitCode}}",
                        container_id,
                    ),
                    "shadow service candidate final state could not be inspected",
                )
                raise ShadowError(
                    "Dynamic Security service candidate state was not created "
                    f"within 10 seconds ({state}); "
                    + _candidate_diagnostic(
                        command_runner,
                        container_id,
                        secret=admin_password,
                    )
                )
            os.chown(dynsec_path, data_stat.st_uid, data_stat.st_gid)
            dynsec_path.chmod(0o600)
            password_init_path.unlink(missing_ok=True)

            admin_host_config = staging / "mosquitto-admin.conf"
            admin_host_config.write_text(
                "-h 127.0.0.1\n"
                "-u admin\n"
                f"-P {admin_password}\n"
                "-i gh-m2-shadow-admin\n"
                "-V 5\n",
                encoding="utf-8",
            )
            admin_host_config.chmod(0o600)
            admin_config_path = "/tmp/gh-m2-admin.conf"
            try:
                _require_success(
                    command_runner,
                    (
                        "docker",
                        "cp",
                        "--archive",
                        str(admin_host_config),
                        f"{container_id}:{admin_config_path}",
                    ),
                    "shadow service candidate admin configuration copy failed",
                )
            finally:
                admin_host_config.unlink(missing_ok=True)

            for command in legacy_shadow_ctrl_commands():
                _require_success(
                    command_runner,
                    (
                        "docker",
                        "exec",
                        container_id,
                        "mosquitto_ctrl",
                        "-o",
                        admin_config_path,
                        "dynsec",
                        *command,
                    ),
                    f"shadow service candidate policy command failed: {command[0]}",
                )

            legacy_probe = "gh/m2/shadow/services/legacy-probe"
            _assert_publish_allowed(
                command_runner,
                container_id,
                None,
                None,
                legacy_probe,
                "legacy-ok",
            )
            return_code, retained = _subscribe_once(
                command_runner,
                container_id,
                None,
                expected_retained_topic,
                timeout_s=5,
            )
            if return_code != 0 or not retained.strip():
                raise ShadowError(
                    "snapshot retained state was not recovered in service candidate"
                )
            _assert_control_denied(
                command_runner,
                container_id,
                None,
                MosquittoRRTransport(
                    command_runner,
                    container_id,
                    admin_config_path,
                ),
                canary_username="gh-shadow-services-anonymous-canary",
            )

            matrix_result = execute_matrix(
                command_runner,
                container_id,
                staging,
                admin_config_path,
                system_id,
                node_id,
            )
        finally:
            if created:
                command_runner.run(("docker", "rm", "-f", container_id))

    return {
        "schema": "gh.m2.t1-shadow-service-candidate/1",
        "archive": archive_path.name,
        "network": "none",
        "node_id": node_id,
        "legacy_anonymous_application_topics": True,
        "anonymous_control_denied": True,
        "retained_state_recovered": True,
        **matrix_result,
        "current_services_modified": False,
    }


def main(
    argv: Sequence[str] | None = None,
    *,
    runner: CommandRunner | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Verify service and node identities in a Dynamic Security "
            "candidate created from a T1 backup"
        )
    )
    parser.add_argument("archive")
    parser.add_argument("--expected-retained-topic", required=True)
    parser.add_argument("--system-id", default="greenhouse")
    parser.add_argument("--node-id", default="gh-n1-a9f2f8")
    args = parser.parse_args(argv)
    try:
        result = run_shadow_service_candidate(
            args.archive,
            expected_retained_topic=args.expected_retained_topic,
            system_id=args.system_id,
            node_id=args.node_id,
            runner=runner,
        )
    except (BackupError, DynsecError, ShadowError, OSError) as error:
        print(
            f"T1 shadow service candidate failed: {error}",
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
