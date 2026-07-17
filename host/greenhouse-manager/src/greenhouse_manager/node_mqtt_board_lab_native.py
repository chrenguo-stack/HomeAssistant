from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from .node_mqtt_board_lab_broker import _wait_for_port
from .node_mqtt_board_lab_common import NodeMqttBoardLabError, _canonical_json
from .node_mqtt_board_lab_matrix import init_fault_matrix, summarize_fault_matrix
from .node_mqtt_board_lab_mqtt import (
    check_serial_log,
    observe_heartbeats,
    send_control,
    smoke_invalid,
    smoke_valid,
)
from .node_mqtt_board_lab_native_broker import (
    create_native_board_lab,
    destroy_native_board_lab,
    invalidate_native_candidate,
    plan_native_board_lab,
    restore_native_candidate,
    start_native_board_lab,
    stop_native_board_lab,
)


def _add_workspace(subparser: argparse.ArgumentParser) -> None:
    subparser.add_argument("--workspace", type=Path, required=True)


def _add_native_tools(subparser: argparse.ArgumentParser) -> None:
    subparser.add_argument("--mosquitto-bin", default="mosquitto")
    subparser.add_argument("--mosquitto-passwd-bin", default="mosquitto_passwd")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Prepare and exercise a native non-production ESP32-C6 MQTT board lab"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan_parser = subparsers.add_parser("plan")
    _add_workspace(plan_parser)
    _add_native_tools(plan_parser)
    plan_parser.add_argument("--bind-host", default="127.0.0.1")
    plan_parser.add_argument("--port", type=int, default=18883)

    create_parser = subparsers.add_parser("create")
    _add_workspace(create_parser)
    _add_native_tools(create_parser)
    create_parser.add_argument("--confirmation", required=True)
    create_parser.add_argument("--bind-host", default="127.0.0.1")
    create_parser.add_argument("--port", type=int, default=18883)

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
            report = plan_native_board_lab(
                args.workspace,
                bind_host=args.bind_host,
                port=args.port,
                mosquitto_bin=args.mosquitto_bin,
                mosquitto_passwd_bin=args.mosquitto_passwd_bin,
            )
        elif args.command == "create":
            report = create_native_board_lab(
                args.workspace,
                confirmation=args.confirmation,
                bind_host=args.bind_host,
                port=args.port,
                mosquitto_bin=args.mosquitto_bin,
                mosquitto_passwd_bin=args.mosquitto_passwd_bin,
                waiter=_wait_for_port,
            )
        elif args.command == "start":
            report = start_native_board_lab(args.workspace, waiter=_wait_for_port)
        elif args.command == "stop":
            report = stop_native_board_lab(args.workspace)
        elif args.command == "smoke-valid":
            report = smoke_valid(args.workspace)
        elif args.command == "invalidate-candidate":
            report = invalidate_native_candidate(args.workspace, waiter=_wait_for_port)
        elif args.command == "smoke-invalid":
            report = smoke_invalid(args.workspace)
        elif args.command == "restore-candidate":
            report = restore_native_candidate(args.workspace, waiter=_wait_for_port)
        elif args.command == "observe":
            report = observe_heartbeats(
                args.workspace,
                duration_s=args.duration,
                output=args.output,
            )
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
            report = destroy_native_board_lab(args.workspace)
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
        print(f"Native node MQTT board lab failed: {error}", file=sys.stderr)
        return 2
    print(_canonical_json(report))
    if args.command == "summarize" and report["status"] != "node_mqtt_board_lab_fault_matrix_succeeded":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
