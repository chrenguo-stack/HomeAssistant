# N3-W T1 F4 Stopped Runtime Acceptance Recovery — Live Read-Only Preexecution Runbook

Date: 2026-10-16

~~~text
TASK=N3W_T1_F4_STOPPED_RUNTIME_ACCEPTANCE_RECOVERY_LIVE_READONLY_PREEXECUTION_20261016_01
STATUS=PREPARED_NOT_EXECUTED

T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
ARTIFACT_TRANSFER=false
RECOVERY_AUTHORIZATION_GRANTED=false
RECOVERY_AUTHORIZATION_CLAIMED=false
RECOVERY_AUTHORIZATION_CONSUMED=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
REBOOT=false
~~~

## Purpose

Collect one fresh, read-only real-T1 snapshot before any exact recovery artifact is transferred or any recovery
authorization is granted.

This runbook does not start, stop, enable, disable, restart, reload, copy, extract, rename or delete anything on T1.

## Frozen authority

~~~text
FAILED_SOURCE_HEAD=ffcbb1a890e42ac776c6d90000bf3f25195da01d
FAILED_PACKAGE_MANIFEST_SHA256=4df1d95b0849aa4ca574f31f8fd55e57fe118fba1c5913d2d8b3f96e286ec669
FAILED_LAUNCHER_SHA256=f7f742505f439675fb19ecf8f98b8235703d6e2a1c5c9217ecfe01a025be3c8b
FAILED_LAUNCHER_SIZE_BYTES=157616
FAILED_ACCEPTANCE_AUTHORIZATION=N3W_T1_F4_RUNTIME_ACCEPTANCE_LIVE_20261015_01

SUCCESSOR_SOURCE_HEAD=f0bcc2ac50326b9a988405af8a2aad4c51694810
SUCCESSOR_PACKAGE_MANIFEST_SHA256=37c620daf57a3f49614a4c2824c55b7e20413ef63593cd1781e4f359fb4729b5
SUCCESSOR_LAUNCHER_SHA256=eaf28175909479007d6d1df7522811d032890dcaa2a2280228c93e6dce128bb3
SUCCESSOR_CONTROL_TAR_SHA256=9d1ba965ac72887dbac6cc48381d228843c6c489e92217ef65886d73cd0c309d
SUCCESSOR_ARTIFACT_ZIP_SHA256=7c633170dfcbe2f9587fd51eaa48455505069c21b2c76df48e9d9ef54249b225

PROSPECTIVE_RECOVERY_AUTHORIZATION=N3W_T1_F4_STOPPED_RUNTIME_ACCEPTANCE_RECOVERY_LIVE_20261016_01
PROSPECTIVE_SUCCESSOR_ACTIVATION_AUTHORIZATION=N3W_T1_F4_RUNTIME_ACTIVATION_SUCCESSOR_LIVE_20261016_01
PROSPECTIVE_SUCCESSOR_ACCEPTANCE_AUTHORIZATION=N3W_T1_F4_RUNTIME_ACCEPTANCE_SUCCESSOR_LIVE_20261016_01

RESERVED_STAGING_PATH=/var/tmp/n3w-t1-f4-recovery-f0bcc2ac50326b9a988405af8a2aad4c51694810
~~~

The three prospective authorization IDs are reserved only. They are not granted by this document or by running the
read-only collector.

## Mac Terminal collector

Set `T1` privately in the shell before running. Do not commit the private locator to GitHub.

~~~bash
set -euo pipefail
: "${T1:?Set T1 to the private SSH locator first}"
COLLECT="$(mktemp)"
trap 'rm -f "$COLLECT"' EXIT
cat > "$COLLECT" <<'PY'
import hashlib
import json
import os
import shutil
import stat
import subprocess
from pathlib import Path

TRANSACTION = Path("/var/lib/n3w-t1-provisioning/F4_ACTIVATION_TRANSACTION.json")
REPORT = Path("/var/lib/n3w-t1-provisioning/F4_RUNTIME_ACCEPTANCE.json")
LAUNCHER = Path("/usr/local/sbin/n3w-t1-f4-activation")
STAGING = Path("/var/tmp/n3w-t1-f4-recovery-f0bcc2ac50326b9a988405af8a2aad4c51694810")
TARGET_PORTS = {1883, 8883, 18883, 8123, 47110, 47111, 47112}
PROSPECTIVE = [
    "N3W_T1_F4_STOPPED_RUNTIME_ACCEPTANCE_RECOVERY_LIVE_20261016_01",
    "N3W_T1_F4_RUNTIME_ACTIVATION_SUCCESSOR_LIVE_20261016_01",
    "N3W_T1_F4_RUNTIME_ACCEPTANCE_SUCCESSOR_LIVE_20261016_01",
]

def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def run(argv):
    p = subprocess.run(
        argv,
        check=False,
        text=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    return p.returncode, p.stdout.strip(), p.stderr.strip()

def systemctl(mode, unit):
    rc, out, _ = run(["systemctl", mode, unit])
    return out or f"rc:{rc}"

def file_binding(path):
    if path.is_symlink() or not path.is_file():
        return None
    st = path.stat()
    return {
        "sha256": sha256(path),
        "size": st.st_size,
        "mode": stat.S_IMODE(st.st_mode),
        "uid": st.st_uid,
        "gid": st.st_gid,
    }

transaction = json.loads(TRANSACTION.read_text(encoding="utf-8"))
installed = transaction.get("installed_files")
installed_mismatches = []
if isinstance(installed, dict):
    for raw_path, expected in sorted(installed.items()):
        path = Path(raw_path)
        actual = file_binding(path)
        if not isinstance(expected, dict) or actual is None:
            installed_mismatches.append(raw_path)
            continue
        keys = ("sha256", "size", "mode", "uid", "gid")
        if any(actual.get(k) != expected.get(k) for k in keys):
            installed_mismatches.append(raw_path)
else:
    installed_mismatches.append("<installed_files_invalid>")

docker_rc, docker_out, docker_err = run([
    "docker",
    "ps",
    "--filter",
    "label=com.docker.compose.project=n3wfc4",
    "--format",
    '{{.Label "com.docker.compose.service"}}',
])
running_services = None
if docker_rc == 0:
    running_services = sorted(
        line.strip() for line in docker_out.splitlines() if line.strip()
    )

ss_rc, ss_out, ss_err = run(["ss", "-lntH"])
listener_ports = None
if ss_rc == 0:
    listener_ports = []
    for row in ss_out.splitlines():
        fields = row.split()
        if len(fields) < 4:
            continue
        local = fields[3]
        try:
            port = int(local.rsplit(":", 1)[1])
        except (ValueError, IndexError):
            continue
        if port in TARGET_PORTS:
            listener_ports.append(port)
    listener_ports = sorted(set(listener_ports))

prior = set()
for key in (
    "authorization_id",
    "control_repair_authorization_id",
    "activation_authority_repair_authorization_id",
    "runtime_start_repair_authorization_id",
    "runtime_continuation_authority_repair_authorization_id",
    "runtime_acceptance_recovery_authorization_id",
    "activation_authorization_id",
    "runtime_acceptance_authorization_id",
    "persistence_authorization_id",
    "certificate_audit_authorization_id",
    "certificate_timer_authorization_id",
):
    value = transaction.get(key)
    if isinstance(value, str):
        prior.add(value)

history_valid = True
for key in (
    "activation_authorization_history",
    "runtime_acceptance_authorization_history",
):
    value = transaction.get(key, [])
    if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
        history_valid = False
    else:
        prior.update(value)

launcher = file_binding(LAUNCHER)
transaction_sha256 = sha256(TRANSACTION)
free_bytes = shutil.disk_usage("/var/tmp").free

document = {
    "stage": transaction.get("stage"),
    "error_code": transaction.get("error_code"),
    "rollback_proven": transaction.get("rollback_proven"),
    "rollback_error_count": transaction.get("rollback_error_count"),
    "production_service_start": transaction.get("production_service_start"),
    "persistence_enabled": transaction.get("persistence_enabled"),
    "certificate_timer_enabled": transaction.get("certificate_timer_enabled"),
    "product_listener_ports_recorded": transaction.get("product_listener_ports"),
    "package_source_head": transaction.get("package_source_head"),
    "package_manifest_sha256": transaction.get("package_manifest_sha256"),
    "runtime_acceptance_authorization_id": transaction.get(
        "runtime_acceptance_authorization_id"
    ),
    "runtime_acceptance_authorization_claimed": transaction.get(
        "runtime_acceptance_authorization_claimed"
    ),
    "runtime_acceptance_authorization_consumed": transaction.get(
        "runtime_acceptance_authorization_consumed"
    ),
    "runtime_acceptance_authorization_replay_allowed": transaction.get(
        "runtime_acceptance_authorization_replay_allowed"
    ),
    "runtime_acceptance_passed": transaction.get("runtime_acceptance_passed"),
    "runtime_acceptance_recovery_authorization_claimed": transaction.get(
        "runtime_acceptance_recovery_authorization_claimed"
    ),
    "runtime_acceptance_report_present": REPORT.exists() or REPORT.is_symlink(),
    "transaction_sha256": transaction_sha256,
    "installed_launcher": launcher,
    "installed_material_binding_pass": installed_mismatches == [],
    "installed_material_mismatches": installed_mismatches,
    "docker_runtime_probe": "PASS" if docker_rc == 0 else "FAIL",
    "docker_runtime_probe_error": docker_err[:300] if docker_rc != 0 else "",
    "running_services": running_services,
    "listener_probe": "PASS" if ss_rc == 0 else "FAIL",
    "listener_probe_error": ss_err[:300] if ss_rc != 0 else "",
    "product_listener_ports": listener_ports,
    "broker_active": systemctl("is-active", "n3wfc4-broker-activation.service"),
    "broker_enabled": systemctl("is-enabled", "n3wfc4-broker-activation.service"),
    "services_active": systemctl("is-active", "n3wfc4-services-activation.service"),
    "services_enabled": systemctl("is-enabled", "n3wfc4-services-activation.service"),
    "guard_active": systemctl("is-active", "n3wfc4-broker-ingress-guard.service"),
    "certificate_service_active": systemctl(
        "is-active",
        "n3wfc4-broker-certificate-lifecycle.service",
    ),
    "certificate_timer_active": systemctl(
        "is-active",
        "n3wfc4-broker-certificate-lifecycle.timer",
    ),
    "certificate_timer_enabled": systemctl(
        "is-enabled",
        "n3wfc4-broker-certificate-lifecycle.timer",
    ),
    "authorization_history_valid": history_valid,
    "prospective_authorization_collisions": {
        value: value in prior for value in PROSPECTIVE
    },
    "staging_path_exists": STAGING.exists() or STAGING.is_symlink(),
    "var_tmp_free_bytes": free_bytes,
}
print("READONLY_PREEXECUTION=" + json.dumps(document, sort_keys=True))
PY
ssh -T   -o StrictHostKeyChecking=yes   -o ConnectTimeout=10   -o ConnectionAttempts=1   -o ControlMaster=no   -o ControlPath=none   -o ControlPersist=no   -o ClearAllForwardings=yes   -o RequestTTY=no   "$T1"   python3 - < "$COLLECT"
~~~

The SSH process owns stdin in this command, so `ssh -n` must not be added.

## Expected PASS contract

A PASS candidate must show:

~~~text
stage=STOPPED_RUNTIME_ACCEPTANCE
error_code=manager_mqtt_socket_count_invalid
rollback_proven=true
rollback_error_count=0

package_source_head=ffcbb1a890e42ac776c6d90000bf3f25195da01d
package_manifest_sha256=4df1d95b0849aa4ca574f31f8fd55e57fe118fba1c5913d2d8b3f96e286ec669

runtime_acceptance_authorization_id=N3W_T1_F4_RUNTIME_ACCEPTANCE_LIVE_20261015_01
runtime_acceptance_authorization_claimed=true
runtime_acceptance_authorization_consumed=true
runtime_acceptance_authorization_replay_allowed=false
runtime_acceptance_passed!=true
runtime_acceptance_recovery_authorization_claimed!=true

installed_launcher.sha256=f7f742505f439675fb19ecf8f98b8235703d6e2a1c5c9217ecfe01a025be3c8b
installed_launcher.size=157616
installed_material_binding_pass=true

production_service_start=false
persistence_enabled=false
certificate_timer_enabled=false

docker_runtime_probe=PASS
running_services=[]
listener_probe=PASS
product_listener_ports=[]

broker_enabled=disabled
services_enabled=disabled
broker_active in [inactive,failed]
services_active in [inactive,failed]

guard_active=active
certificate_service_active=inactive
certificate_timer_active=inactive
certificate_timer_enabled=disabled

runtime_acceptance_report_present=false
authorization_history_valid=true
all prospective_authorization_collisions=false
staging_path_exists=false
~~~

The recorded transaction listener set must also be `[]`.

Free-space evidence is recorded but the transfer-size threshold is evaluated only before the later staging gate.
The exact tar is only 235520 bytes, but the staging gate must still preserve a conservative reserve and avoid assuming
capacity from size alone.

## Hard STOP conditions

Any of the following stops the route before transfer:

- transaction stage or failure code differs;
- rollback is not proven;
- source/manifest/launcher binding differs;
- installed-material binding is not exact;
- Docker or listener probe is unproven;
- any product service is running;
- any product listener is present;
- Broker/Services are enabled;
- certificate timer/service state is not safely stopped;
- runtime-acceptance report exists;
- ingress guard is not active;
- a prospective authorization collides with any prior/history ID;
- reserved staging path already exists;
- the failed acceptance authorization is not the consumed/no-replay R1 authorization.

Do not repair or normalize any mismatch inside this read-only gate.

## After PASS

~~~text
AFTER_PASS_STOP=true
RECOVERY_AUTHORIZATION_GRANTED=false
ARTIFACT_TRANSFER=false
LIVE_RUNTIME_MUTATION=false

NEXT_ONE_GATE=N3W_T1_F4_STOPPED_RUNTIME_ACCEPTANCE_RECOVERY_EXACT_ARTIFACT_STAGING_PREEXECUTION_20261016_01
AUTO_EXECUTE_NEXT_GATE=false
~~~

The next gate may prepare/perform exact tar transfer and extraction while keeping the runtime stopped. The actual
`repair-stopped-runtime-acceptance` command still requires a separately granted recovery authorization and remains
outside this read-only preexecution.
