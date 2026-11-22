"""One-time, approved transition of the spare T1 from legacy HA OTA supervision."""

import base64
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import signal
import stat
import subprocess
import sys
import time


APP = "n3wfc4-services-activation.service"
LEGACY = "n3w-t1-ha-ota.service"
OVERLAY = Path("/opt/HomeAssistant/infra/n3w-t1/production/docker-compose.ha-ota.yml")
DROPIN = "95-n3w-ha-ota.conf"
OVERLAY_HASH = "1b0fd19cb3f8047d0ce50ecfdd69f0e71d8256bed2198de10d7d78c39eacd618"
DROPIN_HASH = "cee2d95971a1d91adeec4f7974d0bac1f4b7eab379168e91459d3d07641f1800"
APP_HASH = "9f7fecb6135284ceb2c9a293ed791509e6820e16a916b17b0d346334073de1d8"
LEGACY_HASH = "af8d9755ba13d9300fb5318d077e5d20078229814fdc29e4127806ef78ddb370"
FAULT_DROPIN = Path("/etc/systemd/system/n3w-t1-ha-ota.service.d/90-u9plus-fault-acceptance.conf")
FAULT_DROPIN_HASH = "dcb4e566c12e6f57add6bcfb100a69001b3146b47abf4cb824a166726938aa6a"
FAULT_DAEMON = Path(
    "/var/lib/n3w-t1-core-updater/u9plus-fault-acceptance-r1/candidate-tools/"
    "n3w_t1_core_updater_ha_daemon.py"
)
PACKAGE_HASH = "f39629268ffeab9906f9de8cb60362d604d5b9150ef4c13571926b00921e6b84"
LEGACY_MOUNT = ("bind", "/run/n3w-t1-ota", "/run/n3w/t1-ota", False)
LEGACY_SOCKET = Path("/run/n3w-t1-ota/ha-ota.sock")
APP_SERVICES = ("manager", "homeassistant")
IMAGE_IDS = {
    "broker": "sha256:df265f1e2b2e3dc35d5eb194e698c598e01c5ebca370da307b34332f9bf0a563",
    "manager": "sha256:1471828ab07cf9b71c01a6e78994711a5954f0a178b8be087a28bb65a967c7d2",
    "homeassistant": "sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365",
}
REFS = {
    "broker": "local/n3w-mosquitto:2.1.2-3184566d",
    "manager": "local/greenhouse-manager:fresh-44e7d7472714",
    "homeassistant": "local/n3w-homeassistant:2026.10.4-5881590f",
}
TRANSACTIONS = (
    ("COMMITTED", "39c076050122402f93b4956523129e4555df210d8e45caea1ababd88f1ee3d0b"),
    (None, None),
    ("ROLLED_BACK", "a427bef98d2886234bf706eb1347f09148429e44c79ab08f01e1071dd0722492"),
)


def digest(payload):
    return hashlib.sha256(payload).hexdigest()


def need(condition, error):
    if not condition:
        raise ValueError(error)


class SystemdPropertiesMissing(ValueError):
    def __init__(self, unit, properties):
        super().__init__("systemd_properties_missing")
        self.unit = unit
        self.properties = sorted(properties)


def error_code(error):
    code = str(error).split(":", 1)[0]
    return code if re.fullmatch(r"[a-z][a-z0-9_]{2,95}", code) else type(error).__name__


def error_details(error):
    if isinstance(error, SystemdPropertiesMissing):
        return {"systemd_unit": error.unit, "missing_properties": error.properties}
    return {}


def progress(phase):
    print(f"R7_PHASE={phase}", file=sys.stderr, flush=True)


def checked_file(path, expected_hash):
    metadata = path.lstat()
    need(
        stat.S_ISREG(metadata.st_mode) and metadata.st_uid == 0
        and not metadata.st_mode & 0o022 and digest(path.read_bytes()) == expected_hash,
        "installed_file_binding_mismatch",
    )
    return path


def sync_parent(path):
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def unit_props(unit, *required, optional=()):
    args = ["systemctl", "show", "--all", "--no-pager"]
    for field in (*required, *optional):
        args += ["--property", field]
    result = subprocess.run([*args, unit], capture_output=True, timeout=20, check=True)
    props = dict(line.split("=", 1) for line in result.stdout.decode().splitlines())
    missing = set(required) - props.keys()
    if missing:
        raise SystemdPropertiesMissing(unit, missing)
    for field in optional:
        props.setdefault(field, "")
    return props


def systemctl(action, unit=None):
    args = ["systemctl", action]
    if action in {"start", "stop"}:
        args += ["--job-mode=fail"]
    if unit:
        args.append(unit)
    result = subprocess.run(args, capture_output=True, timeout=205, check=False)
    need(result.returncode == 0, f"systemctl_{action}_failed")


def apps_quiesced(host, project):
    for service in APP_SERVICES:
        output = host._run((
            "docker", "ps", "-q", "--filter", f"label=com.docker.compose.project={project}",
            "--filter", f"label=com.docker.compose.service={service}",
        ), timeout=15).stdout
        need(not output.strip(), f"{service}_still_running")


def run():
    from n3w_t1_core_updater_ha_usb_state import HaUsbStateStore
    from n3w_t1_core_updater_host import EXPECTED_EXECSTART, EXPECTED_EXECSTOP
    from n3w_t1_core_updater_host import EXPECTED_LISTENERS, PROJECT, LocalHost
    from n3w_t1_core_updater_v2_common import canonical
    from n3w_t1_core_updater_v2_state import V2StateStore

    for variable in ("DOCKER_CONTEXT", "DOCKER_TLS", "DOCKER_TLS_VERIFY"):
        os.environ.pop(variable, None)
    os.environ["DOCKER_HOST"] = "unix:///var/run/docker.sock"
    host = LocalHost()
    store = V2StateStore()
    usb_store = HaUsbStateStore()
    prepare_path = store.root / "homeassistant-usb-prepare.json"

    def transaction_snapshot():
        rows = []
        usb_record = usb_store.read()
        for doc in (store.read(), store.read_legacy(), usb_record):
            rows.append((doc["status"], digest(canonical(doc))) if doc else (None, None))
        need(tuple(rows) == TRANSACTIONS, "ota_transaction_evidence_changed")
        need(usb_record.get("phase") == "U13B_ROLLED_BACK", "legacy_usb_phase_not_terminal")
        need(not prepare_path.is_symlink(), "legacy_prepare_state_invalid")
        return digest(prepare_path.read_bytes()) if prepare_path.exists() else None

    def app_props():
        return unit_props(APP, "LoadState", "ActiveState", "UnitFileState",
                          "FragmentPath", "DropInPaths", "NeedDaemonReload",
                          "Requires", "ExecStart", "ExecStop")

    def legacy_props():
        return unit_props(LEGACY, "LoadState", "ActiveState", "UnitFileState",
                          "FragmentPath", "DropInPaths", "NeedDaemonReload",
                          "RequiredBy", "BoundBy", "ConsistsOf", "PropagatesStopTo",
                          "MainPID", "ExecStart", "RefuseManualStop",
                          optional=("ExecStop", "ExecStopPost"))

    def supervision(legacy, active):
        props = app_props()
        need(props["LoadState"] == "loaded" and props["ActiveState"] == active
             and props["UnitFileState"] == "enabled"
             and props["NeedDaemonReload"] == "no", "application_unit_state_mismatch")
        checked_file(Path(props["FragmentPath"]), APP_HASH)
        need((LEGACY in props["Requires"].split()) == legacy, "legacy_dependency_mismatch")
        if legacy:
            drop = Path(props["DropInPaths"])
            need(drop.is_absolute() and drop.name == DROPIN and drop.parent.name == APP + ".d",
                 "legacy_dropin_path_mismatch")
            checked_file(drop, DROPIN_HASH)
        else:
            need(not props["DropInPaths"], "unexpected_application_dropin")
            host._service_unit()
            drop = None
        for field, expected in (("ExecStart", EXPECTED_EXECSTART), ("ExecStop", EXPECTED_EXECSTOP)):
            prefix, argv = expected.split("=", 1)
            need(prefix == field, "expected_systemd_command_invalid")
            if legacy:
                arg = '-f ${N3WFC4_COMPOSE_FILE}'
                argv = argv.replace(arg, f"{arg} -f {OVERLAY}", 1)
            loaded = re.findall(r"argv\[\]=(.*?)\s+;", props[field])
            need(loaded == [argv], "loaded_application_command_mismatch")
        return drop

    def legacy_daemon(active, enabled, expected_pid=None):
        props = legacy_props()
        need(props["LoadState"] == "loaded" and props["NeedDaemonReload"] == "no",
             "legacy_daemon_load_state_mismatch")
        need(props["ActiveState"] == active, "legacy_daemon_active_state_mismatch")
        need(props["UnitFileState"] == enabled, "legacy_daemon_enablement_mismatch")
        checked_file(Path(props["FragmentPath"]), LEGACY_HASH)
        need(props["DropInPaths"] == str(FAULT_DROPIN), "legacy_fault_dropin_path_mismatch")
        checked_file(FAULT_DROPIN, FAULT_DROPIN_HASH)
        loaded = re.findall(r"argv\[\]=(.*?)\s+;", props["ExecStart"])
        need(loaded == [f"/usr/bin/python3 {FAULT_DAEMON}"], "legacy_fault_start_command_mismatch")
        # Empty stop commands can be omitted by systemctl. Both files that
        # define this unit have exact-byte checks and contain no stop hooks.
        need(set(props["RequiredBy"].split()) <= {APP} and not any(
            props[k] for k in ("BoundBy", "ConsistsOf", "PropagatesStopTo", "ExecStop", "ExecStopPost")
        ), "legacy_daemon_extra_dependencies_or_commands")
        need(props["RefuseManualStop"] == "no", "legacy_daemon_manual_stop_refused")
        pid = int(props["MainPID"])
        if active == "active":
            need(pid > 0 and LEGACY_SOCKET.is_socket(), "legacy_process_or_socket_missing")
            need(expected_pid is None or pid == expected_pid, "legacy_daemon_pid_changed")
        else:
            need(pid == 0 and not LEGACY_SOCKET.is_socket(), "legacy_daemon_not_quiesced")
        return pid

    def container_shape(service, runtime, legacy):
        item = json.loads(host._run(("docker", "inspect", runtime["container_id"]), timeout=20).stdout)[0]
        need(all(m["Type"] in {"bind", "tmpfs"} for m in item["Mounts"]),
             "unexpected_runtime_volume_type")
        mounts = {(m["Type"], m["Source"], m["Destination"], m["RW"])
                  for m in item["Mounts"] if m["Type"] == "bind"}
        if legacy and service == "manager":
            need(LEGACY_MOUNT in mounts, "legacy_manager_mount_missing")
            mounts.remove(LEGACY_MOUNT)
        if service == "manager":
            flag = [s.split("=", 1)[1] for s in item["Config"]["Env"]
                    if s.startswith("GH_N3W_T1_OTA_ENABLED=")]
            need(flag == ["true"] if legacy else flag in ([], ["false"]),
                 "manager_legacy_ota_flag_mismatch")
        return mounts

    def mount_shape(service, compose):
        volumes = compose["services"][service].get("volumes", [])
        need(all(v["type"] == "bind" and Path(v["source"]).is_absolute() for v in volumes),
             "unexpected_application_volume_type")
        return {(v["type"], v["source"], v["target"], not v.get("read_only", False))
                for v in volumes}

    def wait_healthy(legacy, before, expected_mounts, prepare_hash):
        deadline = time.monotonic() + 150
        last = "health_timeout"
        while True:
            try:
                now = ({name: host._runtime(name) for name in REFS} if legacy
                       else host.inspect()["runtime"])
                need(now["broker"] == before["broker"], "broker_identity_changed")
                for name in APP_SERVICES:
                    need(all(now[name][key] == before[name][key] for key in (
                        "image_ref", "image_id", "platform", "network_mode",
                    )), f"{name}_runtime_binding_changed")
                    need(container_shape(name, now[name], legacy) == expected_mounts[name],
                         f"{name}_application_mounts_changed")
                need(host._listener_snapshot() == EXPECTED_LISTENERS, "listener_contract_drift")
                http = host._homeassistant_http_status(allow_unavailable=True)
                need(http in (200, 401), "homeassistant_http_unavailable")
                auth = {name: host._mqtt_authenticated(name) for name in APP_SERVICES}
                need(all(auth.values()), "application_mqtt_not_yet_authenticated")
                need(transaction_snapshot() == prepare_hash, "legacy_prepare_state_changed")
                return {"http_status": http, "mqtt_authenticated": auth}
            except Exception as error:
                last = error_code(error)
            if time.monotonic() >= deadline:
                raise ValueError(last)
            time.sleep(3)

    def restore(drop, backup, new_start_attempted, legacy_pid):
        # The pre-existing fault acceptance daemon can re-enter a USB oracle
        # at startup even after the durable U13B record is terminal.
        legacy_daemon("active", "enabled", legacy_pid)
        if new_start_attempted:
            systemctl("stop", APP)
            try:
                apps_quiesced(host, PROJECT)
            except ValueError:
                host._run((*host._compose_argv(), "stop", "homeassistant", "manager"), timeout=120)
                apps_quiesced(host, PROJECT)
        if not os.path.lexists(drop):
            checked_file(backup, DROPIN_HASH)
            os.link(backup, drop, follow_symlinks=False)
            sync_parent(drop)
        checked_file(drop, DROPIN_HASH)
        systemctl("daemon-reload")
        legacy_daemon("active", "enabled", legacy_pid)
        if app_props()["ActiveState"] != "active":
            systemctl("start", APP)
        supervision(True, "active")

    progress("PRECHECK")
    need(store._existing_root(), "transaction_root_missing")
    with store.lock():
        prepare_hash = transaction_snapshot()
        drop = supervision(True, "active")
        legacy_pid = legacy_daemon("active", "enabled")
        checked_file(OVERLAY, OVERLAY_HASH)
        parent = drop.parent.lstat()
        need(stat.S_ISDIR(parent.st_mode) and parent.st_uid == 0 and not parent.st_mode & 0o022
             and drop.resolve() == drop, "legacy_dropin_directory_invalid")
        backup = drop.with_name(".95-n3w-ha-ota.conf.r7-backup")
        need(not os.path.lexists(backup), "legacy_dropin_backup_already_exists")
        host._activation_env()
        host._system_health_v2()
        eligibility = json.loads(host._run((
            "/usr/local/sbin/n3w-t1-clean-reference-r2a", "eligibility", "--phase", "services",
        ), timeout=20).stdout)
        need(eligibility.get("status") == "PASS" and eligibility.get("phase") == "services"
             and eligibility.get("transaction_stage") == "RUNTIME_STARTED",
             "standard_application_start_not_eligible")
        compose = host.render_compose()
        bindings, modes = host._image_binding_authority_v2(compose)
        need(bindings == REFS and modes["homeassistant"] == "dynamic"
             and modes["manager"] == "dynamic", "base_image_bindings_changed")
        before = {name: host._runtime(name) for name in REFS}
        for name, ref in REFS.items():
            need(before[name]["image_ref"] == ref
                 and before[name]["image_id"] == host.image_id(ref) == IMAGE_IDS[name]
                 and compose["services"][name]["pull_policy"] == "never",
                 f"{name}_local_image_mismatch")
        expected_mounts = {name: mount_shape(name, compose) for name in APP_SERVICES}
        for name, targets in (
            ("manager", {"/var/lib/greenhouse-manager/manager", "/var/lib/greenhouse-manager/n3w"}),
            ("homeassistant", {"/config"}),
        ):
            need(targets <= {m[2] for m in expected_mounts[name]}, "application_data_mount_missing")
            need(container_shape(name, before[name], True) == expected_mounts[name],
                 "base_application_mount_mismatch")
        wait_healthy(True, before, expected_mounts, prepare_hash)

        report = {"backup_path": str(backup), "homeassistant_version": "2026.10.4"}
        new_start_attempted = False
        os.link(drop, backup, follow_symlinks=False)
        checked_file(backup, DROPIN_HASH)
        sync_parent(backup)
        try:
            progress("STOP_APPLICATION")
            systemctl("stop", APP)
            apps_quiesced(host, PROJECT)
            need(host._runtime("broker") == before["broker"], "broker_identity_changed")
            need(transaction_snapshot() == prepare_hash, "legacy_prepare_state_changed")
            progress("SWITCH_SUPERVISION")
            checked_file(drop, DROPIN_HASH).unlink()
            sync_parent(drop)
            systemctl("daemon-reload")
            supervision(False, "inactive")
            legacy_daemon("active", "enabled", legacy_pid)
            progress("START_STANDARD_APPLICATION")
            new_start_attempted = True
            systemctl("start", APP)
            progress("VERIFY_STANDARD_APPLICATION")
            report.update(wait_healthy(False, before, expected_mounts, prepare_hash))
            supervision(False, "active")
            legacy_daemon("active", "enabled", legacy_pid)
        except (Exception, KeyboardInterrupt) as error:
            report.update(error_code=error_code(error), **error_details(error))
            progress("ROLLBACK")
            try:
                signal.signal(signal.SIGINT, signal.SIG_IGN)
                signal.signal(signal.SIGTERM, signal.SIG_IGN)
                signal.signal(signal.SIGHUP, signal.SIG_IGN)
                restore(drop, backup, new_start_attempted, legacy_pid)
                report.update(wait_healthy(True, before, expected_mounts, prepare_hash))
                legacy_daemon("active", "enabled", legacy_pid)
                report.update(status="R7_LEGACY_CUTOVER_ROLLED_BACK", broker_unchanged=True,
                              application_data_mounts_preserved=True, transactions_unchanged=True)
                return 3, report
            except Exception as rollback_error:
                report.update(status="R7_LEGACY_CUTOVER_ROLLBACK_INCOMPLETE",
                              rollback_error=error_code(rollback_error))
                if details := error_details(rollback_error):
                    report["rollback_details"] = details
                return 4, report

        # After proving the standard stack, retire the old service. If a stop
        # result is ambiguous, keep the verified standard scope in service
        # instead of allowing systemd to restart the fault acceptance daemon.
        try:
            progress("RETIRE_LEGACY_DAEMON")
            systemctl("disable", LEGACY)
            legacy_daemon("active", "disabled", legacy_pid)
            need(not legacy_props()["RequiredBy"], "legacy_daemon_still_required")
            systemctl("stop", LEGACY)
            legacy_daemon("inactive", "disabled")
            supervision(False, "active")
            need(host._runtime("broker") == before["broker"], "broker_identity_changed")
            need(transaction_snapshot() == prepare_hash, "legacy_prepare_state_changed")
        except (Exception, KeyboardInterrupt) as error:
            report.update(status="R7_LEGACY_CUTOVER_FINALIZATION_PENDING",
                          error_code=error_code(error), standard_application_verified=True,
                          **error_details(error))
            return 5, report

        report.update(status="R7_LEGACY_CUTOVER_PASS", broker_unchanged=True,
                      application_data_mounts_preserved=True, transactions_unchanged=True)
        return 0, report


def main():
    def interrupted(_signum, _frame):
        raise KeyboardInterrupt

    for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(signum, interrupted)
    try:
        need(os.geteuid() == 0 and sys.platform == "linux"
             and platform.machine() in {"aarch64", "arm64"}
             and sys.version_info >= (3, 11), "unsupported_spare_environment")
        payload = base64.b64decode(PACKAGE_ON_SPARE, validate=True)
        need(digest(payload) == PACKAGE_HASH, "readonly_probe_package_hash_mismatch")
        fd = os.memfd_create("n3w-r7-probe")
        try:
            with os.fdopen(os.dup(fd), "wb") as stream:
                stream.write(payload)
            sys.path.insert(0, f"/proc/self/fd/{fd}")
            rc, report = run()
        finally:
            os.close(fd)
    except (Exception, KeyboardInterrupt) as error:
        rc, report = 2, {"status": "R7_LEGACY_CUTOVER_PRECHECK_STOP",
                         "error_code": error_code(error), **error_details(error)}
    print(json.dumps(report, sort_keys=True), flush=True)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
