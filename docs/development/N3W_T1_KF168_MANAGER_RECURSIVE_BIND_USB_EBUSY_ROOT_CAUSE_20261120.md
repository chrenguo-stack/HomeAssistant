# KF-168 live root cause: Manager recursive bind retains USB superblock

```text
STATUS=ROOT_CAUSE_REPRODUCED
PRODUCTION_AUTHORITY=false
PHASE_A_OVERALL=NOT_YET_PASS
ISOLATED_DIAGNOSTIC_AUTHORIZATION=CONSUMED_NO_REPLAY
ISOLATED_MOUNT_INVOCATION_COUNT=1
ISOLATED_MOUNT_RETURN_CODE=32
ISOLATED_MOUNT_STDERR_CLASS=device_busy
OTA_RESTART_COUNT=0
```

## Binding

- Prior live STOP archive: `0f50f0b98eefeb6780aca597ddd0da798251159d`, IPC `ERROR / ha_prepare_host_command_failed`.
- Diagnostic source review PR #809 head at rebind: `06332c58de850c590da83e0971d7576291f371b2`. No source was deployed by this diagnostic.
- Exact Host SHA-256: `4548f591d972576ea4d3f1f078cb55b483d1f63f2244b03c3413da1891e09d3f`, `U13B_ROLLED_BACK / ROLLED_BACK`.
- Exact bound removable ext4 partition verified by UUID, label, disk fingerprint, and non-root ancestry. Parent and isolated namespaces both saw it unmounted before the isolated mount command.

## Evidence and causal chain

1. The exact `mount -o ro,noload,nodev,nosuid,noexec` call in a newly private mount namespace returned exit 32 with a device-busy stderr classification. No mount succeeded and no unmount command was invoked in the diagnostic namespace.
2. Eleven mount namespaces were observed after the attempt. The bound ext4 device was absent from the host namespace and present in exactly one other observed namespace. Neither a direct block-device fd nor a sysfs holder was observed.
3. Docker container inspection proved the namespace owner was the Manager container, which has a read-only bind from `/run/n3w-t1-ota` to `/run/n3w/t1-ota`. The bound partition's mountinfo record is at the exact translated `media/<transaction-prefix>` path and exposes the full filesystem. The VFS mount flags are `ro` but the superblock flags are `rw`. The process start time was 2026-11-20T09:31:33.520000Z.
4. Docker includes existing submounts in a recursive directory bind by default. A read-only bind can retain a reference to a writable superblock. Linux rejects a fresh block filesystem mount with a mismatched `SB_RDONLY` state while that superblock is still held. This accounts for the reproduced device-busy failure and the earlier generic prepare-host error. [Docker bind documentation](https://docs.docker.com/engine/storage/bind-mounts/#recursive-mounts) · [Linux superblock implementation](https://code.googlesource.com/linux/torvalds/linux/%2B/d97ae6474ca0411bb8c2696e5764ec946dba43d0/fs/super.c)

The diagnostic ended with the bound USB still unmounted in the host namespace, identical Host transaction bytes, and the same OTA main PID. No device path, namespace ID, private connection information, subprocess output or secret is included. No container mount was removed, no service was restarted, and the hidden Manager mount remained present at observation.

## Repair boundary

Prevent Manager's IPC export from recursively retaining recovery media. The source design should isolate the socket export and recovery mount tree, preserve existing IPC ownership and client compatibility, and exercise a Linux bind/mount regression with disposable media. Keep strict `ro,noload` semantics. Recovery for the already-pinned live mount requires a separate reviewed and explicitly authorized operation. This document does not grant it.

## Spent diagnostic provenance

Local streamed probe SHA-256: `0024840fc0d86d742a4de698cdc8a5f0dea939a0d3cbb509f3d952a69b162ef7`. The source below is historical evidence of a consumed attempt.

<details>
<summary>Historical isolated probe</summary>

```text
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

STATE = Path("/var/lib/n3w-t1-core-updater")
TX = STATE / "homeassistant-usb-upgrade.json"
OTA = "n3w-t1-ha-ota.service"
TX_DIGEST = "4548f591d972576ea4d3f1f078cb55b483d1f63f2244b03c3413da1891e09d3f"
CHILD = r"""
import json, os, subprocess, sys

device, target, parent_namespace = sys.argv[1:]
result = {"mount_invocations": 0, "umount_invocations": 0}

def invoke(*argv):
    try:
        proc = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, timeout=20)
    except subprocess.TimeoutExpired:
        return None, b"", "timeout"
    stderr = proc.stderr.lower()
    categories = (
        ("permission_denied", (b"permission denied", b"operation not permitted")),
        ("device_busy", (b"busy", b"already mounted")),
        ("journal_recovery_required", (b"journal recovery", b"needs recovery")),
        ("mount_option_or_filesystem", (b"bad option", b"bad superblock", b"wrong fs type")),
        ("path_or_source_unavailable", (b"no such file", b"can't find", b"does not exist")),
        ("not_mounted", (b"not mounted",)),
    )
    reason = next((label for label, terms in categories if any(x in stderr for x in terms)), None)
    return proc.returncode, proc.stdout, reason or ("unclassified" if stderr else "no_stderr")

def main():
    assert os.stat("/proc/self/ns/mnt").st_ino != int(parent_namespace)
    assert not any(
        field.startswith(("shared:", "master:"))
        for line in open("/proc/self/mountinfo")
        for field in line.split(" - ", 1)[0].split()[6:]
    )
    result["namespace_private"] = True
    rc, out, reason = invoke("findmnt", "--noheadings", "--output", "TARGET", "--source", device)
    result["before_findmnt_rc"] = rc
    assert rc == 1 and not out and reason == "no_stderr"
    result["mount_invocations"] = 1
    rc, _, reason = invoke("mount", "-o", "ro,noload,nodev,nosuid,noexec", device, target)
    result.update(mount_rc=rc, mount_stderr_class=reason)
    if rc != 0:
        return
    try:
        rc, out, reason = invoke("findmnt", "--noheadings", "--output", "OPTIONS", "--source", device)
        options = set(out.decode().strip().split(","))
        result.update(findmnt_options_rc=rc, findmnt_options_stderr_class=reason,
                      observed_ro=rc == 0 and "ro" in options and "rw" not in options,
                      observed_noload=bool(options & {"noload", "norecovery"}))
        rc, out, reason = invoke("findmnt", "--noheadings", "--output", "SOURCE", "--target", target)
        result.update(findmnt_source_rc=rc, findmnt_source_stderr_class=reason,
                      source_exact=rc == 0 and out.decode().strip() == device)
    finally:
        result["umount_invocations"] = 1
        rc, _, reason = invoke("umount", target)
        result.update(umount_rc=rc, umount_stderr_class=reason)
        rc, out, reason = invoke("findmnt", "--noheadings", "--output", "TARGET", "--source", device)
        result.update(after_findmnt_rc=rc, after_unmounted=rc == 1 and not out and reason == "no_stderr")

try:
    main()
except Exception as error:
    result["guard_error_type"] = type(error).__name__
print(json.dumps(result), flush=True)
"""


def run(*args, input_bytes=None, timeout=15):
    return subprocess.run(
        args, input=input_bytes, capture_output=True, timeout=timeout, check=False
    )


def checked(*args):
    result = run(*args)
    assert result.returncode == 0
    return result.stdout.decode().strip()


def absent(device):
    result = run("findmnt", "--noheadings", "--output", "TARGET", "--source", device)
    return result.returncode == 1 and not result.stdout and not result.stderr


def main(result):
    assert os.geteuid() == 0
    before = TX.read_bytes()
    assert hashlib.sha256(before).hexdigest() == TX_DIGEST
    tx = json.loads(before)
    assert (tx["phase"], tx["status"]) == ("U13B_ROLLED_BACK", "ROLLED_BACK")
    assert tx["authorization_consumed"] is True
    result["host_baseline_exact"] = True
    device = checked("blkid", "-c", "/dev/null", "-t", "UUID=" + tx["usb_filesystem_uuid"], "-o", "device")
    assert re.fullmatch(r"/dev/[A-Za-z0-9_-]+", device)
    assert checked("blkid", "-c", "/dev/null", "-s", "TYPE", "-o", "value", device) == "ext4"
    assert checked("blkid", "-c", "/dev/null", "-s", "LABEL", "-o", "value", device) == "N3W-UPDATE"
    assert checked("blkid", "-c", "/dev/null", "-s", "UUID", "-o", "value", device).lower() == tx["usb_filesystem_uuid"].lower()
    assert Path("/etc/mtab").is_symlink()
    assert Path("/etc/mtab").resolve() == Path("/proc/self/mounts").resolve()
    sys.path.insert(0, str(STATE / "u9plus-fault-acceptance-r1/candidate-tools"))
    from n3w_t1_core_updater_ha_prepare_host import (
        SubprocessPrepareBackend, _flatten_blocks, _stable_fingerprint,
    )

    matches = [
        disk for disk in SubprocessPrepareBackend()._lsblk()
        if disk.get("type") == "disk"
        and any(node.get("path") == device for node in _flatten_blocks([disk]))
    ]
    assert len(matches) == 1
    disk = matches[0]
    root_mm = checked("findmnt", "--noheadings", "--output", "MAJ:MIN", "/")
    assert root_mm and root_mm not in {node.get("maj:min") for node in _flatten_blocks([disk])}
    assert str(disk.get("tran")).lower() == "usb" and disk.get("rm") in (1, True, "1")
    assert _stable_fingerprint(disk) == tx["usb_device_identity_public_fingerprint"]
    target = Path("/run/n3w-t1-ota/media") / tx["transaction_id_sha256"][:16]
    assert target.is_dir() and target.resolve() == target
    assert target.stat().st_uid == 0 and not target.stat().st_mode & 0o077
    assert absent(device)
    assert checked("systemctl", "is-active", OTA) == "active"
    pid = checked("systemctl", "show", "-p", "MainPID", "--value", OTA)
    assert pid.isdigit() and int(pid) > 0
    parent_ns = os.stat("/proc/self/ns/mnt").st_ino
    assert os.stat(f"/proc/{pid}/ns/mnt").st_ino == parent_ns
    result["bound_usb_verified"] = True
    child = run(
        "unshare", "--mount", "--propagation", "private",
        "python3", "-I", "-B", "-", device, str(target), str(parent_ns),
        input_bytes=CHILD.encode(), timeout=110,
    )
    result["unshare_rc"] = child.returncode
    if child.stdout:
        result["isolated"] = json.loads(child.stdout)
    result["global_usb_unmounted"] = absent(device)
    result["host_transaction_unchanged"] = TX.read_bytes() == before
    result["ota_pid_unchanged"] = checked("systemctl", "show", "-p", "MainPID", "--value", OTA) == pid
    assert all(result[k] for k in ("global_usb_unmounted", "host_transaction_unchanged", "ota_pid_unchanged"))
    assert child.returncode == 0 and "guard_error_type" not in result["isolated"]
    result["status"] = "OBSERVED"


output = {"diagnostic": "KF168_ISOLATED_USB_READONLY_MOUNT"}
try:
    main(output)
except Exception as error:
    output.update(status="STOP", error_type=type(error).__name__)
    print(json.dumps(output, sort_keys=True))
    sys.exit(1)
print(json.dumps(output, sort_keys=True))
```

</details>
