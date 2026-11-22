"""Operator-run backup of the R8 spare T1's original application state."""

import argparse
import base64
from contextlib import closing
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import re
import shutil
import sqlite3
import stat
import subprocess
import sys
import tarfile
import tempfile
from zipfile import ZipFile

REPO = "chrenguo-stack/HomeAssistant"
ARTIFACT = 14717720726
ZIP_SHA = "287307871e3cc4262a3f010888f71001cb2e705f1d87f637742e995c5d015106"
PYZ_SHA = "f39629268ffeab9906f9de8cb60362d604d5b9150ef4c13571926b00921e6b84"
RUN_ID = "n3w-r8-current-backup-20261122-01"
WORK = Path("/var/tmp") / RUN_ID
UNIT = "n3wfc4-services-activation.service"
BROKER_UNIT = "n3wfc4-broker-activation.service"
LEGACY = "n3w-t1-ha-ota.service"
BACKUP = "homeassistant-preupgrade.tar.gz.enc"
METADATA = "homeassistant-preupgrade.metadata.json"
RECEIPT = "receipt.json"
APP_NAMES = ("homeassistant", "manager")
HA = Path("/var/lib/n3wfc4-homeassistant")
MANAGER = Path("/var/lib/greenhouse-manager/manager")
REPLAY = Path("/var/lib/greenhouse-manager/n3w")
ROOTS = (HA, MANAGER, REPLAY)
ROOT_KEY = Path("/var/lib/greenhouse-manager/identity/system-root.key")
COMPOSE = Path("/etc/n3wfc4/docker-compose.yml")
ENV = Path("/etc/n3wfc4/docker-compose.env")
ACTIVATION_ENV = Path("/etc/n3wfc4/broker-activation.env")
HA_CONFIG = Path("/opt/HomeAssistant/infra/n3w-t1/production/homeassistant-configuration.yaml")
EXPECTED_UNIT_SHA = "9f7fecb6135284ceb2c9a293ed791509e6820e16a916b17b0d346334073de1d8"
IMAGES = {
    "broker": ("local/n3w-mosquitto:2.1.2-3184566d", "sha256:df265f1e2b2e3dc35d5eb194e698c598e01c5ebca370da307b34332f9bf0a563"),
    "manager": ("local/greenhouse-manager:fresh-44e7d7472714", "sha256:1471828ab07cf9b71c01a6e78994711a5954f0a178b8be087a28bb65a967c7d2"),
    "homeassistant": ("local/n3w-homeassistant:2026.10.4-5881590f", "sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365"),
}
TRANSACTIONS = (
    ("COMMITTED", "39c076050122402f93b4956523129e4555df210d8e45caea1ababd88f1ee3d0b"),
    (None, None),
    ("ROLLED_BACK", "a427bef98d2886234bf706eb1347f09148429e44c79ab08f01e1071dd0722492"),
)
PASS = "R8_CURRENT_BACKUP_PASS"
MIN_SPACE = 64 * 1024 * 1024


def need(condition, reason):
    if not condition:
        raise ValueError(reason)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def file_sha(path):
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


def write_record(name, record):
    temp = WORK / (name + ".tmp")
    with temp.open("w") as stream:
        json.dump(record, stream, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temp.replace(WORK / name)
    fd = os.open(WORK, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def reason(error):
    if isinstance(error, subprocess.CalledProcessError):
        return f"command_failed:{Path(error.cmd[0]).name}:{error.returncode}"
    if isinstance(error, ValueError) or type(error).__name__ in {"UpdaterError", "UpdaterV2Error"}:
        code = str(error).partition(":")[0]
        if re.fullmatch(r"[a-z][a-z0-9_]{2,110}", code):
            return code
    return type(error).__name__


def sanity_remote():
    need(os.geteuid() == 0 and sys.platform == "linux" and platform.machine() in {"aarch64", "arm64"}
         and sys.version_info >= (3, 11), "unexpected_spare_environment")
    os.umask(0o077)
    for key in ("DOCKER_CONTEXT", "DOCKER_TLS", "DOCKER_TLS_VERIFY"):
        os.environ.pop(key, None)
    os.environ["DOCKER_HOST"] = "unix:///var/run/docker.sock"


def private_work():
    info = WORK.lstat()
    need(stat.S_ISDIR(info.st_mode) and info.st_uid == 0 and stat.S_IMODE(info.st_mode) == 0o700,
         "backup_work_directory_invalid")


def regular(path, mode=None):
    info = path.lstat()
    need(path.resolve() == path and stat.S_ISREG(info.st_mode) and info.st_uid == 0 and info.st_nlink == 1
         and (mode is None or stat.S_IMODE(info.st_mode) == mode), "spare_file_metadata_changed")


def unit_props(host, unit, *names):
    raw = host._run(("systemctl", "show", unit, *(f"--property={key}" for key in names)), timeout=20).stdout
    fields = dict(line.split("=", 1) for line in raw.decode().splitlines() if "=" in line)
    need(all(key in fields for key in names), "systemd_properties_missing")
    return fields


def transactions(store, usb, canonical):
    records = (store.read(), store.read_legacy(), usb.read())
    result = tuple((doc["status"], sha(canonical(doc))) if doc else (None, None) for doc in records)
    need(result == TRANSACTIONS, "ota_transaction_baseline_changed")
    return result


def verify_bind_mounts(host, snapshot):
    expected = {
        "homeassistant": {(str(HA), "/config")},
        "manager": {(str(MANAGER), str(MANAGER)), (str(REPLAY), str(REPLAY))},
        "broker": {("/var/lib/n3wfc4-broker", "/mosquitto/data")},
    }
    for service, binding in expected.items():
        container = snapshot["runtime"][service]["container_id"]
        mounts = json.loads(host._run(("docker", "inspect", "-f", "{{json .Mounts}}", container), timeout=20).stdout)
        writable = {(row["Source"], row["Destination"]) for row in mounts if row["RW"] and row["Type"] == "bind"}
        need(writable == binding and all(not row["RW"] or row["Type"] in {"bind", "tmpfs"} for row in mounts),
             "writable_mounts_changed")


def baseline(host):
    snapshot = host.observe_v2()
    host._validate_converged_health_v2(snapshot)
    for service, (ref, image_id) in IMAGES.items():
        runtime = snapshot["runtime"][service]
        need(runtime["image_ref"] == ref and runtime["image_id"] == image_id == host.image_id(ref)
             and runtime["restart_count"] == 0, "spare_runtime_identity_changed")
    verify_bind_mounts(host, snapshot)
    return snapshot


def assert_apps_stopped(host, before):
    fields = unit_props(host, UNIT, "ActiveState", "SubState", "MainPID", "ControlPID", "NRestarts")
    need((fields["ActiveState"], fields["SubState"]) in {("inactive", "dead"), ("failed", "failed")}
         and all(fields[key] == "0" for key in ("MainPID", "ControlPID", "NRestarts")), "application_stop_not_verified")
    for service in APP_NAMES:
        need(host._running_count(service) == 0, "application_container_still_running")
        state = json.loads(host._run(("docker", "inspect", "-f", "{{json .State}}",
                                      before["runtime"][service]["container_id"]), timeout=20).stdout)
        need(state["Status"] == "exited" and not state["Running"] and not state["Restarting"]
             and state["Pid"] == 0 and not state["OOMKilled"] and not state["Error"], "application_container_stop_unverified")
    running = host._run(("docker", "ps", "-q"), timeout=20).stdout.decode().splitlines()
    for container in running:
        mounts = json.loads(host._run(("docker", "inspect", "-f", "{{json .Mounts}}", container), timeout=20).stdout)
        for row in mounts:
            if row["Type"] == "bind" and row["RW"]:
                source = Path(row["Source"]).resolve()
                need(not any(source.is_relative_to(root) or root.is_relative_to(source) for root in ROOTS),
                     "protected_tree_has_running_container_writer")


def check_databases(root):
    locations = [root / HA.relative_to("/") / "home-assistant_v2.db",
                 root / MANAGER.relative_to("/") / "manager-state.sqlite3",
                 root / REPLAY.relative_to("/") / "replay.sqlite3"]
    for tree in (root / MANAGER.relative_to("/"), root / REPLAY.relative_to("/")):
        locations.extend(path for path in tree.rglob("*") if path.suffix in {".db", ".sqlite", ".sqlite3"})
    databases = sorted(set(locations))
    cursors = None
    with tempfile.TemporaryDirectory(prefix="sqlite-check-", dir=WORK / "plain") as temporary:
        for index, database in enumerate(databases):
            target = Path(temporary) / str(index)
            for suffix in ("", "-wal", "-journal"):
                source = Path(str(database) + suffix)
                if suffix and not source.exists() and not source.is_symlink():
                    continue
                need(source.is_file() and not source.is_symlink(), "protected_database_missing_or_invalid")
                shutil.copyfile(source, Path(str(target) + suffix))
            with closing(sqlite3.connect(target.as_uri() + "?mode=rw", uri=True, timeout=10)) as conn:
                need(conn.execute("PRAGMA quick_check").fetchall() == [("ok",)], "protected_database_quick_check_failed")
                if database == locations[2] and conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='n3w_canonical_cursors'"
                ).fetchone():
                    cursors = read_cursors(conn)
    return len(databases), cursors


def protect(host, provider, record):
    plain = WORK / "plain"
    plain.mkdir(mode=0o700)
    snapshot = plain / "snapshot"
    snapshot.mkdir(mode=0o700)
    sources = (*ROOTS, *record["launch_files"])
    for root in ROOTS:
        provider(work_root=plain, ha_data_root=root)._validate_source_tree()
    host._run(("/usr/bin/cp", "-a", "--parents", "--", *map(str, sources), str(snapshot)),
              timeout=50)
    for path in sources:
        copied = snapshot / path.relative_to("/")
        host._run(("/usr/bin/diff", "-qr", "--no-dereference", "--", str(path), str(copied)), timeout=30)
    for path, expected in record["launch_files"].items():
        need(file_sha(snapshot / path.relative_to("/")) == expected, "launch_configuration_snapshot_changed")
    tx = sha(os.urandom(32))
    protected = provider(work_root=plain, ha_data_root=snapshot, product_config=HA_CONFIG)
    destination = os.open(WORK, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        sealed = protected.create(destination, tx)
        protected.verify(destination, tx, sealed)
        restored = plain / "restored"
        protected.restore_to_stage(destination, tx, sealed, restored)
        verified_sqlite, cursors = check_databases(restored)
    finally:
        os.close(destination)
    shutil.rmtree(plain)
    return {
        "transaction_id_sha256": tx, "backup": sealed.public(), "metadata_sha256": file_sha(WORK / METADATA),
        "isolated_restore_verified": True, "sqlite_databases_verified": verified_sqlite,
    }, cursors


def recovery_start():
    if (WORK / "resume-required").is_file():
        subprocess.run(("systemctl", "start", UNIT), check=True, timeout=190, capture_output=True)
        (WORK / "resume-required").unlink()


def read_cursors(connection):
    rows = connection.execute("SELECT node_id, boot_session_hex, seq FROM n3w_canonical_cursors")
    return {node: (boot, seq) for node, boot, seq in rows}


def manager_cursors():
    from n3w_t1_core_updater_ha_data_evidence import read_local_database
    from n3w_t1_core_updater_v2_common import UpdaterV2Error

    try:
        with read_local_database(REPLAY / "replay.sqlite3") as conn:
            return read_cursors(conn)
    except (OSError, sqlite3.Error, UpdaterV2Error):
        return None


def manager_receive_since(previous):
    if previous is None:
        return "EVIDENCE_UNAVAILABLE"
    current = manager_cursors()
    if current is None:
        return "EVIDENCE_UNAVAILABLE"
    for node, (boot, seq) in current.items():
        if node not in previous or boot != previous[node][0] or seq > previous[node][1]:
            return "FRESH_CURSOR_OBSERVED"
    return "NO_FRESH_CURSOR_OBSERVED"


def worker():
    from n3w_t1_core_updater_ha_backup import ProtectedHaDataBackup
    from n3w_t1_core_updater_ha_usb_state import HaUsbStateStore
    from n3w_t1_core_updater_host import LocalHost
    from n3w_t1_core_updater_v2_common import canonical
    from n3w_t1_core_updater_v2_state import V2StateStore

    host = LocalHost()
    store, usb = V2StateStore(), HaUsbStateStore()
    receipt = {"run_id": RUN_ID, "status": "R8_CURRENT_BACKUP_FAILED", "application_stop_attempted": False}

    def phase(name):
        write_record("phase.json", {"run_id": RUN_ID, "phase": name})

    try:
        need(store.root.is_dir() and not store.root.is_symlink(), "ota_transaction_root_missing")
        with store.lock():
            phase("PRECHECK")
            before = baseline(host)
            transactions(store, usb, canonical)
            app = unit_props(host, UNIT, "FragmentPath", "DropInPaths", "NeedDaemonReload", "UnitFileState")
            need(app["NeedDaemonReload"] == "no" and not app["DropInPaths"] and app["UnitFileState"] == "enabled",
                 "standard_application_unit_changed")
            require_inactive = (LEGACY, "n3w-t1-ha-recovery-startup.service", "n3w-t1-ha-recovery-retry.timer",
                                "n3w-t1-ha-ota-ipc.socket")
            need(all(host._systemctl("is-active", unit) in {"inactive", "unknown"} for unit in require_inactive),
                 "other_ota_supervision_active")
            app_file = Path(app["FragmentPath"])
            regular(app_file)
            need(file_sha(app_file) == EXPECTED_UNIT_SHA, "standard_application_unit_changed")
            regular(COMPOSE, 0o644)
            regular(ENV, 0o600)
            regular(ROOT_KEY, 0o600)
            ProtectedHaDataBackup(work_root=WORK)._root_key()
            launch = (COMPOSE, ENV, app_file, ACTIVATION_ENV, HA_CONFIG)
            for path in launch:
                regular(path)
            launch_hashes = {path: file_sha(path) for path in launch}
            for path in ROOTS:
                need(path.resolve(strict=True) == path and path.is_dir(), "protected_bind_path_changed")
            sizes = host._run(("/usr/bin/du", "-sbx", "--", *map(str, ROOTS)), timeout=20).stdout.splitlines()
            allocated_budget = max(MIN_SPACE, 6 * (sum(int(row.split()[0]) for row in sizes)
                                                   + sum(path.stat().st_size for path in launch)))
            need(len(sizes) == len(ROOTS) and shutil.disk_usage(WORK).free >= allocated_budget,
                 "spare_backup_space_insufficient")
            previous_cursors = None
            receipt["application_stop_attempted"] = True
            write_record("resume-required", {"run_id": RUN_ID})
            try:
                phase("STOP_APPLICATION")
                stop = host._run(("systemctl", "stop", "--job-mode=fail", UNIT), timeout=180, check=False)
                receipt["stop_command_exit"] = stop.returncode
                assert_apps_stopped(host, before)
                host.broker_continuity(before["runtime"]["broker"])
                phase("VERIFY_ISOLATED_RESTORE")
                protected, previous_cursors = protect(host, ProtectedHaDataBackup, {"launch_files": launch_hashes})
                receipt.update(protected)
                assert_apps_stopped(host, before)
            except Exception as error:
                receipt["backup_error"] = reason(error)
            finally:
                try:
                    phase("RESUME_APPLICATION")
                finally:
                    recovery_start()
            phase("VERIFY_ORIGINAL_RUNTIME")
            host.wait_services(timeout=135)
            after = baseline(host)
            host.broker_continuity(before["runtime"]["broker"])
            need(all(file_sha(path) == expected for path, expected in launch_hashes.items()), "launch_configuration_changed")
            need(after["compose_render_sha256"] == before["compose_render_sha256"]
                 and all(after["runtime"][s]["runtime_contract_sha256"] == before["runtime"][s]["runtime_contract_sha256"]
                         for s in APP_NAMES), "application_runtime_contract_changed")
            transactions(store, usb, canonical)
            receipt.update(original_stack_healthy=True, broker_same_instance=True, transactions_unchanged=True,
                           mqtt_authenticated=after["mqtt_authenticated"],
                           manager_receive_observation=manager_receive_since(previous_cursors),
                           homeassistant_http_status=after["homeassistant_http_status"])
            if "backup_error" not in receipt:
                receipt["status"] = PASS
    except Exception as error:
        receipt["error"] = reason(error)
    write_record(RECEIPT, receipt)
    return 0 if receipt["status"] == PASS else 1


def collect():
    folder = WORK / RECEIPT
    if not folder.exists():
        stage = (WORK / "phase.json").read_text().strip() if (WORK / "phase.json").is_file() else "no_worker_receipt"
        print(f"R8 备份尚无终态 {stage}", file=sys.stderr)
        return 2
    record = json.loads(folder.read_bytes())
    print(json.dumps(record, sort_keys=True), file=sys.stderr)
    if record["status"] != PASS:
        return 1
    with tarfile.open(mode="w|", fileobj=sys.stdout.buffer) as archive:
        for name in (BACKUP, METADATA, RECEIPT):
            archive.add(WORK / name, arcname=name, recursive=False)
    return 0


def remote(mode, payload):
    sanity_remote()
    if mode == "collect":
        private_work()
        return collect()

    package = base64.b64decode(payload, validate=True)
    need(sha(package) == PYZ_SHA, "recovery_pyz_sha_mismatch")
    python = "/usr/bin/python3"
    WORK.mkdir(mode=0o700)
    private_work()
    runner = WORK / "executor.py"
    runner.write_bytes(base64.b64decode(REMOTE_SCRIPT, validate=True))
    (WORK / "ha-recovery.pyz").write_bytes(package)
    result = subprocess.run((
        "systemd-run", "--wait", "--unit=" + RUN_ID, "--property=Type=exec",
        "--property=RuntimeMaxSec=900", "--property=TimeoutStopSec=210",
        f"--property=ExecStopPost={python} -I -B {runner} recover",
        python, "-I", "-B", str(runner), "worker",
    ), stdout=sys.stderr, check=False)
    if result.returncode != 0:
        print(f"R8 detached worker exit={result.returncode}", file=sys.stderr)
    return collect()


def operator():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ssh", required=True)
    parser.add_argument("--collect", action="store_true")
    args = parser.parse_args()
    need(bool(args.ssh.strip()), "missing_spare_ssh_target")
    root = Path.home() / ".n3w-r8-private"
    root.mkdir(mode=0o700, exist_ok=True)
    info = root.lstat()
    need(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and not stat.S_IMODE(info.st_mode) & 0o077,
         "mac_backup_directory_not_private")
    final = root / RUN_ID
    need(not final.exists() and not final.is_symlink(), "mac_backup_destination_already_exists")
    need(shutil.disk_usage(root).free >= MIN_SPACE, "mac_backup_space_insufficient")
    mode = "collect" if args.collect else "run"
    script = Path(__file__).read_bytes()
    package = b""
    if mode == "run":
        zipped = subprocess.check_output(("gh", "api", f"repos/{REPO}/actions/artifacts/{ARTIFACT}/zip"), timeout=120)
        need(sha(zipped) == ZIP_SHA, "recovery_zip_sha_mismatch")
        with ZipFile(io.BytesIO(zipped)) as archive:
            package = archive.read("ha-recovery.pyz")
        need(sha(package) == PYZ_SHA, "recovery_pyz_sha_mismatch")
    header = f"REMOTE_MODE = {mode!r}\nREMOTE_PAYLOAD = {base64.b64encode(package)!r}\nREMOTE_SCRIPT = {base64.b64encode(script)!r}\n".encode()
    command = ('if [ "$(id -u)" -eq 0 ]; then exec /usr/bin/python3 -I -B -; '
               'else exec sudo -n /usr/bin/python3 -I -B -; fi')
    print("等待备用 T1 返回备份及恢复校验结果。", flush=True)
    with tempfile.TemporaryDirectory(prefix=".r8-receive-", dir=root) as temporary:
        path = Path(temporary)
        delivery = path / "delivery.tar"
        with delivery.open("wb") as output:
            result = subprocess.run(("ssh", "-o", "StrictHostKeyChecking=yes", "-o", "ForwardAgent=no",
                                     "-o", "ClearAllForwardings=yes", "-o", "ConnectTimeout=10", "-T",
                                     "--", args.ssh, command), input=header + script, stdout=output, check=False)
        if result.returncode:
            return result.returncode
        ready = path / "ready"
        ready.mkdir(mode=0o700)
        with tarfile.open(delivery, mode="r:") as archive:
            members = archive.getmembers()
            need(len(members) == 3 and {item.name for item in members} == {BACKUP, METADATA, RECEIPT}
                 and all(item.isfile() for item in members), "backup_transfer_manifest_invalid")
            for item in members:
                with archive.extractfile(item) as source, (ready / item.name).open("xb") as target:
                    shutil.copyfileobj(source, target)
                    target.flush()
                    os.fsync(target.fileno())
        record = json.loads((ready / RECEIPT).read_bytes())
        need(record["run_id"] == RUN_ID and record["status"] == PASS
             and record["original_stack_healthy"] is True and record["isolated_restore_verified"] is True
             and record["broker_same_instance"] is True, "backup_receipt_not_eligible")
        need((ready / BACKUP).stat().st_size == record["backup"]["archive_size_bytes"]
             and file_sha(ready / BACKUP) == record["backup"]["archive_sha256"]
             and file_sha(ready / METADATA) == record["metadata_sha256"], "backup_transfer_digest_mismatch")
        os.rename(ready, final)
    print("R8_MAC_ENCRYPTED_COPY_VERIFIED=true")
    print(f"PRIVATE_BACKUP_DIR={final}")
    return 0


if __name__ == "__main__":
    try:
        if "REMOTE_MODE" in globals():
            rc = remote(REMOTE_MODE, REMOTE_PAYLOAD)
        elif sys.argv[1:] in (["worker"], ["recover"]):
            sanity_remote()
            private_work()
            if sys.argv[1] == "recover":
                try:
                    recovery_start()
                finally:
                    if (WORK / "plain").is_dir():
                        shutil.rmtree(WORK / "plain")
                rc = 0
            else:
                need(file_sha(WORK / "ha-recovery.pyz") == PYZ_SHA, "recovery_pyz_sha_mismatch")
                sys.path.insert(0, str(WORK / "ha-recovery.pyz"))
                rc = worker()
        else:
            os.umask(0o077)
            rc = operator()
    except Exception as error:
        print(f"R8 backup stopped: {reason(error)}", file=sys.stderr)
        rc = 1
    sys.exit(rc)
