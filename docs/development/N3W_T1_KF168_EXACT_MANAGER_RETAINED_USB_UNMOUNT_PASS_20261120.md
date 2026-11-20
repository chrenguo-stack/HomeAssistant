# KF-168 exact retained Manager USB mount cleanup

```text
STATUS=PASS_CLEANUP_ONLY
AUTHORIZATION=CONSUMED_NO_REPLAY
MANAGER_NAMESPACE_UMOUNT_INVOCATIONS=1
UMOUNT_RETURN=0
UMOUNT_ERRNO=0
MANAGER_RESTART_COUNT=0
OTA_RESTART_COUNT=0
HOST_TRANSACTION_UNCHANGED=true
PHASE_A_OVERALL=NOT_YET_PASS
PRODUCTION_AUTHORITY=false
```

Root-cause authority: [Manager recursive bind and isolated EBUSY reproduction](https://github.com/chrenguo-stack/HomeAssistant/blob/b726c7d14732e4a73568ada4c0ad29a59a2f8e27/docs/development/N3W_T1_KF168_MANAGER_RECURSIVE_BIND_USB_EBUSY_ROOT_CAUSE_20261120.md).

With fresh explicit operator authorization, the executor verified the exact current removable ext4 disk fingerprint and UUID, the Manager container, its read-only OTA runtime bind, and the single private ext4 submount corresponding to the bound partition and transaction target. It pinned the Manager mount namespace and container root by descriptors, checked the kernel mount ID again inside that namespace, and issued exactly one normal `umount2` with `UMOUNT_NOFOLLOW`. Force, lazy unmount, remount, retries, USB metadata writes and service restart commands were outside the execution.

At 2026-11-20T10:42:37Z, the exact retained mount was absent in Manager and there were zero bound-partition mounts across 11 inspected mount namespaces. The ext4 superblock read-only probe returned zero and the pre-existing `needs_recovery` flag was no longer reported following the normal final unmount. No test mount was issued as part of cleanup.

- Host transaction remained byte-identical at SHA-256 `4548f591d972576ea4d3f1f078cb55b483d1f63f2244b03c3413da1891e09d3f`, `U13B_ROLLED_BACK / ROLLED_BACK`.
- Manager container and PID unchanged; OTA main PID unchanged; candidate override active, exact candidate U13B Host blob `437f3e6c4cae53f7d94e244cd312ac454768f8e1`.
- U11 supervision, container counts 1/1/1, exact listeners, both MQTT authentications and HA HTTP 401 verified.
- IPC queried as UID/GID 999:999 still returned the earlier terminal `ERROR / ha_prepare_host_command_failed`. The observer PASS meant the cleanup baseline was intact; the product completion oracle was not rerun.
- The persistent prevention boundary remains separate: isolate the Manager IPC export from USB recovery submounts and regress both container start during recovery and strict read-only completion. Any later OTA restart or deployment requires a separately scoped authorization.

Historical streamed executor SHA-256 `3cf44764b101ed341be05c0218331d2f0bb76a8b7315038511374843d03d7f78`. The text below is retained solely as evidence of the consumed cleanup.

<details>
<summary>Historical exact-unmount executor</summary>

```text
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

STATE = Path("/var/lib/n3w-t1-core-updater")
TRANSACTION = STATE / "homeassistant-usb-upgrade.json"
EXPECTED_SHA256 = "4548f591d972576ea4d3f1f078cb55b483d1f63f2244b03c3413da1891e09d3f"
OTA = "n3w-t1-ha-ota.service"
HOST_RUNTIME = "/run/n3w-t1-ota"
MANAGER_RUNTIME = "/run/n3w/t1-ota"
libc = ctypes.CDLL(None, use_errno=True)
libc.setns.argtypes = (ctypes.c_int, ctypes.c_int)
libc.umount2.argtypes = (ctypes.c_char_p, ctypes.c_int)
UMOUNT_NOFOLLOW = 8


def cmd(*args):
    return subprocess.check_output(
        args, stdin=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=20
    ).decode().strip()


def manager_identity():
    cid = cmd(
        "docker", "ps", "-q", "--filter", "label=com.docker.compose.project=n3wfc4",
        "--filter", "label=com.docker.compose.service=manager",
    )
    assert re.fullmatch(r"[0-9a-f]{12,64}", cid)
    value = json.loads(cmd("docker", "inspect", "-f", "{{json .State}}", cid))
    assert value["Running"] is True and isinstance(value["Pid"], int) and value["Pid"] > 0
    return cid, value["Pid"]


def parse_mounts(rows):
    mounts = []
    for line in rows.splitlines():
        before, sep, after = line.partition(" - ")
        if not sep:
            raise ValueError("mountinfo_invalid")
        fields = before.split()
        fs, _source, super_options = after.split()
        mounts.append((
            int(fields[0]), fields[2], fields[3], fields[4],
            set(fields[5].split(",")), fields[6:], fs, set(super_options.split(",")),
        ))
    return mounts


def snapshot(rows, target, major_minor):
    mounts = parse_mounts(rows)
    expected = [row for row in mounts if row[3] == target]
    assert len(expected) == 1
    value = expected[0]
    assert [row for row in mounts if row[1] == major_minor] == expected
    assert value[1] == major_minor and value[2] == "/" and value[6] == "ext4"
    assert "ro" in value[4] and "rw" in value[7]
    assert not any(field.startswith(("shared:", "master:")) for field in value[5])
    return value[0]


def child_unmount(ns_fd, root_fd, proc_fd, target, mm, mount_id, result_fd):
    report = {"unmount_invocations": 0}
    try:
        assert libc.setns(ns_fd, 0) == 0
        os.fchdir(root_fd)
        os.chroot(".")
        os.chdir("/")
        with os.fdopen(os.open("self/mountinfo", os.O_RDONLY, dir_fd=proc_fd)) as mountinfo:
            assert snapshot(mountinfo.read(), target, mm) == mount_id
        report["unmount_invocations"] = 1
        outcome = libc.umount2(os.fsencode(target), UMOUNT_NOFOLLOW)
        report["unmount_rc"] = outcome
        report["unmount_errno"] = ctypes.get_errno() if outcome else 0
    except Exception as error:
        report["guard_error_type"] = type(error).__name__
    os.write(result_fd, json.dumps(report).encode())
    os._exit(0)


def main(result):
    assert os.geteuid() == 0
    original = TRANSACTION.read_bytes()
    assert hashlib.sha256(original).hexdigest() == EXPECTED_SHA256
    tx = json.loads(original)
    assert (tx["phase"], tx["status"]) == ("U13B_ROLLED_BACK", "ROLLED_BACK")
    assert tx["authorization_consumed"] is True
    device = cmd("blkid", "-c", "/dev/null", "-t", "UUID=" + tx["usb_filesystem_uuid"], "-o", "device")
    assert re.fullmatch(r"/dev/[A-Za-z0-9_-]+", device)
    assert cmd("blkid", "-c", "/dev/null", "-s", "TYPE", "-o", "value", device) == "ext4"
    assert cmd("blkid", "-c", "/dev/null", "-s", "LABEL", "-o", "value", device) == "N3W-UPDATE"
    device_stat = os.stat(device)
    assert stat.S_ISBLK(device_stat.st_mode)
    mm = f"{os.major(device_stat.st_rdev)}:{os.minor(device_stat.st_rdev)}"
    parent = Path("/sys/dev/block", mm).resolve().parent
    root_mm = cmd("findmnt", "--noheadings", "--output", "MAJ:MIN", "/")
    assert root_mm not in {mm, (parent / "dev").read_text().strip()}
    sys.path.insert(0, str(STATE / "u9plus-fault-acceptance-r1/candidate-tools"))
    from n3w_t1_core_updater_ha_prepare_host import (
        SubprocessPrepareBackend, _flatten_blocks, _stable_fingerprint,
    )
    disks = [
        disk for disk in SubprocessPrepareBackend()._lsblk()
        if disk.get("type") == "disk"
        and any(node.get("path") == device for node in _flatten_blocks([disk]))
    ]
    assert len(disks) == 1
    assert str(disks[0].get("tran")).lower() == "usb" and disks[0].get("rm") in (1, True, "1")
    assert _stable_fingerprint(disks[0]) == tx["usb_device_identity_public_fingerprint"]
    assert not any(row[1] == mm for row in parse_mounts(Path("/proc/self/mountinfo").read_text()))
    ota_pid = cmd("systemctl", "show", "-p", "MainPID", "--value", OTA)
    assert cmd("systemctl", "is-active", OTA) == "active" and int(ota_pid) > 0
    assert cmd("systemctl", "is-active", "n3wfc4-services-activation.service") == "active"
    assert cmd("systemctl", "is-active", "n3wfc4-broker-activation.service") == "active"
    cid, manager_pid = manager_identity()
    exports = json.loads(cmd("docker", "inspect", "-f", "{{json .Mounts}}", cid))
    expected_export = [
        mount for mount in exports
        if mount.get("Type") == "bind" and mount.get("Source") == HOST_RUNTIME
        and mount.get("Destination") == MANAGER_RUNTIME and mount.get("RW") is False
    ]
    assert len(expected_export) == 1
    prefix = tx["transaction_id_sha256"][:16]
    assert re.fullmatch(r"[0-9a-f]{16}", prefix)
    target = f"{MANAGER_RUNTIME}/media/{prefix}"
    manager_proc = Path("/proc") / str(manager_pid)
    mount_id = snapshot((manager_proc / "mountinfo").read_text(), target, mm)
    ns_fd = os.open(manager_proc / "ns/mnt", os.O_RDONLY)
    root_fd = os.open(manager_proc / "root", os.O_RDONLY | os.O_DIRECTORY)
    proc_fd = os.open("/proc", os.O_RDONLY | os.O_DIRECTORY)
    assert os.fstat(ns_fd).st_ino != os.stat("/proc/self/ns/mnt").st_ino
    assert os.fstat(ns_fd).st_ino == (manager_proc / "ns/mnt").stat().st_ino
    assert os.stat(target.lstrip("/"), dir_fd=root_fd).st_dev == device_stat.st_rdev
    assert manager_identity() == (cid, manager_pid)
    assert TRANSACTION.read_bytes() == original
    result["exact_manager_mount_verified"] = True

    receiver, sender = os.pipe()
    worker = os.fork()
    if worker == 0:
        os.close(receiver)
        child_unmount(ns_fd, root_fd, proc_fd, target, mm, mount_id, sender)
    os.close(sender)
    with os.fdopen(receiver, "rb") as note:
        payload = note.read()
    _, worker_status = os.waitpid(worker, 0)
    for fd in (proc_fd, root_fd, ns_fd):
        os.close(fd)
    assert worker_status == 0 and payload
    result.update(json.loads(payload))
    result["manager_unchanged"] = manager_identity() == (cid, manager_pid)
    result["ota_pid_unchanged"] = cmd("systemctl", "show", "-p", "MainPID", "--value", OTA) == ota_pid
    result["host_transaction_unchanged"] = TRANSACTION.read_bytes() == original
    result["host_usb_unmounted"] = not any(
        row[1] == mm for row in parse_mounts(Path("/proc/self/mountinfo").read_text())
    )
    result["manager_usb_mount_absent"] = not any(
        row[1] == mm or row[3] == target
        for row in parse_mounts((manager_proc / "mountinfo").read_text())
    )
    assert result.get("unmount_invocations") == 1 and result.get("unmount_rc") == 0
    assert all(result[key] for key in (
        "manager_unchanged", "ota_pid_unchanged", "host_transaction_unchanged",
        "host_usb_unmounted", "manager_usb_mount_absent",
    ))
    result["status"] = "PASS"


result = {"operation": "KF168_EXACT_MANAGER_RETAINED_USB_UNMOUNT", "unmount_invocations": 0}
try:
    main(result)
except Exception as error:
    result.update(status="STOP", error_type=type(error).__name__)
    print(json.dumps(result, sort_keys=True))
    sys.exit(1)
print(json.dumps(result, sort_keys=True))
```

</details>
