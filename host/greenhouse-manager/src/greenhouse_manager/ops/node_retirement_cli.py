from __future__ import annotations

import argparse
import json
import os
import sys
import threading
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Protocol, TextIO

import paho.mqtt.client as mqtt

from ..runtime.credential_lifecycle import CredentialLifecycleStore, CredentialState
from ..runtime.dynsec_api import DynsecProvisioner, PahoDynsecTransport
from ..runtime.dynsec_plan import build_node_provisioning_plan
from ..runtime.registration import RegistrationRegistry, RetirementJob

DEFAULT_DB_PATH = "/var/lib/greenhouse-manager/registration.sqlite3"


class CredentialRevoker(Protocol):
    def revoke(self, job: RetirementJob, generation: int) -> None: ...


def _read_secret(path_text: str) -> str:
    path = Path(path_text).expanduser()
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise ValueError("provisioning password file must be a regular absolute path")
    if path.stat().st_mode & 0o077:
        raise ValueError(
            "provisioning password file must not be accessible by group or other"
        )
    value = path.read_text(encoding="utf-8").rstrip("\r\n")
    if not value or "\n" in value or "\r" in value or "\x00" in value:
        raise ValueError(
            "provisioning password file must contain one non-empty secret"
        )
    return value


class PahoCredentialRevoker:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        client_id: str,
        tls: bool,
        ca_file: str | None,
        timeout_s: float = 10.0,
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.client_id = client_id
        self.tls = tls
        self.ca_file = ca_file
        self.timeout_s = timeout_s

    def revoke(self, job: RetirementJob, generation: int) -> None:
        connected = threading.Event()
        connection_error: list[str] = []
        client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=self.client_id,
            protocol=mqtt.MQTTv5,
        )
        client.username_pw_set(self.username, self.password)
        if self.tls:
            client.tls_set(ca_certs=self.ca_file)
        transport = PahoDynsecTransport(client, timeout_s=self.timeout_s)

        def on_connect(
            _client: mqtt.Client,
            _userdata: object,
            _flags: mqtt.ConnectFlags,
            reason_code: mqtt.ReasonCode,
            _properties: mqtt.Properties | None,
        ) -> None:
            if reason_code.is_failure:
                connection_error.append(str(reason_code))
            connected.set()

        client.on_connect = on_connect
        client.on_message = transport.on_message
        client.reconnect_delay_set(min_delay=1, max_delay=5)
        try:
            client.connect(self.host, self.port, keepalive=30)
            client.loop_start()
            if not connected.wait(self.timeout_s):
                raise RuntimeError("provisioning MQTT connection timed out")
            if connection_error:
                raise RuntimeError("provisioning MQTT connection was rejected")
            plan = build_node_provisioning_plan(
                system_id=job.system_id,
                node_id=job.node_id,
                generation=generation,
            )
            DynsecProvisioner(transport).deprovision(plan)
        finally:
            client.disconnect()
            client.loop_stop()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Retire greenhouse nodes through the durable C-07 outbox"
    )
    parser.add_argument(
        "--db",
        default=os.getenv("GH_PAIRING_DB_PATH", DEFAULT_DB_PATH),
        help="registration SQLite path",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    retire = subparsers.add_parser(
        "retire",
        help="atomically retire a registration and queue external cleanup",
    )
    retire.add_argument("hardware_id")
    retire.add_argument("--system-id", default=os.getenv("GH_SYSTEM_ID", "dev"))
    retire.add_argument("--reason", default="operator_retired")
    retire.add_argument(
        "--defer-credential-revocation",
        action="store_true",
        help="queue only; node_id remains non-reusable until revocation succeeds",
    )

    subparsers.add_parser("list", help="list retirement outbox records")

    status = subparsers.add_parser("status", help="show one retirement record")
    status.add_argument("retirement_id", type=int)

    revoke = subparsers.add_parser(
        "revoke-credentials",
        help="delete the node Dynamic Security client/role and release metadata",
    )
    revoke.add_argument("retirement_id", type=int)
    revoke.add_argument("--mqtt-host", default=os.getenv("GH_MQTT_HOST", "mosquitto"))
    revoke.add_argument(
        "--mqtt-port",
        type=int,
        default=int(os.getenv("GH_MQTT_PORT", "1883")),
    )
    revoke.add_argument("--username", default=os.getenv("GH_PROVISIONING_MQTT_USERNAME"))
    revoke.add_argument(
        "--password-file",
        default=os.getenv("GH_PROVISIONING_MQTT_PASSWORD_FILE"),
    )
    revoke.add_argument(
        "--client-id",
        default=os.getenv("GH_PROVISIONING_MQTT_CLIENT_ID"),
    )
    revoke.add_argument(
        "--tls",
        action=argparse.BooleanOptionalAction,
        default=os.getenv("GH_MQTT_TLS", "").lower() in {"1", "true", "yes", "on"},
    )
    revoke.add_argument("--ca-file", default=os.getenv("GH_MQTT_CA_FILE"))

    isolated = subparsers.add_parser(
        "confirm-isolated",
        help="record externally verified revocation and private ingress isolation",
    )
    isolated.add_argument("retirement_id", type=int)
    isolated.add_argument("--evidence", required=True)
    isolated.add_argument(
        "--credentials-revoked-externally",
        action="store_true",
        required=True,
    )
    isolated.add_argument(
        "--private-ingress-disabled",
        action="store_true",
        required=True,
    )
    return parser


def _job_document(job: RetirementJob) -> dict[str, object]:
    document = asdict(job)
    for key in ("created_at", "updated_at", "completed_at"):
        value = document[key]
        document[key] = (
            value.isoformat(timespec="milliseconds").replace("+00:00", "Z")
            if value is not None
            else None
        )
    return document


def _write(output: TextIO, document: object) -> None:
    json.dump(
        document,
        output,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )
    output.write("\n")


def _build_revoker(args: argparse.Namespace, system_id: str) -> CredentialRevoker:
    if not args.username:
        raise ValueError("provisioning MQTT username is required")
    if not args.password_file:
        raise ValueError("provisioning MQTT password file is required")
    if args.tls and not args.ca_file:
        raise ValueError("MQTT CA file is required when TLS is enabled")
    client_id = args.client_id or f"gh-provisioning-{system_id}"
    return PahoCredentialRevoker(
        host=args.mqtt_host,
        port=args.mqtt_port,
        username=args.username,
        password=_read_secret(args.password_file),
        client_id=client_id,
        tls=args.tls,
        ca_file=args.ca_file,
    )


def _revoke_job(
    database: Path,
    registry: RegistrationRegistry,
    job: RetirementJob,
    revoker: CredentialRevoker,
) -> RetirementJob:
    try:
        with CredentialLifecycleStore(database) as lifecycle_store:
            lifecycle = lifecycle_store.get(job.hardware_id)
            lifecycle_node_id = lifecycle.node_id or lifecycle.last_node_id
            if lifecycle_node_id != job.node_id:
                raise ValueError(
                    "credential lifecycle node_id does not match retirement job"
                )
            if lifecycle.state is not CredentialState.REVOKED:
                revoker.revoke(job, lifecycle.active_generation)
                lifecycle_store.revoke(job.hardware_id, reason="node_retired")
    except Exception as error:
        registry.record_retirement_failure(
            job.retirement_id,
            f"credential_revocation_failed:{type(error).__name__}",
        )
        raise
    return registry.mark_credentials_revoked(
        job.retirement_id,
        evidence="dynsec_client_role_deleted",
    )


def main(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    credential_revoker: CredentialRevoker | None = None,
) -> int:
    output = stdout or sys.stdout
    error_output = stderr or sys.stderr
    args = _parser().parse_args(argv)
    database = Path(args.db)
    if not database.exists():
        print(f"Registration database does not exist: {database}", file=error_output)
        return 2

    try:
        with RegistrationRegistry(database) as registry:
            if args.command == "retire":
                job = registry.retire(
                    args.hardware_id,
                    system_id=args.system_id,
                    reason=args.reason,
                )
                if not args.defer_credential_revocation:
                    revoker = credential_revoker
                    if revoker is None:
                        revoke_args = argparse.Namespace(
                            mqtt_host=os.getenv("GH_MQTT_HOST", "mosquitto"),
                            mqtt_port=int(os.getenv("GH_MQTT_PORT", "1883")),
                            username=os.getenv("GH_PROVISIONING_MQTT_USERNAME"),
                            password_file=os.getenv(
                                "GH_PROVISIONING_MQTT_PASSWORD_FILE"
                            ),
                            client_id=os.getenv("GH_PROVISIONING_MQTT_CLIENT_ID"),
                            tls=os.getenv("GH_MQTT_TLS", "").lower()
                            in {"1", "true", "yes", "on"},
                            ca_file=os.getenv("GH_MQTT_CA_FILE"),
                        )
                        revoker = _build_revoker(revoke_args, job.system_id)
                    job = _revoke_job(database, registry, job, revoker)
                _write(output, _job_document(job))
            elif args.command == "list":
                _write(
                    output,
                    [_job_document(job) for job in registry.list_retirement_jobs()],
                )
            elif args.command == "status":
                _write(
                    output,
                    _job_document(registry.get_retirement_job(args.retirement_id)),
                )
            elif args.command == "revoke-credentials":
                job = registry.get_retirement_job(args.retirement_id)
                revoker = credential_revoker or _build_revoker(args, job.system_id)
                job = _revoke_job(database, registry, job, revoker)
                _write(output, _job_document(job))
            elif args.command == "confirm-isolated":
                evidence = f"external_revocation_and_private_ingress:{args.evidence}"
                job = registry.mark_credentials_revoked(
                    args.retirement_id,
                    evidence=evidence,
                )
                _write(output, _job_document(job))
    except (KeyError, RuntimeError, ValueError) as error:
        print(f"Node retirement command failed: {error}", file=error_output)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
