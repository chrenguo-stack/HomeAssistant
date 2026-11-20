# KF-168 authorized IPC migration STOP and rollback audit

```text
MIGRATION=STOP
MIGRATION_AUTHORIZATION=CONSUMED_NO_REPLAY
PRODUCTION_AUTHORITY=false
LIVE_TARGET_SOURCE=4abebaa61c1db0be41a724c45263e26ac15eb06e
FIVE_FILE_ROLLBACK=PASS
BUSINESS_RUNTIME_AFTER_ROLLBACK=PASS
PHASE_A_OVERALL=NOT_YET_PASS
```

Authority: [exact five-file migration preflight](https://github.com/chrenguo-stack/HomeAssistant/blob/b7f7d2dd70ae00deead70c30f23551fc8c1645e6/docs/development/N3W_T1_KF168_MANAGER_OTA_IPC_MIGRATION_PREFLIGHT_20261120.md).

## What happened

- Fresh exact preflight passed for all 33 candidate members, the five
  asset baselines, existing Manager Compose config hash, the prior IPC
  terminal and an unmounted exact USB. Five previous byte streams were
  saved and verified in the protected one-shot receipt directory before
  either owner was stopped.
- The executor stopped the application owner and OTA once, replaced the
  five authorized assets, pre-created the single stopped Manager using the
  new bind, started OTA, and verified both public endpoints and the host
  compatibility alias. The application start command returned. The
  immediate running-container check raised `container_not_unique`, so
  the new layout did not reach completion verification.
- The constrained rollback restored five files and started OTA and the
  application owner on the old layout. The immediate running-container
  assertion stopped the observer again. Independent read-only checks
  subsequently proved all five original bytes and the old Manager bind
  restored, with all services settled. The attempt was not repeated.

## Proven executor failure

The application owner is `Type=simple`. During the candidate attempt,
systemd emitted Started at 11:17:32.950290 UTC, then the execute-and-rollback
path requested stop at 11:17:33.388309 UTC. During rollback it emitted
Started at 11:17:55.315169 UTC, while Docker recorded HA and Manager starts
at 11:17:56.576259 and 11:17:56.578443 UTC. The executor treated activation
of the Compose process as readiness of the Docker containers, with no
readiness window. Thus the stopped/pre-created to running transition can
raise the false `container_not_unique` gate before container startup. The
proof is strongest on the independently observed rollback timing. There is
no evidence the integrated new layout failed after reaching a settled
application runtime.

A successor execution candidate needs the same bounded readiness barrier
on install and rollback. Treat zero running containers as retryable while
the unique expected stopped/resident ID is still exact and the owner has
not failed; require exact running identity, overlay, image and health
before claiming readiness. Duplicate or replaced Manager, service
failure or deadline expiry must fail closed. Do not substitute a fixed
sleep or another service start. Test delayed startup and drift offline.

## Settled rollback evidence

- 11:18:20 UTC: all five restored files byte-equal to their verified
  pre-deploy backups; three owners active; legacy Manager bind restored;
  Manager, HA and Broker counts 1/1/1. Broker container start timestamp
  remained from 2026-11-19T14:01:51Z. Host transaction digest remained
  `4548f591d972576ea4d3f1f078cb55b483d1f63f2244b03c3413da1891e09d3f`.
- 11:18:56 UTC: U11 overlay, exact listeners, both MQTT authentications
  and HA HTTP 401 verified; IPC observed `ROLLING_BACK`.
- 11:22:13 UTC: the same business/Host checks still passed. The old
  layout's restarted oracle ended at
  `ERROR / u9_plus_recovery_customer_oracle_incomplete` (queried as
  Manager UID/GID 999:999).
- Kernel log in the rollback window reported one mount and one unmount
  for the exact bound ext4 partition, with no matching ext4 error. There
  were zero residual bound-partition mounts in 11 checked namespaces.
  This attempt did not reproduce the earlier mount-command failure.
- Manager accepted simplified N3-W telemetry event count was zero in the
  11:17:51–11:22:13 UTC sample, which encloses the rollback oracle window.
  The required fresh-telemetry evidence was therefore absent. The
  aggregate oracle error itself does not identify every failed assertion.
  This is separate from the migration executor startup readiness error.

No Broker command, U9 replay, U10 replay, direct USB transaction
write, permanent-fix redeploy or Phase B was performed. The next safe
work is source-only executor readiness repair and an explicit check that
a verifiable N3-W telemetry source is available for a future exact run.

## Spent executor evidence

Historical wrapper SHA-256:
`519539f6f67d8a5f37bd9cd28cd90cb7ac61ece35ba7135c4a494c697a220785`.
Source assets were streamed from the exact PR git commit, with the old
and target digests taken from the preflight archive. Runtime backup
bytes remain private. The following excerpts are historical and confer
no execution permission.

<details>
<summary>Sanitized one-shot execution receipt</summary>

```jsonl
{"app_starts": 0, "app_stops": 0, "asset_count": 5, "asset_writes": 0, "broker_mutation_requested": false, "candidate_members": 33, "ota_starts": 0, "ota_stops": 0, "status": "PREFLIGHT_PASS", "step": "fresh_exact_preflight"}
{"app_starts": 0, "app_stops": 0, "asset_count": 5, "asset_writes": 0, "authorization_claimed": true, "broker_mutation_requested": false, "ota_starts": 0, "ota_stops": 0, "status": "ROLLBACK_BYTES_READY", "step": "save_verified_rollback"}
{"action": "stop", "app_starts": 0, "app_stops": 1, "asset_writes": 0, "authorization_claimed": true, "broker_mutation_requested": false, "ota_starts": 0, "ota_stops": 0, "status": "ACTION_INVOKED", "step": "stop_owners", "unit": "n3wfc4-services-activation.service"}
{"action": "stop", "app_starts": 0, "app_stops": 1, "asset_writes": 0, "authorization_claimed": true, "broker_mutation_requested": false, "ota_starts": 0, "ota_stops": 1, "status": "ACTION_INVOKED", "step": "stop_owners", "unit": "n3w-t1-ha-ota.service"}
{"app_starts": 0, "app_stops": 1, "asset_writes": 5, "authorization_claimed": true, "broker_mutation_requested": false, "identity_bound": true, "ota_starts": 0, "ota_stops": 1, "status": "MANAGER_PRECREATED", "step": "precreate_manager"}
{"action": "start", "app_starts": 0, "app_stops": 1, "asset_writes": 5, "authorization_claimed": true, "broker_mutation_requested": false, "ota_starts": 1, "ota_stops": 1, "status": "ACTION_INVOKED", "step": "start_new_owners", "unit": "n3w-t1-ha-ota.service"}
{"action": "start", "app_starts": 1, "app_stops": 1, "asset_writes": 5, "authorization_claimed": true, "broker_mutation_requested": false, "ota_starts": 1, "ota_stops": 1, "status": "ACTION_INVOKED", "step": "start_new_owners", "unit": "n3wfc4-services-activation.service"}
{"app_starts": 1, "app_stops": 1, "asset_writes": 5, "authorization_claimed": true, "broker_mutation_requested": false, "ota_starts": 1, "ota_stops": 1, "reason": "container_not_unique", "status": "INSTALL_STOP", "step": "start_new_owners", "subprocess_rc": null}
{"action": "stop", "app_starts": 1, "app_stops": 1, "asset_writes": 5, "authorization_claimed": true, "broker_mutation_requested": false, "ota_starts": 1, "ota_stops": 1, "rollback_app_stops": 1, "status": "ACTION_INVOKED", "step": "rollback", "unit": "n3wfc4-services-activation.service"}
{"action": "stop", "app_starts": 1, "app_stops": 1, "asset_writes": 5, "authorization_claimed": true, "broker_mutation_requested": false, "ota_starts": 1, "ota_stops": 1, "rollback_app_stops": 1, "rollback_ota_stops": 1, "status": "ACTION_INVOKED", "step": "rollback", "unit": "n3w-t1-ha-ota.service"}
{"action": "start", "app_starts": 1, "app_stops": 1, "asset_writes": 5, "authorization_claimed": true, "broker_mutation_requested": false, "ota_starts": 1, "ota_stops": 1, "rollback_app_stops": 1, "rollback_asset_writes": 5, "rollback_ota_starts": 1, "rollback_ota_stops": 1, "status": "ACTION_INVOKED", "step": "rollback", "unit": "n3w-t1-ha-ota.service"}
{"action": "start", "app_starts": 1, "app_stops": 1, "asset_writes": 5, "authorization_claimed": true, "broker_mutation_requested": false, "ota_starts": 1, "ota_stops": 1, "rollback_app_starts": 1, "rollback_app_stops": 1, "rollback_asset_writes": 5, "rollback_ota_starts": 1, "rollback_ota_stops": 1, "status": "ACTION_INVOKED", "step": "rollback", "unit": "n3wfc4-services-activation.service"}
{"app_starts": 1, "app_stops": 1, "asset_writes": 5, "authorization_claimed": true, "broker_mutation_requested": false, "ota_starts": 1, "ota_stops": 1, "reason": "container_not_unique", "rollback_app_starts": 1, "rollback_app_stops": 1, "rollback_asset_writes": 5, "rollback_ota_starts": 1, "rollback_ota_stops": 1, "status": "ROLLBACK_STOP", "step": "rollback", "subprocess_rc": null}
{"app_starts": 1, "app_stops": 1, "asset_writes": 5, "authorization_claimed": true, "broker_mutation_requested": false, "ota_starts": 1, "ota_stops": 1, "reason": "container_not_unique", "rollback_app_starts": 1, "rollback_app_stops": 1, "rollback_asset_writes": 5, "rollback_ota_starts": 1, "rollback_ota_stops": 1, "status": "STOP", "step": "rollback", "subprocess_rc": null}
```

</details>

<details>
<summary>Historical executor source</summary>

```text
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import time

STATE = Path("/var/lib/n3w-t1-core-updater")
TX = STATE / "homeassistant-usb-upgrade.json"
CANDIDATE = STATE / "u9plus-fault-acceptance-r1/candidate-tools"
OTA = "n3w-t1-ha-ota.service"
APP = "n3wfc4-services-activation.service"
BROKER = "n3wfc4-broker-activation.service"
UNIT = Path("/etc/systemd/system") / OTA
OVERRIDE = UNIT.parent / (OTA + ".d") / "90-u9plus-fault-acceptance.conf"
OVERLAY = Path("/opt/HomeAssistant/infra/n3w-t1/production/docker-compose.ha-ota.yml")
IPC = Path("/run/n3w-t1-ota-ipc")
LEGACY_SOCKET = Path("/run/n3w-t1-ota/ha-ota.sock")
RECEIPT = STATE / "kf168-ipc-export-migration-4abebaa61c1d"
TX_SHA = "4548f591d972576ea4d3f1f078cb55b483d1f63f2244b03c3413da1891e09d3f"
EXACT_OVERRIDE_SHA = "dcb4e566c12e6f57add6bcfb100a69001b3146b47abf4cb824a166726938aa6a"
STEPS = {"asset_writes": 0, "app_stops": 0, "ota_stops": 0, "app_starts": 0, "ota_starts": 0,
         "broker_mutation_requested": False}


def require(value, code):
    if not value:
        raise ValueError(code)


def emit(status, **details):
    note = {"status": status, **STEPS, **details}
    print(json.dumps(note, sort_keys=True), flush=True)
    if RECEIPT.is_dir() and not RECEIPT.is_symlink() and STEPS.get("authorization_claimed"):
        with (RECEIPT / "receipt.jsonl").open("a") as out:
            out.write(json.dumps(note, sort_keys=True) + "\n")
            out.flush()
            os.fsync(out.fileno())


def run(*args, timeout=25, check=True):
    result = subprocess.run(args, stdin=subprocess.DEVNULL, capture_output=True,
                            timeout=timeout, check=False)
    if check and result.returncode:
        error = RuntimeError("subprocess_failed")
        error.returncode = result.returncode
        raise error
    return result


def out(*args):
    return run(*args).stdout.decode().strip()


def prop(unit, key):
    return out("systemctl", "show", "-p", key, "--value", unit)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def blob(data):
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def docker_id(service, *, running=True):
    argv = ["docker", "ps", "-q", "--no-trunc"]
    if not running:
        argv.append("-a")
    value = out(*argv, "--filter", "label=com.docker.compose.project=n3wfc4",
                "--filter", "label=com.docker.compose.service=" + service)
    require(re.fullmatch(r"[0-9a-f]{64}", value), "container_not_unique")
    return value


def inspect_value(container, template):
    return json.loads(out("docker", "inspect", "-f", "{{json " + template + "}}", container))


def manager_bind(container, source):
    matches = [entry for entry in inspect_value(container, ".Mounts")
               if entry.get("Destination") == "/run/n3w/t1-ota"]
    return (len(matches) == 1 and matches[0].get("Type") == "bind"
            and matches[0].get("Source") == source and matches[0].get("RW") is False)


def device_is_unmounted(device):
    info = device.stat()
    mm = f"{os.major(info.st_rdev)}:{os.minor(info.st_rdev)}"
    seen = set()
    for p in Path("/proc").iterdir():
        if not p.name.isdecimal():
            continue
        try:
            ns = (p / "ns/mnt").stat().st_ino
            if ns in seen:
                continue
            rows = (p / "mountinfo").read_text().splitlines()
            require(not any(row.split()[2] == mm for row in rows), "bound_usb_mounted")
            seen.add(ns)
        except (FileNotFoundError, ProcessLookupError):
            continue
    require(bool(seen), "mount_observation_empty")


def active(unit):
    return run("systemctl", "is-active", unit, check=False).stdout.strip() == b"active"


def validate_state(device, original, broker):
    require(TX.read_bytes() == original, "host_transaction_drift")
    require(active(BROKER) and prop(BROKER, "MainPID") == broker[0]
            and docker_id("broker") == broker[1], "broker_drift")
    device_is_unmounted(device)


def read_asset(path):
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and info.st_nlink == 1
            and not info.st_mode & 0o022, "asset_metadata")
    return path.read_bytes(), info


def replace_asset(target, payload, metadata):
    fd, temporary = tempfile.mkstemp(prefix=".kf168-ipc-", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fchown(stream.fileno(), metadata.st_uid, metadata.st_gid)
            os.fchmod(stream.fileno(), stat.S_IMODE(metadata.st_mode))
            for attr in os.listxattr(target, follow_symlinks=False):
                os.setxattr(stream.fileno(), attr, os.getxattr(target, attr, follow_symlinks=False))
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)
    directory = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def compose(*args):
    command = (
        'test "$N3WFC4_COMPOSE_PROJECT_NAME" = n3wfc4; '
        'test "$N3WFC4_COMPOSE_ENV_FILE" = /etc/n3wfc4/docker-compose.env; '
        'test "$N3WFC4_COMPOSE_FILE" = /etc/n3wfc4/docker-compose.yml; '
        'exec /usr/bin/docker compose --project-name "$N3WFC4_COMPOSE_PROJECT_NAME" '
        '--env-file "$N3WFC4_COMPOSE_ENV_FILE" -f "$N3WFC4_COMPOSE_FILE" '
        '-f /opt/HomeAssistant/infra/n3w-t1/production/docker-compose.ha-ota.yml '
        '--profile application "$@"'
    )
    return run("systemd-run", "--quiet", "--wait", "--pipe", "--collect",
               "--property=EnvironmentFile=/etc/n3wfc4/broker-activation.env",
               "--property=EnvironmentFile=-/etc/n3wfc4/ha-ota-activation.env",
               "/bin/sh", "-eu", "-c", command, "kf168", *args, timeout=75)


def precreate(manager_image, source):
    compose("up", "--no-start", "--no-deps", "--no-build", "--pull", "never", "manager")
    manager = docker_id("manager", running=False)
    require(inspect_value(manager, ".State.Running") is False
            and inspect_value(manager, ".Image") == manager_image
            and manager_bind(manager, source), "manager_precreate_drift")
    return manager


def compose_manager_hash():
    fields = compose("config", "--hash", "manager").stdout.decode().split()
    require(len(fields) == 2 and fields[0] == "manager"
            and re.fullmatch(r"[a-f0-9]{64}", fields[1]), "compose_manager_hash_missing")
    return fields[1]


def lifecycle(action, unit, key):
    STEPS[key] = STEPS.get(key, 0) + 1
    emit("ACTION_INVOKED", action=action, unit=unit)
    run("systemctl", action, unit, timeout=80)


def wait_socket(socket_path):
    deadline = time.monotonic() + 25
    while time.monotonic() < deadline:
        if socket_path.is_socket() and active(OTA):
            return
        time.sleep(0.25)
    raise ValueError("ota_socket_unavailable")


def wait_completion(probe, manager, baseline):
    deadline = time.monotonic() + 265
    last = None
    while time.monotonic() < deadline:
        require(TX.read_bytes() == baseline and active(APP) and active(OTA), "completion_baseline_drift")
        require(docker_id("manager") == manager, "manager_identity_changed")
        try:
            response = probe["query_status"]()
        except OSError:
            time.sleep(2)
            continue
        require(response.get("accepted") is True and response.get("code") == "status", "ipc_rejected")
        phase, error = response.get("phase"), response.get("error_code")
        if (phase, error) != last:
            last = phase, error
            emit("IPC_OBSERVED",
                 ipc_phase=phase if isinstance(phase, str) and re.fullmatch("[A-Z_]{1,80}", phase) else None,
                 ipc_error=error if isinstance(error, str) and re.fullmatch("[a-z0-9_]{1,120}", error) else None)
        if phase == "ROLLED_BACK" and error is None:
            return
        if phase == "ERROR":
            raise ValueError("ipc_terminal_error")
        time.sleep(2)
    raise ValueError("ipc_completion_timeout")


def rollback(context):
    original, device, broker, assets, manager_image, ha_image = context
    validate_state(device, original, broker)
    require(not out("systemctl", "list-jobs", "--no-legend", "--no-pager"), "systemd_jobs_pending")
    STEPS["step"] = "rollback"
    if active(APP):
        lifecycle("stop", APP, "rollback_app_stops")
    if active(OTA):
        lifecycle("stop", OTA, "rollback_ota_stops")
    validate_state(device, original, broker)
    require(not active(APP) and not active(OTA), "rollback_owners_not_stopped")
    for target, old, new, info in reversed(assets):
        current, _ = read_asset(target)
        require(current in (old, new), "rollback_asset_drift")
        if current == new:
            replace_asset(target, old, info)
            STEPS["rollback_asset_writes"] = STEPS.get("rollback_asset_writes", 0) + 1
        require(target.read_bytes() == old, "rollback_asset_verify")
    run("systemctl", "daemon-reload", timeout=55)
    manager = precreate(manager_image, "/run/n3w-t1-ota")
    lifecycle("start", OTA, "rollback_ota_starts")
    wait_socket(LEGACY_SOCKET)
    lifecycle("start", APP, "rollback_app_starts")
    require(docker_id("manager") == manager and inspect_value(docker_id("homeassistant"), ".Image") == ha_image,
            "rollback_app_identity_drift")
    validate_state(device, original, broker)
    emit("ROLLBACK_RUNTIME_RESTORED")


def execute(bundle, mode):
    require(os.geteuid() == 0, "root_required")
    STEPS["step"] = "fresh_exact_preflight"
    require(not RECEIPT.exists() and not RECEIPT.is_symlink(), "one_shot_already_claimed")
    original = TX.read_bytes()
    require(digest(original) == TX_SHA, "host_transaction_drift")
    tx = json.loads(original)
    require(tx["phase"] == "U13B_ROLLED_BACK" and tx["authorization_consumed"] is True, "host_not_terminal")
    dev = out("blkid", "-c", "/dev/null", "-t", "UUID=" + tx["usb_filesystem_uuid"], "-o", "device")
    require(re.fullmatch(r"/dev/[A-Za-z0-9_-]+", dev), "bound_device_not_unique")
    device = Path(dev)
    require(stat.S_ISBLK(device.stat().st_mode), "bound_device_not_block")
    require(out("blkid", "-c", "/dev/null", "-s", "TYPE", "-o", "value", dev) == "ext4"
            and out("blkid", "-c", "/dev/null", "-s", "LABEL", "-o", "value", dev) == "N3W-UPDATE",
            "bound_device_type_label_drift")
    sys.path.insert(0, str(CANDIDATE))
    from n3w_t1_core_updater_ha_prepare_host import SubprocessPrepareBackend, _flatten_blocks, _stable_fingerprint

    root_mm = out("findmnt", "--noheadings", "--output", "MAJ:MIN", "/")
    disks = [disk for disk in SubprocessPrepareBackend()._lsblk() if disk.get("type") == "disk"
             and any(node.get("path") == dev for node in _flatten_blocks([disk]))]
    require(len(disks) == 1 and root_mm
            and root_mm not in {node.get("maj:min") for node in _flatten_blocks(disks)}
            and disks[0].get("tran") == "usb" and disks[0].get("rm") in (1, True, "1")
            and _stable_fingerprint(disks[0]) == tx["usb_device_identity_public_fingerprint"],
            "bound_device_fingerprint_drift")
    require(digest(OVERRIDE.read_bytes()) == EXACT_OVERRIDE_SHA
            and prop(OTA, "FragmentPath") == str(UNIT)
            and prop(OTA, "DropInPaths").split() == [str(OVERRIDE)], "ota_unit_binding_drift")
    require(not IPC.exists() and not IPC.is_symlink() and LEGACY_SOCKET.is_socket(), "ipc_runtime_drift")
    require(active(APP) and active(OTA), "baseline_services_inactive")
    require(OTA in prop(APP, "Requires").split() and OTA in prop(APP, "After").split()
            and str(OVERLAY) in prop(APP, "ExecStart") and str(OVERLAY) in prop(APP, "ExecStop"),
            "owner_dependency_drift")
    manager, ha = docker_id("manager"), docker_id("homeassistant")
    require(manager_bind(manager, "/run/n3w-t1-ota"), "manager_previous_layout_drift")
    manager_image, ha_image = inspect_value(manager, ".Image"), inspect_value(ha, ".Image")
    broker = prop(BROKER, "MainPID"), docker_id("broker")
    validate_state(device, original, broker)
    expected = bundle["candidate"]
    old_candidate = bundle["old_candidate"]
    require(len(expected) == 33 and len(old_candidate) == 3, "candidate_scope")
    for name, target_blob in expected.items():
        require(re.fullmatch(r"n3w_t1_[A-Za-z0-9_]+\.py", name), "candidate_member_name")
        current, _ = read_asset(CANDIDATE / name)
        require(blob(current) == old_candidate.get(name, target_blob), "candidate_baseline_drift")
    assets = []
    for key, item in bundle["assets"].items():
        target = {"unit": UNIT, "overlay": OVERLAY}.get(key, CANDIDATE / key)
        old, info = read_asset(target)
        new = base64.b64decode(item["bytes"], validate=True)
        require(digest(new) == item["target_sha256"], "payload_sha256_mismatch")
        require((digest(old) == item["old"] if key in ("unit", "overlay") else
                 key in old_candidate and blob(old) == old_candidate[key]
                 and blob(new) == expected[key]), "asset_baseline_drift")
        assets.append((target, old, new, info))
    require(len(assets) == 5, "asset_scope")
    probe = {"__name__": "migration_health_probe"}
    exec(compile(bundle["probe"], "<health observer>", "exec"), probe)
    response = probe["query_status"]()
    require(response.get("accepted") is True and response.get("code") == "status"
            and response.get("phase") == "ERROR"
            and response.get("error_code") == "ha_prepare_host_command_failed", "ipc_baseline_drift")
    emit("PREFLIGHT_PASS", asset_count=len(assets), candidate_members=len(expected))
    if mode == "preflight":
        return
    require(mode == "execute", "execution_mode_invalid")
    STEPS["step"] = "verify_compose_environment_before_outage"
    require(
        compose_manager_hash() ==
        inspect_value(manager, '.Config.Labels').get("com.docker.compose.config-hash"),
        "compose_baseline_configuration_drift",
    )
    validate_state(device, original, broker)

    os.umask(0o077)
    RECEIPT.mkdir(mode=0o700)
    STEPS["authorization_claimed"] = True
    context = original, device, broker, assets, manager_image, ha_image
    try:
        STEPS["step"] = "save_verified_rollback"
        for target, old, _, _ in assets:
            backup = RECEIPT / (target.name + ".previous")
            with backup.open("xb") as stream:
                stream.write(old)
                stream.flush()
                os.fsync(stream.fileno())
            require(backup.read_bytes() == old, "rollback_backup_verify")
        directory = os.open(RECEIPT, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        emit("ROLLBACK_BYTES_READY", asset_count=len(assets))
        validate_state(device, original, broker)

        STEPS["step"] = "stop_owners"
        lifecycle("stop", APP, "app_stops")
        lifecycle("stop", OTA, "ota_stops")
        require(not active(APP) and not active(OTA), "owners_not_stopped")
        validate_state(device, original, broker)

        STEPS["step"] = "publish_five_assets"
        for target, old, new, info in assets:
            require(target.read_bytes() == old, "pre_replace_drift")
            replace_asset(target, new, info)
            STEPS["asset_writes"] += 1
            require(target.read_bytes() == new, "published_asset_verify")
        require(not IPC.exists() and not IPC.is_symlink(), "export_path_already_exists")
        run("/usr/bin/install", "-d", "-o", "root", "-g", "999", "-m", "0750", str(IPC))
        run("systemctl", "daemon-reload", timeout=55)
        require(str(IPC) in prop(OTA, "ExecStartPre") and str(IPC) in prop(OTA, "ExecStopPost")
                and str(CANDIDATE / "n3w_t1_core_updater_ha_daemon.py") in prop(OTA, "ExecStart"),
                "effective_unit_drift")
        validate_state(device, original, broker)

        STEPS["step"] = "precreate_manager"
        precreated = precreate(manager_image, str(IPC))
        require(precreated != manager, "manager_not_recreated")
        emit("MANAGER_PRECREATED", identity_bound=True)
        validate_state(device, original, broker)

        STEPS["step"] = "start_new_owners"
        lifecycle("start", OTA, "ota_starts")
        wait_socket(IPC / "ha-ota.sock")
        require(LEGACY_SOCKET.is_symlink() and LEGACY_SOCKET.resolve() == IPC / "ha-ota.sock"
                and (IPC / "approved-homeassistant.json").is_file(), "export_endpoints_drift")
        lifecycle("start", APP, "app_starts")
        require(docker_id("manager") == precreated and manager_bind(precreated, str(IPC))
                and inspect_value(docker_id("homeassistant"), ".Image") == ha_image,
                "app_identity_after_start")
    except Exception as error:
        emit("INSTALL_STOP", reason=str(error) if isinstance(error, ValueError) else type(error).__name__,
             subprocess_rc=getattr(error, "returncode", None))
        if STEPS["app_stops"] or STEPS["ota_stops"]:
            try:
                rollback(context)
            except Exception as secondary:
                emit("ROLLBACK_STOP", reason=str(secondary) if isinstance(secondary, ValueError) else type(secondary).__name__,
                     subprocess_rc=getattr(secondary, "returncode", None))
        raise

    STEPS["step"] = "wait_for_product_completion"
    wait_completion(probe, precreated, original)
    STEPS["step"] = "fresh_final_audit"
    probe["result"].clear()
    probe["main"](post_restart=True)
    validate_state(device, original, broker)
    require(docker_id("manager") == precreated, "final_manager_identity_drift")
    emit("PASS", evidence=probe["result"], host_transaction_unchanged=True, broker_unchanged=True)


try:
    execute(INPUT_BUNDLE, EXECUTION_MODE)
except Exception as error:
    emit("STOP", reason=str(error) if isinstance(error, ValueError) else type(error).__name__,
         subprocess_rc=getattr(error, "returncode", None))
    sys.exit(1)
```

</details>
