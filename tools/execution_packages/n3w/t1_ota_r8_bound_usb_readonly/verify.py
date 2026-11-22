#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
from pathlib import Path

EXPECTED_PREFLIGHT_HEAD = "decbb0cf5f3b16b90f4d324796cc701e84260191"
EXPECTED_TRANSACTION_SHA256 = "a427bef98d2886234bf706eb1347f09148429e44c79ab08f01e1071dd0722492"
EXPECTED_DEVICE = "/dev/sda1"
EXPECTED_MAJOR_MINOR = "8:1"
EXPECTED_CURRENT_VERSION = "2026.10.4"
EXPECTED_ROLLBACK_STATUS = "CURRENT_2026_10_4_ROLLBACK_MATERIALS_VERIFIED"
PRIVATE_MOUNTPOINT = "/mnt"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _preflight_source() -> str:
    path = (
        Path(__file__).resolve().parents[1]
        / "t1_ota_r8_spare_preflight"
        / "preflight.py"
    )
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("r8_preflight_source_missing")
    return path.read_text(encoding="utf-8")


def _load_preflight_module():
    import importlib.util

    path = (
        Path(__file__).resolve().parents[1]
        / "t1_ota_r8_spare_preflight"
        / "preflight.py"
    )
    spec = importlib.util.spec_from_file_location("n3w_r8_spare_preflight", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("r8_preflight_import_unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _parse_report(stdout: str) -> dict[str, object]:
    candidates = []
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                candidates.append(value)
    if len(candidates) != 1:
        raise RuntimeError("isolated_usb_report_not_unique")
    return candidates[0]


def validate_report(report: dict[str, object]) -> None:
    if report.get("status") != "R8_SPARE_READONLY_PREFLIGHT_COLLECTED":
        raise RuntimeError("isolated_usb_preflight_status_invalid")
    if report.get("errors") != {}:
        raise RuntimeError("isolated_usb_preflight_errors_present")
    if report.get("transactions_stable") is not True:
        raise RuntimeError("isolated_usb_transaction_drift")

    runtime = report.get("runtime")
    if not isinstance(runtime, dict):
        raise RuntimeError("isolated_usb_runtime_missing")
    if (
        runtime.get("homeassistant_version") != EXPECTED_CURRENT_VERSION
        or runtime.get("diagnostic_only") is not False
        or runtime.get("listeners_match") is not True
        or runtime.get("references_match_compose") is not True
    ):
        raise RuntimeError("isolated_usb_runtime_drift")

    transactions = report.get("transactions")
    if not isinstance(transactions, dict):
        raise RuntimeError("isolated_usb_transactions_missing")
    ha = transactions.get("homeassistant_usb")
    if (
        not isinstance(ha, dict)
        or ha.get("status") != "ROLLED_BACK"
        or ha.get("sha256") != EXPECTED_TRANSACTION_SHA256
    ):
        raise RuntimeError("isolated_usb_transaction_binding_drift")

    bound = report.get("bound_usb")
    if (
        not isinstance(bound, dict)
        or bound.get("status") != "BOUND_USB_PRESENT"
        or bound.get("device") != EXPECTED_DEVICE
        or bound.get("major_minor") != EXPECTED_MAJOR_MINOR
        or bound.get("filesystem") != "ext4"
        or bound.get("transaction_sha256") != EXPECTED_TRANSACTION_SHA256
    ):
        raise RuntimeError("isolated_usb_device_binding_drift")
    mounts = bound.get("mounts")
    if (
        not isinstance(mounts, list)
        or len(mounts) != 1
        or not isinstance(mounts[0], dict)
        or mounts[0].get("target") != PRIVATE_MOUNTPOINT
    ):
        raise RuntimeError("isolated_usb_private_mount_not_observed")

    usb = report.get("usb")
    if (
        not isinstance(usb, dict)
        or usb.get("status") != "OBSERVED"
        or usb.get("filesystem") != "ext4"
        or usb.get("read_only") is not True
    ):
        raise RuntimeError("isolated_usb_readonly_contract_invalid")

    rollback = report.get("rollback_materials")
    if (
        not isinstance(rollback, dict)
        or rollback.get("status") != EXPECTED_ROLLBACK_STATUS
    ):
        raise RuntimeError("isolated_usb_rollback_materials_not_verified")

    capacity = report.get("capacity_policy")
    if (
        not isinstance(capacity, dict)
        or capacity.get("decision_point") != "AFTER_RELEASE_BEFORE_NEXT_IMPORT"
        or capacity.get("capacity_decision") != "DEFER_UNTIL_POST_RELEASE_MEASUREMENT"
        or capacity.get("post_release_available_bytes") is not None
    ):
        raise RuntimeError("isolated_usb_capacity_policy_drift")


def _host_mount_state(transport) -> bool:
    result = transport.run_remote(
        (
            "findmnt",
            "--list",
            "--source",
            EXPECTED_DEVICE,
            "--output",
            "TARGET",
            "--noheadings",
        ),
        timeout=20,
        check=False,
    )
    if result.returncode not in {0, 1}:
        raise RuntimeError("host_usb_mount_probe_failed")
    return result.returncode == 0


def _bootstrap(source: str, encoded_package: str) -> str:
    return f"""import subprocess
from pathlib import Path

SOURCE = {source!r}
PACKAGE = {encoded_package!r}
MOUNTPOINT = {PRIVATE_MOUNTPOINT!r}
DEVICE = {EXPECTED_DEVICE!r}

mountpoint = Path(MOUNTPOINT)
if mountpoint.is_symlink() or not mountpoint.is_dir():
    raise SystemExit("isolated_mountpoint_invalid")
probe = subprocess.run(
    ["findmnt", "--mountpoint", MOUNTPOINT],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    check=False,
    timeout=10,
)
if probe.returncode == 0:
    raise SystemExit("isolated_mountpoint_preoccupied")
if probe.returncode != 1:
    raise SystemExit("isolated_mountpoint_probe_failed")
subprocess.run(
    [
        "mount", "--internal-only", "-t", "ext4",
        "-o", "ro,noload,nodev,nosuid,noexec",
        "--", DEVICE, MOUNTPOINT,
    ],
    check=True,
    timeout=20,
)
rc = 1
try:
    namespace = {{
        "__name__": "__main__",
        "PACKAGE_ON_SPARE": PACKAGE,
        "USB_MOUNT": MOUNTPOINT,
    }}
    try:
        exec(compile(SOURCE, "<r8-spare-preflight>", "exec"), namespace)
    except SystemExit as exit_status:
        rc = int(exit_status.code or 0)
finally:
    subprocess.run(
        ["umount", "--", MOUNTPOINT],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=20,
    )
raise SystemExit(rc)
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True)
    parser.add_argument("--known-hosts", type=Path, required=True)
    parser.add_argument("--expected-host-key-sha256", required=True)
    parser.add_argument("--package", type=Path, required=True)
    args = parser.parse_args()

    repo = _repo_root()
    sys.path.insert(0, str(repo / "tools"))
    from n3w_t1_ssh_transport import SSHTransport

    preflight = _load_preflight_module()
    package = preflight.read_package(args.package)
    source = _preflight_source()
    payload = _bootstrap(
        source,
        base64.b64encode(package).decode("ascii"),
    )

    transport = SSHTransport(
        target=args.target,
        known_hosts=args.known_hosts,
        expected_host_key_sha256=args.expected_host_key_sha256,
    )
    try:
        epoch = transport.start_epoch()
        print(
            "SSH_HOST_KEY_BINDING=PASS "
            f"EPOCH={epoch['epoch']} "
            f"HOST_KEY_SHA256={epoch['host_key_sha256']}"
        )
        if _host_mount_state(transport):
            raise RuntimeError("host_usb_already_mounted")

        env = transport.managed_environment()
        command = (
            'if [ "$(id -u)" -eq 0 ]; then '
            'exec /usr/bin/unshare --mount --propagation private --fork '
            '/usr/bin/python3 -I -B -; '
            'else exec sudo -n /usr/bin/unshare --mount --propagation private --fork '
            '/usr/bin/python3 -I -B -; fi'
        )
        completed = subprocess.run(
            [
                "ssh",
                "-o",
                "StrictHostKeyChecking=yes",
                "-o",
                "ForwardAgent=no",
                "-o",
                "ClearAllForwardings=yes",
                "-o",
                "RequestTTY=no",
                "--",
                args.target,
                command,
            ],
            input=payload,
            text=True,
            capture_output=True,
            env=env,
            check=False,
            timeout=1800,
        )
        if completed.stdout:
            print(completed.stdout, end="")
        if completed.stderr:
            print(completed.stderr, file=sys.stderr, end="")
        if completed.returncode != 0:
            raise RuntimeError(
                f"isolated_usb_remote_failed:{completed.returncode}"
            )

        report = _parse_report(completed.stdout)
        validation_error = None
        try:
            validate_report(report)
        except Exception as error:
            validation_error = error

        if _host_mount_state(transport):
            raise RuntimeError("host_usb_mount_leaked") from validation_error
        print("HOST_USB_MOUNT_STATE=UNCHANGED_UNMOUNTED")
        print("EXT4_JOURNAL_REPLAY=DISABLED_BY_RO_NOLOAD")
        if validation_error is not None:
            raise validation_error
        print("CURRENT_2026_10_4_ROLLBACK_MATERIALS=VERIFIED")
        print("ISOLATED_USB_VERIFY=PASS")
        return 0
    finally:
        transport.close_epoch()


if __name__ == "__main__":
    raise SystemExit(main())
