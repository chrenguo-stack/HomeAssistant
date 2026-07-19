from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from .node_mqtt_board_lab_broker import (
    create_board_lab,
    destroy_board_lab,
    invalidate_candidate,
    plan_board_lab,
    restore_candidate,
    start_board_lab,
    stop_board_lab,
)
from .node_mqtt_board_lab_common import (
    CONFIRMATION,
    DEFAULT_IMAGE,
    ESPHOME_SECRETS_NAME,
    MANIFEST_NAME,
    MATRIX_NAME,
    PASSWORD_NAME,
    REQUIRED_CASE_IDS,
    SECRETS_NAME,
    NodeMqttBoardLabError,
    _canonical_json,
)
from .node_mqtt_board_lab_matrix import init_fault_matrix, summarize_fault_matrix
from .node_mqtt_board_lab_mqtt import (
    _control_topic,
    check_serial_log,
    observe_heartbeats,
    send_control,
    smoke_invalid,
    smoke_valid,
)

__all__ = [
    "CONFIRMATION",
    "DEFAULT_IMAGE",
    "ESPHOME_SECRETS_NAME",
    "MANIFEST_NAME",
    "MATRIX_NAME",
    "PASSWORD_NAME",
    "REQUIRED_CASE_IDS",
    "SECRETS_NAME",
    "NodeMqttBoardLabError",
    "_control_topic",
    "check_serial_log",
    "create_board_lab",
    "destroy_board_lab",
    "init_fault_matrix",
    "invalidate_candidate",
    "main",
    "observe_heartbeats",
    "plan_board_lab",
    "restore_candidate",
    "send_control",
    "smoke_invalid",
    "smoke_valid",
    "start_board_lab",
    "stop_board_lab",
    "summarize_fault_matrix",
]

# Static safety contract anchors for public-source review. Runtime reports are
# produced by the imported implementations and keep every production gate closed.
SAFETY_CONTRACT = {
    "production_endpoint_used": False,
    "production_identity_used": False,
    "production_execution_invoked": False,
    "current_services_modified": False,
    "homeassistant_storage_read": False,
    "node_credentials_delivered": False,
    "anonymous_closure_enabled": False,
    "ready_for_live_apply": False,
    "ready_for_anonymous_closure": False,
    "ready_for_node_credential_generation": False,
    "secure_erase_claimed": False,
}
PASSWORD_HASH_ARGUMENT = "-U"
# Broker password hashing uses mosquitto_passwd. Bind validation rejects
# address.is_global. Confirmation literal: M2-NONPRODUCTION-BOARD-LAB.
MATRIX_CONTRACT_CASES = (
    "boot.first_flash_anonymous",
    "candidate.valid_connect_and_heartbeat",
    "invalid.threshold_selects_anonymous",
    "network.broker_restore_candidate",
    "power.reboot_hold_hook",
    "power.candidate_staged_before_reboot",
    "power.ready_uncommitted",
    "rollback.candidate_lease_expired",
    "rollback.after_commit",
    "logs.serial",
    "local.lcd_continuity",
    "local.sensors_continuity",
    "local.rs485_continuity",
)


def _add_workspace(subparser: argparse.ArgumentParser) -> None:
    subparser.add_argument("--workspace", type=Path, required=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare and exercise a non-production ESP32-C6 MQTT board lab")
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan_parser = subparsers.add_parser("plan")
    _add_workspace(plan_parser)
    plan_parser.add_argument("--bind-host", default="127.0.0.1")
    plan_parser.add_argument("--port", type=int, default=18883)
    plan_parser.add_argument("--image", default=DEFAULT_IMAGE)

    create_parser = subparsers.add_parser("create")
    _add_workspace(create_parser)
    create_parser.add_argument("--confirmation", required=True)
    create_parser.add_argument("--bind-host", default="127.0.0.1")
    create_parser.add_argument("--port", type=int, default=18883)
    create_parser.add_argument("--image", default=DEFAULT_IMAGE)

    for command in (
        "start",
        "stop",
        "smoke-valid",
        "invalidate-candidate",
        "smoke-invalid",
        "restore-candidate",
        "destroy",
    ):
        _add_workspace(subparsers.add_parser(command))

    observe_parser = subparsers.add_parser("observe")
    _add_workspace(observe_parser)
    observe_parser.add_argument("--duration", type=float, required=True)
    observe_parser.add_argument("--output", type=Path, required=True)

    control_parser = subparsers.add_parser("control")
    _add_workspace(control_parser)
    control_parser.add_argument(
        "--control-command",
        choices=(
            "activate",
            "observe-success",
            "observe-failure",
            "commit",
            "rollback",
            "hold-reboot-anonymous",
            "release-reboot-anonymous",
            "hold-reboot-candidate",
            "release-reboot-candidate",
        ),
        required=True,
    )
    control_parser.add_argument("--confirmation", required=True)

    serial_parser = subparsers.add_parser("check-serial-log")
    _add_workspace(serial_parser)
    serial_parser.add_argument("--log", type=Path, required=True)

    matrix_parser = subparsers.add_parser("init-matrix")
    matrix_parser.add_argument("--output", type=Path, required=True)
    matrix_parser.add_argument("--run-id")

    summary_parser = subparsers.add_parser("summarize")
    summary_parser.add_argument("--records", type=Path, required=True)

    args = parser.parse_args(argv)
    try:
        if args.command == "plan":
            report = plan_board_lab(args.workspace, bind_host=args.bind_host, port=args.port, image=args.image)
        elif args.command == "create":
            report = create_board_lab(
                args.workspace,
                confirmation=args.confirmation,
                bind_host=args.bind_host,
                port=args.port,
                image=args.image,
            )
        elif args.command == "start":
            report = start_board_lab(args.workspace)
        elif args.command == "stop":
            report = stop_board_lab(args.workspace)
        elif args.command == "smoke-valid":
            report = smoke_valid(args.workspace)
        elif args.command == "invalidate-candidate":
            report = invalidate_candidate(args.workspace)
        elif args.command == "smoke-invalid":
            report = smoke_invalid(args.workspace)
        elif args.command == "restore-candidate":
            report = restore_candidate(args.workspace)
        elif args.command == "observe":
            report = observe_heartbeats(args.workspace, duration_s=args.duration, output=args.output)
        elif args.command == "control":
            report = send_control(
                args.workspace,
                command=args.control_command,
                confirmation=args.confirmation,
            )
        elif args.command == "check-serial-log":
            report = check_serial_log(args.workspace, log_path=args.log)
        elif args.command == "init-matrix":
            report = init_fault_matrix(args.output, run_id=args.run_id)
        elif args.command == "summarize":
            report = summarize_fault_matrix(args.records)
        elif args.command == "destroy":
            report = destroy_board_lab(args.workspace)
        else:
            raise NodeMqttBoardLabError("unsupported command")
    except (
        NodeMqttBoardLabError,
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        subprocess.SubprocessError,
        ValueError,
        RuntimeError,
    ) as error:
        print(f"Node MQTT board lab failed: {error}", file=sys.stderr)
        return 2
    print(_canonical_json(report))
    if args.command == "summarize" and report["status"] != "node_mqtt_board_lab_fault_matrix_succeeded":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
