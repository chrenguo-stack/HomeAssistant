# KF-168 IPC export migration preflight and release review

```text
SOURCE_REVIEW=PASS
SOURCE_HEAD=4abebaa61c1db0be41a724c45263e26ac15eb06e
SOURCE_TREE=b34b33ebd7bd477c7f10692c001b8da45768a645
T1_READONLY_BASELINE=PASS
MIGRATION_SEQUENCE=REVIEW_ONLY
PRODUCTION_AUTHORITY=false
PHASE_A_OVERALL=NOT_YET_PASS
```

[PR #810](https://github.com/chrenguo-stack/HomeAssistant/pull/810)
was rebound to the exact source above. All 16 executed workflows succeeded;
4 draft-gated workflows skipped. The [Linux ext4 and socket regression](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44724148347)
and [HA target binding](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44724148316)
both passed. The focused source review confirmed the daemon publishes both
Manager endpoints in the independent directory, systemd owns its preparation
and stale socket cleanup, and the in-container paths and UID 999 peer check
remain unchanged. Production installation and full service lifecycle were
not exercised by that regression.

## Fresh T1 read-only baseline

At 2026-11-20T11:08:16Z, Host was `U13B_ROLLED_BACK / ROLLED_BACK`
with transaction SHA-256
`4548f591d972576ea4d3f1f078cb55b483d1f63f2244b03c3413da1891e09d3f`.
The uniquely bound ext4 USB had no mounts across 11 observed mount
namespaces. Manager, HA and Broker were healthy 1/1/1 with exact listeners,
both MQTT authentications and HA HTTP 401. The candidate override
remained active. Read-only status as 999:999 returned the previous
terminal `ERROR / ha_prepare_host_command_failed`. The probe did not
re-run completion or read USB transaction metadata anew.

The older Manager bind and legacy host socket are active. The new export
directory is absent and the approved manifest source is present. The
application supervision unit Requires and is After the OTA unit. The
existing `90-u9plus-fault-acceptance.conf` candidate override must stay
bound, with observed SHA-256
`dcb4e566c12e6f57add6bcfb100a69001b3146b47abf4cb824a166726938aa6a`.
The running U13B Host blob remains `437f3e6c4cae53f7d94e244cd312ac454768f8e1`.

## Exact deployment delta to review

The active candidate directory matched 30 of 33 reviewed product members.
The following three candidate files and two installed assets delimit the
reviewed delta. Before any future write, rebind each old value and recover
the exact rollback bytes from the named Git object or the verified current
asset, preserving root ownership and permissions. The candidate files are
in the already-bound Phase-A override's `candidate-tools` directory, not
the installed daemon source under `/opt/HomeAssistant/tools`.

| Asset | Observed version | PR #810 target |
| --- | --- | --- |
| Candidate `n3w_t1_core_updater_ha_daemon.py` | blob `941baffc8423a10cfa1436323d109caae17be473` | blob `bb048c3641b9f66767d89b20a80aa3049fbed8db` |
| Candidate `n3w_t1_core_updater_ha_ipc.py` | blob `48558556169a045da092aef94d4c5244d2c48775` | blob `893545a401858c57fd4c0c03b8f486bbe5a3c8d9` |
| Candidate `n3w_t1_core_updater_ha_prepare_host.py` | blob `060066bb3495bcf50a373fa7d83633b0eb85276d` | blob `ed42956bd5ac9f945c329a020e5645645890ca5c` |
| `/etc/systemd/system/n3w-t1-ha-ota.service` | SHA-256 `af8d9755ba13d9300fb5318d077e5d20078229814fdc29e4127806ef78ddb370` | SHA-256 `72edc7d3075f1cbc9843999ade6cedafa261e551b8a8ba878ade46cf992d5c68` |
| `/opt/HomeAssistant/infra/n3w-t1/production/docker-compose.ha-ota.yml` | SHA-256 `1b0fd19cb3f8047d0ce50ecfdd69f0e71d8256bed2198de10d7d78c39eacd618` | SHA-256 `126dd7fc4174171412ab6a623f97216ddaa9054c409941bc9f8ee4448cfd68d5` |

The IPC difference has a historical source locator. The live blob was the
U10 status-repair source at `b47e4e5e747a3337f992159e7c65ec1e49c86ca4`.
The exact candidate adds only the safe error-code-prefix fallback to
`_public_code()` (`345382410fe18b3f8015c84013094f0550d549cd`).
OTA unit and Compose overlay old bytes match repository base
`06332c58de850c590da83e0971d7576291f371b2`.

## Sequence guard and stop

A simple OTA restart followed by Manager recreation is unsafe for this
candidate. The daemon captures Manager container ID before its recovery
worker starts. A Manager recreated after that capture violates strict
peer matching. The proposed order for execution review is:

1. Prepare rollback bytes and verify the old unit, override, overlay, all 33
   candidate bindings and no USB mounts. Stop the application owner and
   OTA in a controlled maintenance window. Keep Broker active.
2. Stage the exact five assets while both owners are stopped. Prepare the
   new root:999 0750 export directory and reload systemd. Validate the
   effective units and rendered Compose delta.
3. Pre-create the single stopped Manager with the new bind using the
   existing Compose project and both approved Compose files. The installed
   Compose supports `up --no-start --no-deps --no-build --pull never`.
   Validate its bind source, unchanged image, single exact residue and
   absence of the bound USB. Capture its ID before starting OTA.
4. Start OTA and verify the export, legacy alias and preserved Manager
   identity. Start the application owner and verify it uses that same
   Manager ID. If it recreates Manager, stop rather than retrying OTA.
5. Observe IPC completion, durable Host/USB agreement and the existing
   business health checks. Preserve and review rollback decisions;
   reversal would restore the old three candidate files, unit and overlay
   as a coordinated set, with both owners stopped and no USB mounted.

The sequence had no T1 writes in this preflight. The application-owner
stop/start can interrupt Manager and HA, and the five-file change includes
an installed production overlay. No earlier restart or unmount approval
covers that deployment. This record is an execution-review input and
does not authorize or claim a production operation.

Observer SHA-256 `a9865b156ce695870e9031605858b5c263a3edc5b440397b9270d68c1b459d1c`.
The observer was fed the exact 33-member product binding from PR #810;
it emitted only hashes, summarized service state and mount counts.

<details>
<summary>Read-only observer source</summary>

```text
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

OTA_UNIT = "n3w-t1-ha-ota.service"
APP_UNIT = "n3wfc4-services-activation.service"
BROKER_UNIT = "n3wfc4-broker-activation.service"
TX_PATH = Path("/var/lib/n3w-t1-core-updater/homeassistant-usb-upgrade.json")
CANDIDATE = TX_PATH.parent / "u9plus-fault-acceptance-r1/candidate-tools"
OVERLAY = Path("/opt/HomeAssistant/infra/n3w-t1/production/docker-compose.ha-ota.yml")
NEW_EXPORT = Path("/run/n3w-t1-ota-ipc")
EXPECTED_TRANSACTION = "4548f591d972576ea4d3f1f078cb55b483d1f63f2244b03c3413da1891e09d3f"


def run(*args):
    return subprocess.check_output(args, stdin=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                   timeout=20).decode().strip()


def prop(unit, field):
    return run("systemctl", "show", "-p", field, "--value", unit)


def digest(path):
    assert path.is_absolute() and path.is_file() and not path.is_symlink()
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mounts_for_device(mm):
    observed = {}
    for item in Path("/proc").iterdir():
        if not item.name.isdecimal():
            continue
        try:
            ns = (item / "ns/mnt").stat().st_ino
            if ns not in observed:
                observed[ns] = sum(
                    row.split()[2] == mm for row in (item / "mountinfo").read_text().splitlines()
                )
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
    return len(observed), sum(observed.values())


def manager_id():
    cid = run("docker", "ps", "-q", "--filter", "label=com.docker.compose.project=n3wfc4",
              "--filter", "label=com.docker.compose.service=manager")
    assert re.fullmatch(r"[0-9a-f]{12,64}", cid)
    return cid


def verify(result, expected):
    result["step"] = "host_and_usb"
    host_bytes = TX_PATH.read_bytes()
    assert hashlib.sha256(host_bytes).hexdigest() == EXPECTED_TRANSACTION
    tx = json.loads(host_bytes)
    assert tx["phase"] == "U13B_ROLLED_BACK" and tx["status"] == "ROLLED_BACK"
    assert tx["authorization_claimed"] is True and tx["authorization_consumed"] is True
    dev = run("blkid", "-c", "/dev/null", "-t", "UUID=" + tx["usb_filesystem_uuid"], "-o", "device")
    assert re.fullmatch(r"/dev/[A-Za-z0-9_-]+", dev)
    dev_stat = os.stat(dev)
    assert stat.S_ISBLK(dev_stat.st_mode)
    mm = f"{os.major(dev_stat.st_rdev)}:{os.minor(dev_stat.st_rdev)}"
    parent = Path("/sys/dev/block", mm).resolve().parent
    root = run("findmnt", "--noheadings", "--output", "MAJ:MIN", "/")
    assert root and root not in {mm, (parent / "dev").read_text().strip()}
    assert run("blkid", "-c", "/dev/null", "-s", "TYPE", "-o", "value", dev) == "ext4"
    assert run("blkid", "-c", "/dev/null", "-s", "LABEL", "-o", "value", dev) == "N3W-UPDATE"
    result["mount_namespaces_read"], result["bound_usb_mount_count"] = mounts_for_device(mm)
    assert result["mount_namespaces_read"] > 0 and result["bound_usb_mount_count"] == 0
    result["host_transaction_sha256"] = EXPECTED_TRANSACTION

    result["step"] = "services_and_overlay"
    units = (OTA_UNIT, APP_UNIT, BROKER_UNIT)
    pids = [prop(unit, "MainPID") for unit in units]
    assert all(value.isdigit() and int(value) > 0 for value in pids)
    assert all(run("systemctl", "is-active", unit) == "active" for unit in units)
    assert str(CANDIDATE / "n3w_t1_core_updater_ha_daemon.py") in prop(OTA_UNIT, "ExecStart")
    assert str(OVERLAY) in prop(APP_UNIT, "ExecStart") and str(OVERLAY) in prop(APP_UNIT, "ExecStop")
    cid = manager_id()
    mounts = json.loads(run("docker", "inspect", "-f", "{{json .Mounts}}", cid))
    manager_bind = [m for m in mounts if m.get("Destination") == "/run/n3w/t1-ota"]
    assert len(manager_bind) == 1 and manager_bind[0].get("Type") == "bind"
    assert manager_bind[0].get("Source") == "/run/n3w-t1-ota" and manager_bind[0].get("RW") is False
    result["manager_current_export"] = "legacy_runtime_root_readonly"
    result["services_requires_ota"] = OTA_UNIT in prop(APP_UNIT, "Requires").split()
    result["services_after_ota"] = OTA_UNIT in prop(APP_UNIT, "After").split()
    result["new_export_absent"] = not NEW_EXPORT.exists() and not NEW_EXPORT.is_symlink()
    result["approved_manifest_source_present"] = (Path("/etc/n3w-t1-ota") / "approved-homeassistant.json").is_file()
    result["legacy_runtime_socket_is_socket"] = (Path("/run/n3w-t1-ota") / "ha-ota.sock").is_socket()
    result["ota_unit_sha256"] = digest(Path(prop(OTA_UNIT, "FragmentPath")))
    result["ota_dropin_sha256"] = [digest(Path(p)) for p in prop(OTA_UNIT, "DropInPaths").split()]
    result["manager_overlay_sha256"] = digest(OVERLAY)

    result["step"] = "candidate_member_binding"
    actual = {}
    for name, target in sorted(expected.items()):
        assert re.fullmatch(r"n3w_t1_[a-zA-Z0-9_]+\.py", name)
        path = CANDIDATE / name
        if path.is_symlink() or not path.is_file():
            actual[name] = "MISSING_OR_UNSAFE"
            continue
        data = path.read_bytes()
        blob = hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
        if blob != target:
            actual[name] = blob
    result["expected_candidate_members"] = len(expected)
    result["candidate_member_drift"] = actual
    assert manager_id() == cid and [prop(unit, "MainPID") for unit in units] == pids
    assert TX_PATH.read_bytes() == host_bytes
    result["host_and_services_unchanged"] = True
    result["status"] = "OBSERVED"


result = {"observed_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()}
try:
    verify(result, EXPECTED_CANDIDATE)
except Exception as error:
    result.update(status="STOP", error_type=type(error).__name__)
    print(json.dumps(result, sort_keys=True))
    sys.exit(1)
print(json.dumps(result, sort_keys=True))
```

</details>
