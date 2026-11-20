# N3-W T1 U9+ Phase-A authorized restart-convergence revalidation

```text
ARCHIVE_STATUS=EVIDENCE_ONLY
PRODUCTION_AUTHORITY=false
LIVE_REVALIDATION=STOP
PHASE_A_OVERALL=NOT_YET_PASS
LIVE_RETRY_AUTHORIZATION=CONSUMED_NO_REPLAY
CANDIDATE_SOURCE_REPLACED=true
OTA_RESTART_INVOCATION_COUNT=1
OTA_RESTART_COMMAND_COMPLETED=true
IPC_PHASE=ERROR
IPC_ERROR_CODE=ha_prepare_host_command_failed
IPC_QUERY_UID_GID=999:999
```

## Exact binding and execution

- Preflight archive commit: `a1d0e5634375bd2efc9d4b81fb9a4c565ea0c38f`. Fresh preflight passed at 2026-11-20T09:29:34.719208Z and passed again inside the one-shot wrapper before replacement.
- Repository main `3e7faf258d670c9eaf3be6ede9bbb02df2ac009d`, PR #807/branch `7811b6bc2fc3cdc5b1cecb45549cb81b6d80784c`, CI authority `3d74881e3bfadbecd23721f8c9d500f95ef69696` (22/22 success).
- Old blob `a103a2633aaea5a34efbfed35449b2eb5bace61b` is recoverable from `93610f23472759cf1601d2ad82b9b59b7225f4d6`. Installed candidate U13B Host blob: `437f3e6c4cae53f7d94e244cd312ac454768f8e1`. The bound diff is deletion of the premature pre-loop health check.
- The candidate was replaced atomically. The sole restart command completed and systemd reported active from 2026-11-20 17:31:30 CST (09:31:30 UTC). The observer terminated on the new IPC error. Retirement/rollback of the new candidate requires a separately scoped decision.
- No second restart was issued. The wrapper did not invoke U9, U10, U11+, transaction writes, USB commands, or production source replacement.

## Fresh observation after STOP

At 2026-11-20T09:35:46.345774Z the read-only probe proved the expected STOP state:

- Host `U13B_ROLLED_BACK / ROLLED_BACK`; exact Host transaction SHA-256 unchanged at `4548f591d972576ea4d3f1f078cb55b483d1f63f2244b03c3413da1891e09d3f`.
- Active candidate daemon override, daemon blob `941baffc8423a10cfa1436323d109caae17be473`; installed U13B Host blob remained `437f3e6c4cae53f7d94e244cd312ac454768f8e1`.
- U11 overlay matched. Manager, HA, Broker each had one running instance; listener contract exact; both MQTT consumers authenticated; HA HTTP 401 and predecessor binding `local/n3w-homeassistant:2026.10.4-5881590f`.
- Read-only IPC returned `ERROR / ha_prepare_host_command_failed` again. The old restart-convergence error did not recur in the observed IPC result. Phase-A completion remains open.
- One exact UUID-bound ext4 partition was visible and unmounted in the observer namespace. The observer's root `findmnt` succeeded. No matching ext4 or I/O error was found in the queried kernel journal window. The current unit journal had five lines and did not expose the error's subprocess or traceback. The active daemon retained CAP_SYS_ADMIN with PrivateDevices disabled.
- The candidate's `ha_prepare_host_command_failed` wrapper drops argv, return code and stderr. The bound-media reconciliation path contains several possible command sites. The failing executable and root cause remain unconfirmed. The USB transaction bytes were not independently re-read in this STOP audit.

## Continuation boundary

KF-168 remains open for live completion. This is a newly observed terminal signature, with prior runtime recovery intact. Stop with the repaired candidate installed and the authorization spent. The next safe entry is a separately scoped read-only diagnosis of the suppressed subprocess failure. No standalone mount, reinstallation, additional restart, destructive replay or Phase B is authorized by this record.

## Spent execution artifact provenance

- One-shot wrapper SHA-256 `14bfdc45f9566c3e8da7fc5c9de266acb8fd56fd1608b38da8e1fb47e9cbee9a`.
- Observer SHA-256 `164fad0600eba56b5aa9edc1b3156d86e2cc8001037b1db80076c7fa903c8f57`.
- Compiled-input transport SHA-256 `11689748558750bcff80d052ba5460dfaf0a28efac35fadec49603f34304f535`. Transport wrapped the observer text and the exact Git blob bytes in a JSON bundle. The post-STOP observer used the same health checks with the observed IPC error as its expected state. Private SSH routing and authentication material are excluded.
- The following text is historical evidence for the consumed attempt. It confers no permission to execute.

<details>
<summary>t1-restart-live-once.py</summary>

```text
import base64
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import time

OLD = "a103a2633aaea5a34efbfed35449b2eb5bace61b"
NEW = "437f3e6c4cae53f7d94e244cd312ac454768f8e1"
activity = {"candidate_replaced": False, "restart_invocation_count": 0}


def emit(**fields):
    print(json.dumps({**activity, **fields}, sort_keys=True), flush=True)


def wait_for_terminal(probe):
    deadline = time.monotonic() + 240
    last = {}
    while time.monotonic() < deadline:
        try:
            status = probe["query_status"]()
        except OSError:
            time.sleep(2)
            continue
        probe["require"](status.get("accepted") is True and status.get("code") == "status")
        phase = status.get("phase")
        error = status.get("error_code")
        last = {
            "ipc_phase": phase if isinstance(phase, str) and re.fullmatch(r"[A-Z_]{1,80}", phase) else None,
            "ipc_error_code": error if isinstance(error, str) and re.fullmatch(r"[a-z0-9_]{1,120}", error) else None,
        }
        if phase == "ROLLED_BACK" and error is None:
            return
        if phase == "ERROR":
            emit(status="IPC_TERMINAL_ERROR", **last)
            raise RuntimeError("ipc_terminal_error")
        time.sleep(2)
    emit(status="IPC_TIMEOUT", **last)
    raise TimeoutError("ipc_completion_timeout")


def execute(probe, payload):
    require = probe["require"]
    run = probe["run"]
    ota = probe["OTA"]
    transaction = probe["TRANSACTION"]
    candidate = probe["CANDIDATE"] / "n3w_t1_core_updater_ha_u13b_host.py"
    activity["step"] = "fresh_preflight"
    require(hashlib.sha1(f"blob {len(payload)}\0".encode() + payload).hexdigest() == NEW)
    compile(payload, "candidate U13B Host", "exec")
    probe["main"]()
    activity["preflight"] = "PASS"
    old_pid = run("systemctl", "show", "-p", "MainPID", "--value", ota)
    baseline = transaction.read_bytes()
    require(hashlib.sha256(baseline).hexdigest() == probe["result"]["host_transaction_sha256"])
    old = candidate.lstat()
    require(stat.S_ISREG(old.st_mode) and old.st_nlink == 1 and old.st_uid == 0)

    activity["step"] = "atomic_candidate_replacement"
    descriptor, temporary = tempfile.mkstemp(prefix=".u13b-live-retry-", dir=candidate.parent)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(payload)
            output.flush()
            os.fchown(output.fileno(), old.st_uid, old.st_gid)
            os.fchmod(output.fileno(), stat.S_IMODE(old.st_mode))
            for name in os.listxattr(candidate, follow_symlinks=False):
                os.setxattr(output.fileno(), name, os.getxattr(candidate, name, follow_symlinks=False))
            os.fsync(output.fileno())
        require(probe["git_blob"](candidate) == OLD)
        current = candidate.lstat()
        require((current.st_dev, current.st_ino, current.st_ctime_ns) ==
                (old.st_dev, old.st_ino, old.st_ctime_ns))
        require(transaction.read_bytes() == baseline)
        require(run("systemctl", "show", "-p", "MainPID", "--value", ota) == old_pid)
        os.replace(temporary, candidate)
        activity["candidate_replaced"] = True
        temporary = None
        directory = os.open(candidate.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        require(probe["git_blob"](candidate) == NEW)
    finally:
        if temporary is not None:
            os.unlink(temporary)

    activity["step"] = "single_ota_restart"
    require(transaction.read_bytes() == baseline)
    require(run("systemctl", "show", "-p", "MainPID", "--value", ota) == old_pid)
    activity["restart_invocation_count"] = 1
    emit(status="RESTART_INVOKING", candidate_blob=NEW)
    subprocess.run(("systemctl", "restart", ota), stdin=subprocess.DEVNULL,
                   capture_output=True, check=True, timeout=60)
    activity["restart_command_completed"] = True
    activity["step"] = "manager_ipc_completion"
    emit(status="OBSERVING")
    wait_for_terminal(probe)

    activity["step"] = "post_restart_snapshot"
    require(run("systemctl", "show", "-p", "MainPID", "--value", ota) != old_pid)
    require(transaction.read_bytes() == baseline)
    probe["result"].clear()
    probe["main"](post_restart=True)
    require(transaction.read_bytes() == baseline)
    emit(status="PASS", evidence=probe["result"], host_transaction_unchanged=True)


def main():
    bundle = json.load(sys.stdin)
    probe = {"__name__": "read_only_probe"}
    exec(compile(bundle["probe"], "read-only preflight", "exec"), probe)
    execute(probe, base64.b64decode(bundle["payload"], validate=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        emit(status="STOP", error_type=type(error).__name__)
        sys.exit(1)
```

</details>

<details>
<summary>t1-restart-readonly-probe.py</summary>

```text
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from datetime import datetime, timezone

STATE = Path("/var/lib/n3w-t1-core-updater")
CANDIDATE = STATE / "u9plus-fault-acceptance-r1/candidate-tools"
TRANSACTION = STATE / "homeassistant-usb-upgrade.json"
OTA = "n3w-t1-ha-ota.service"
OVERRIDE = f"/etc/systemd/system/{OTA}.d/90-u9plus-fault-acceptance.conf"
EXPECTED_ERROR = "u13b_predecessor_runtime_not_running"
result = {
    "gate": "N3W_T1_U9_PLUS_PHASE_A_RESTART_CONVERGENCE_REPAIR_LIVE_REVALIDATION_PREFLIGHT",
    "observed_at_utc": datetime.now(timezone.utc).isoformat(),
}


def require(condition):
    if not condition:
        raise ValueError("preflight_condition_failed")


def run(*args):
    return subprocess.check_output(
        args, stdin=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=20
    ).decode().strip()


def git_blob(path):
    require(path.is_file() and not path.is_symlink())
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def query_status():
    prior_groups = os.getgroups()
    os.setgroups([])
    os.setegid(999)
    os.seteuid(999)
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(10)
            client.connect("/run/n3w-t1-ota/ha-ota.sock")
            client.sendall(b'{"schema":"gh.n3w-t1-ha-ota-ipc-request/1","operation":"status"}\n')
            client.shutdown(socket.SHUT_WR)
            with client.makefile("rb") as stream:
                response = stream.readline(16384)
        require(response.endswith(b"\n"))
        return json.loads(response)
    finally:
        os.seteuid(0)
        os.setegid(0)
        os.setgroups(prior_groups)


def main(*, post_restart=False):
    result["step"] = "host_transaction"
    require(os.geteuid() == 0 and os.getegid() == 0)
    require(TRANSACTION.is_file() and not TRANSACTION.is_symlink())
    baseline = TRANSACTION.read_bytes()
    digest = hashlib.sha256(baseline).hexdigest()
    result["host_transaction_sha256"] = digest
    require(digest == "4548f591d972576ea4d3f1f078cb55b483d1f63f2244b03c3413da1891e09d3f")
    tx = json.loads(baseline)
    require(tx["phase"] == "U13B_ROLLED_BACK" and tx["status"] == "ROLLED_BACK")
    require(tx["rollback_health_verified"] is True)
    result.update(host_phase=tx["phase"], host_status=tx["status"])

    result["step"] = "candidate_override"
    daemon = CANDIDATE / "n3w_t1_core_updater_ha_daemon.py"
    module = CANDIDATE / "n3w_t1_core_updater_ha_u13b_host.py"
    require(run("systemctl", "is-active", OTA) == "active")
    pid = run("systemctl", "show", "-p", "MainPID", "--value", OTA)
    require(pid.isdigit() and int(pid) > 0)
    require(OVERRIDE in run("systemctl", "show", "-p", "DropInPaths", "--value", OTA).split())
    require(str(daemon) in run("systemctl", "show", "-p", "ExecStart", "--value", OTA))
    require(os.fsencode(daemon) in Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0"))
    result["candidate_override_active"] = True
    result["candidate_daemon_blob"] = git_blob(daemon)
    result["candidate_u13b_host_blob"] = git_blob(module)
    require(result["candidate_daemon_blob"] == "941baffc8423a10cfa1436323d109caae17be473")
    expected_blob = ("437f3e6c4cae53f7d94e244cd312ac454768f8e1" if post_restart
                     else "a103a2633aaea5a34efbfed35449b2eb5bace61b")
    require(result["candidate_u13b_host_blob"] == expected_blob)

    result["step"] = "u11_overlay_and_business_runtime"
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(CANDIDATE))
    from n3w_t1_core_updater_ha_u13b_host import (
        BROKER_UNIT, EXPECTED_LISTENERS, SERVICES_UNIT, LocalHost,
        U13BProductionRuntime, image_recovery_record_from_document,
    )

    host = LocalHost()
    require(all(host._systemctl("is-active", unit) == "active"
                for unit in (SERVICES_UNIT, BROKER_UNIT)))
    services = ("manager", "homeassistant", "broker")
    counts = {service: host._running_count(service) for service in services}
    require(counts == dict.fromkeys(services, 1))
    peers = {service: host._runtime(service) for service in services}
    require(all(peer.get("restart_count") == 0 for peer in peers.values()))
    bindings = {
        f"expected_{service}_{parameter}": peers[service][field]
        for service in ("manager", "broker")
        for parameter, field in (
            ("container_id", "container_id"), ("image_ref", "image_ref"),
            ("runtime_image_id", "image_id"),
        )
    }
    runtime = U13BProductionRuntime(host=host, **bindings)
    predecessor = image_recovery_record_from_document(
        tx["predecessor_recovery_identity"],
        expected_kind="predecessor", expected_image_ref=tx["current_image_ref"],
    )
    require(predecessor.image_ref == "local/n3w-homeassistant:2026.10.4-5881590f")
    require(runtime._running_predecessor_evidence(tx, predecessor) is not None)
    result.update(u11_overlay=True, container_counts=counts,
                  homeassistant_binding=predecessor.image_ref)
    result["listeners_exact"] = host._listener_snapshot() == EXPECTED_LISTENERS
    require(result["listeners_exact"])
    result["mqtt_authenticated"] = {
        service: host._mqtt_authenticated(service) for service in services[:2]
    }
    require(all(result["mqtt_authenticated"].values()))
    result["homeassistant_http"] = host._homeassistant_http_status()
    require(result["homeassistant_http"] == 401)

    result["step"] = "manager_ipc_status"
    response = query_status()
    require(response.get("accepted") is True and response.get("code") == "status")
    result["ipc_uid_gid"] = "999:999"
    expected_phase = "ROLLED_BACK" if post_restart else "ERROR"
    expected_error = None if post_restart else EXPECTED_ERROR
    require(response.get("phase") == expected_phase and response.get("error_code") == expected_error)
    result.update(ipc_phase=expected_phase, ipc_error_code=expected_error)

    result["step"] = "end_snapshot"
    require(TRANSACTION.read_bytes() == baseline)
    require(run("systemctl", "show", "-p", "MainPID", "--value", OTA) == pid)
    require(git_blob(module) == result["candidate_u13b_host_blob"])
    result.update(status="PASS", read_only=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        result.update(status="STOP", error_type=type(error).__name__, read_only=True)
        print(json.dumps(result, sort_keys=True))
        sys.exit(1)
    else:
        print(json.dumps(result, sort_keys=True))
```

</details>
