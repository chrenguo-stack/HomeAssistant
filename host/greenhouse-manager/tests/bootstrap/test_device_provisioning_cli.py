from __future__ import annotations

import io
import json
from pathlib import Path

from greenhouse_manager.bootstrap.device_firstboot import PROVISIONING_CONFIRMATION
from greenhouse_manager.bootstrap.device_provisioning_cli import main


class FakeController:
    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []

    def inspect(
        self,
        transaction_root: Path,
        candidate_root: Path,
        *,
        release_id: str,
    ):
        self.calls.append(
            ("inspect", transaction_root, candidate_root, release_id)
        )
        return {
            "status": "PASS",
            "state": "UNPROVISIONED",
            "release_id": release_id,
        }

    def start(
        self,
        transaction_root: Path,
        candidate_root: Path,
        *,
        release_id: str,
        confirmation: str,
    ):
        self.calls.append(
            (
                "start",
                transaction_root,
                candidate_root,
                release_id,
                confirmation,
            )
        )
        return {
            "status": "PASS",
            "state": "DEVICE_READY",
            "release_id": release_id,
        }


def args(command: str, *extra: str) -> list[str]:
    return [
        "--transaction-root",
        "/var/lib/n3w-firstboot",
        "--candidate-root",
        "/var/lib/n3w-firstboot/candidate",
        "--release-id",
        "release-1",
        command,
        *extra,
    ]


def test_status_is_read_only_controller_route() -> None:
    controller = FakeController()
    output = io.StringIO()

    code = main(
        args("status"),
        controller=controller,
        output=output,
        error_output=io.StringIO(),
    )

    document = json.loads(output.getvalue())
    assert code == 0
    assert document["schema"] == "gh.n3w.t1-device-provisioning-cli/1"
    assert document["state"] == "UNPROVISIONED"
    assert document["production_service_start"] is False
    assert controller.calls == [
        (
            "inspect",
            Path("/var/lib/n3w-firstboot"),
            Path("/var/lib/n3w-firstboot/candidate"),
            "release-1",
        )
    ]


def test_start_rejects_wrong_confirmation_before_controller_call() -> None:
    controller = FakeController()
    errors = io.StringIO()

    code = main(
        args("start", "--confirm", "YES"),
        controller=controller,
        output=io.StringIO(),
        error_output=errors,
    )

    document = json.loads(errors.getvalue())
    assert code == 2
    assert document["error_code"] == "provisioning_confirmation_invalid"
    assert document["confirmation_required"] == PROVISIONING_CONFIRMATION
    assert controller.calls == []


def test_start_routes_exact_confirmation_without_reboot_semantics() -> None:
    controller = FakeController()
    output = io.StringIO()

    code = main(
        args("start", "--confirm", PROVISIONING_CONFIRMATION),
        controller=controller,
        output=output,
        error_output=io.StringIO(),
    )

    document = json.loads(output.getvalue())
    assert code == 0
    assert document["state"] == "DEVICE_READY"
    assert document["production_service_start"] is False
    assert controller.calls == [
        (
            "start",
            Path("/var/lib/n3w-firstboot"),
            Path("/var/lib/n3w-firstboot/candidate"),
            "release-1",
            PROVISIONING_CONFIRMATION,
        )
    ]


def test_cli_without_host_adapter_fails_closed() -> None:
    errors = io.StringIO()

    code = main(
        args("status"),
        output=io.StringIO(),
        error_output=errors,
    )

    document = json.loads(errors.getvalue())
    assert code == 2
    assert document["error_code"] == "host_adapter_required"
    assert document["production_service_start"] is False
