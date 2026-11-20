from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

import n3w_t1_core_updater_ha_prepare_host as hostmod
from n3w_t1_core_updater_ha_prepare_host import SubprocessPrepareBackend
from n3w_t1_core_updater_v2_common import UpdaterV2Error
from test_n3w_t1_u13b_controller import USB_UUID, FINGERPRINT, origin_transaction
from n3w_t1_core_updater_ha_usb_state import U9


@pytest.mark.parametrize(
    ("command", "stderr", "expected"),
    [
        (
            ("mount", "-o", "ro,noload,nodev,nosuid,noexec", "/dev/private", "/private/media"),
            b"mount: /private/media: permission denied",
            "tool=mount operation=strict_readonly exit_code=32 reason=permission_denied",
        ),
        (
            ("findmnt", "--noheadings", "--output", "OPTIONS", "--source", "/dev/private"),
            b"",
            "tool=findmnt operation=options exit_code=32 reason=unclassified",
        ),
        (
            ("umount", "/private/media"),
            b"umount: /private/media: target is busy",
            "tool=umount operation=default exit_code=32 reason=device_busy",
        ),
    ],
)
def test_usb_command_failure_logs_redacted_context(
    monkeypatch, caplog, command, stderr, expected
):
    def run(argv, **_kwargs):
        return subprocess.CompletedProcess(argv, 32, b"private stdout", stderr)

    monkeypatch.setattr(hostmod.subprocess, "run", run)
    with pytest.raises(UpdaterV2Error, match="^ha_prepare_host_command_failed$"):
        hostmod._run(command)
    assert expected in caplog.text
    assert "/private" not in caplog.text
    assert "private stdout" not in caplog.text


def disk(mount_path=None):
    points = [] if mount_path is None else [str(mount_path)]
    return {
        "type": "disk",
        "path": "/dev/sdz",
        "tran": "usb",
        "rm": 1,
        "ro": 0,
        "size": 20 * 1024**3,
        "model": "TEST USB",
        "serial": "SERIAL",
        "wwn": "",
        "maj:min": "8:32",
        "mountpoints": points,
        "children": [{
            "type": "part",
            "path": "/dev/sdz1",
            "maj:min": "8:33",
            "mountpoints": points,
        }],
    }


def backend(tmp_path, observed_disk):
    runtime_root = tmp_path / "run"
    runtime_root.mkdir(mode=0o700, exist_ok=True)
    runtime_root.chmod(0o700)
    mount_root = runtime_root / "media"
    if mount_root.exists():
        mount_root.chmod(0o700)
    value = SubprocessPrepareBackend(runtime_root=runtime_root)
    value._lsblk = lambda: [observed_disk]
    value._filesystem_space = lambda path: (20 * 1024**3, 10 * 1024**3)
    value._require_bound_media = lambda media: "/dev/sdz1"
    return value


def install_commands(
    monkeypatch,
    mount_path,
    *,
    already_mounted,
    options,
    options_after_mount=None,
):
    calls = []
    state = {"mounted": False}

    def run(argv, **kwargs):
        calls.append(tuple(argv))
        if tuple(argv) == (
            "findmnt", "--noheadings", "--output", "MAJ:MIN", "/"
        ):
            return b"8:1\n"
        if tuple(argv) == (
            "findmnt", "--noheadings", "--output", "OPTIONS",
            "--source", "/dev/sdz1",
        ):
            value = (
                options_after_mount
                if state["mounted"] and options_after_mount is not None
                else options
            )
            return (value + "\n").encode()
        if argv and argv[0] == "mount":
            state["mounted"] = True
            return b""
        if argv and argv[0] == "umount":
            return b""
        raise AssertionError(f"unexpected command: {argv!r}")

    def optional(argv, **kwargs):
        key = tuple(argv)
        if key == ("blkid", "-s", "TYPE", "-o", "value", "/dev/sdz1"):
            return b"ext4\n"
        if key == ("blkid", "-s", "LABEL", "-o", "value", "/dev/sdz1"):
            return b"N3W-UPDATE\n"
        if key == ("blkid", "-s", "UUID", "-o", "value", "/dev/sdz1"):
            return (USB_UUID + "\n").encode()
        if key == (
            "findmnt", "--noheadings", "--output", "TARGET",
            "--source", "/dev/sdz1",
        ):
            return (
                (str(mount_path) + "\n").encode()
                if already_mounted else None
            )
        raise AssertionError(f"unexpected optional command: {argv!r}")

    monkeypatch.setattr(hostmod, "_run", run)
    monkeypatch.setattr(hostmod, "_run_optional", optional)
    return calls


def test_reconciliation_resolver_mounts_unmounted_usb_ro_noload(
    tmp_path, monkeypatch
):
    transaction = origin_transaction(U9)
    mount_path = (
        tmp_path / "run" / "media"
        / transaction["transaction_id_sha256"][:16]
    )
    observed = disk()
    value = backend(tmp_path, observed)
    calls = install_commands(
        monkeypatch,
        mount_path,
        already_mounted=False,
        options="ro,nosuid,nodev,noexec,relatime",
    )

    media = value.resolve_transaction_media_for_reconciliation(transaction)
    assert media is not None
    assert media.filesystem_uuid == USB_UUID
    assert media.public_fingerprint == FINGERPRINT or len(
        media.public_fingerprint
    ) == 64
    assert (
        "mount",
        "-o",
        "ro,noload,nodev,nosuid,noexec",
        "/dev/sdz1",
        str(mount_path),
    ) in calls


def test_reconciliation_resolver_accepts_existing_exact_ro_mount(
    tmp_path, monkeypatch
):
    transaction = origin_transaction(U9)
    mount_path = (
        tmp_path / "run" / "media"
        / transaction["transaction_id_sha256"][:16]
    )
    mount_path.mkdir(parents=True, mode=0o700)
    value = backend(tmp_path, disk(mount_path))
    calls = install_commands(
        monkeypatch,
        mount_path,
        already_mounted=True,
        options="ro,nosuid,nodev,noexec,relatime",
    )
    assert value.resolve_transaction_media_for_reconciliation(
        transaction
    ) is not None
    assert not any(call and call[0] == "mount" for call in calls)


def test_reconciliation_resolver_replaces_existing_rw_mount_with_strict_ro(
    tmp_path, monkeypatch
):
    transaction = origin_transaction(U9)
    mount_path = (
        tmp_path / "run" / "media"
        / transaction["transaction_id_sha256"][:16]
    )
    mount_path.mkdir(parents=True, mode=0o700)
    value = backend(tmp_path, disk(mount_path))
    calls = install_commands(
        monkeypatch,
        mount_path,
        already_mounted=True,
        options="rw,nosuid,nodev,noexec,relatime",
        options_after_mount="ro,nosuid,nodev,noexec,relatime",
    )
    media = value.resolve_transaction_media_for_reconciliation(transaction)
    assert media is not None
    assert ("umount", str(mount_path)) in calls
    assert (
        "mount",
        "-o",
        "ro,noload,nodev,nosuid,noexec",
        "/dev/sdz1",
        str(mount_path),
    ) in calls



def test_reconciliation_release_unmounts_ro_product_mount(
    tmp_path, monkeypatch
):
    transaction = origin_transaction(U9)
    mount_path = (
        tmp_path / "run" / "media"
        / transaction["transaction_id_sha256"][:16]
    )
    mount_path.mkdir(parents=True, mode=0o700)
    value = backend(tmp_path, disk(mount_path))
    calls = install_commands(
        monkeypatch,
        mount_path,
        already_mounted=True,
        options="ro,nosuid,nodev,noexec,relatime",
    )
    observed = value.resolve_transaction_media_for_reconciliation(
        transaction
    )
    assert observed is not None
    value.release_transaction_media_for_reconciliation(observed)
    assert ("umount", str(mount_path)) in calls
