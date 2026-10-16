## 2026-10-16 Stage A execution closure

~~~text
STAGE_A_RESULT=PASS
LOCAL_EXACT_PACKAGE=PASS

REMOTE_TRANSACTION_SHA256=805fb27f44d36d7e512260373be7dbb8058164d3ea4ce4c1d13659169062dbcf
REMOTE_TRANSACTION_SHA256_MATCH=true

REMOTE_STAGE=STOPPED_RUNTIME_ACCEPTANCE
REMOTE_ERROR_CODE=manager_mqtt_socket_count_invalid
REMOTE_ROLLBACK_PROVEN=true
REMOTE_ROLLBACK_ERROR_COUNT=0

REMOTE_PACKAGE_SOURCE_HEAD=ffcbb1a890e42ac776c6d90000bf3f25195da01d
REMOTE_PACKAGE_MANIFEST_SHA256=4df1d95b0849aa4ca574f31f8fd55e57fe118fba1c5913d2d8b3f96e286ec669

REMOTE_DOCKER_PROBE=PASS
REMOTE_RUNNING_SERVICES=[]
REMOTE_LISTENER_PROBE=PASS
REMOTE_PRODUCT_LISTENER_PORTS=[]

REMOTE_STAGING_ROOT_EXISTS=false
REMOTE_STAGING_TAR_EXISTS=false
REMOTE_STAGING_TAR_PART_EXISTS=false
REMOTE_STAGING_EXTRACT_PART_EXISTS=false

REMOTE_VAR_TMP_FREE_BYTES=6246510592
REMOTE_CAPACITY_PASS=true

ARTIFACT_TRANSFER_TO_T1=false
LIVE_RUNTIME_MUTATION=false
STOP=true
~~~

Stage A satisfies every frozen precondition. No T1 file was written and the transaction hash is unchanged from the
preceding live read-only preexecution.

Stage B is now eligible inside the same already-authorized gate. Stage B remains bounded to the dedicated recovery
staging paths and must stop before the recovery command.

# N3-W T1 F4 Stopped Runtime Acceptance Recovery — Exact Artifact Staging Preexecution

Date: 2026-10-16

~~~text
TASK=N3W_T1_F4_STOPPED_RUNTIME_ACCEPTANCE_RECOVERY_EXACT_ARTIFACT_STAGING_PREEXECUTION_20261016_01
STATUS=PREPARED_AWAITING_STAGE_A

PREDECESSOR_GATE=N3W_T1_F4_STOPPED_RUNTIME_ACCEPTANCE_RECOVERY_LIVE_READONLY_PREEXECUTION_20261016_01
PREDECESSOR_RESULT=CLOSED_PASS

SOURCE_HEAD=f0bcc2ac50326b9a988405af8a2aad4c51694810
ARTIFACT_RUN_ID=38767114055
ARTIFACT_ID=11990381805
ARTIFACT_NAME=n3w-t1-f4-control-package-f0bcc2ac50326b9a988405af8a2aad4c51694810

CONTROL_TAR_SHA256=9d1ba965ac72887dbac6cc48381d228843c6c489e92217ef65886d73cd0c309d
CONTROL_TAR_SIZE=235520
MANIFEST_SHA256=37c620daf57a3f49614a4c2824c55b7e20413ef63593cd1781e4f359fb4729b5
LAUNCHER_SHA256=eaf28175909479007d6d1df7522811d032890dcaa2a2280228c93e6dce128bb3
LAUNCHER_SIZE=177919

PRE_STAGE_TRANSACTION_SHA256=805fb27f44d36d7e512260373be7dbb8058164d3ea4ce4c1d13659169062dbcf

STAGING_ROOT=/var/tmp/n3w-t1-f4-recovery-f0bcc2ac50326b9a988405af8a2aad4c51694810
STAGING_TAR=/var/tmp/n3w-t1-f4-recovery-f0bcc2ac50326b9a988405af8a2aad4c51694810.tar
STAGING_TAR_PART=/var/tmp/n3w-t1-f4-recovery-f0bcc2ac50326b9a988405af8a2aad4c51694810.tar.part
STAGING_EXTRACT_PART=/var/tmp/n3w-t1-f4-recovery-f0bcc2ac50326b9a988405af8a2aad4c51694810.extract.part

RECOVERY_AUTHORIZATION_GRANTED=false
RECOVERY_COMMAND_EXECUTION=false
PRODUCTION_SERVICE_START=false
PERSISTENCE_ENABLE=false
CERTIFICATE_TIMER_ENABLE=false
BOARD_ACCESS=false
REBOOT=false
MERGE=false
~~~

## 1. Gate structure

This gate is split into two bounded stages.

### Stage A — local exact-artifact materialization + fresh remote staging preflight

Stage A is read-only on T1.

It proves:

- GitHub artifact can be freshly materialized on the Mac;
- local tar, manifest and launcher reproduce the frozen hashes;
- the real T1 transaction has not drifted since the previous read-only gate;
- all four reserved staging paths are absent;
- the product runtime/listener state remains stopped;
- enough `/var/tmp` free space exists for a bounded staging operation.

STOP after Stage A output.

### Stage B — exact tar transfer, atomic publication, extraction and remote rebinding

Stage B is the only T1 filesystem mutation in this gate.

It may:

- write the exact tar to the dedicated `.tar.part` path;
- verify its exact SHA-256;
- atomically rename it to the dedicated final `.tar` path;
- create the dedicated `.extract.part` directory;
- extract only the exact validated package there;
- validate manifest, all package file hashes/sizes and launcher binding;
- atomically publish the extracted directory to the reserved staging root.

It may not:

- replace `/usr/local/sbin/n3w-t1-f4-activation`;
- execute `repair-stopped-runtime-acceptance`;
- claim/consume the recovery authorization;
- start/stop/enable/disable/restart/reload product services;
- enable persistence or certificate lifecycle;
- access any board.

STOP immediately after the remote staging binding report.

## 2. Stage A Mac Terminal command

~~~bash
set -euo pipefail
REPO='chrenguo-stack/HomeAssistant'
RUN_ID='38767114055'
ARTIFACT='n3w-t1-f4-control-package-f0bcc2ac50326b9a988405af8a2aad4c51694810'
EXPECTED_TAR='9d1ba965ac72887dbac6cc48381d228843c6c489e92217ef65886d73cd0c309d'
EXPECTED_MANIFEST='37c620daf57a3f49614a4c2824c55b7e20413ef63593cd1781e4f359fb4729b5'
EXPECTED_LAUNCHER='eaf28175909479007d6d1df7522811d032890dcaa2a2280228c93e6dce128bb3'
EXPECTED_TX='805fb27f44d36d7e512260373be7dbb8058164d3ea4ce4c1d13659169062dbcf'
EXPECTED_SOURCE='f0bcc2ac50326b9a988405af8a2aad4c51694810'
T1='root@192.168.68.195'
WORK="$(mktemp -d "${TMPDIR:-/tmp}/n3w-f4-stage-a.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT
command -v gh >/dev/null
gh auth status -h github.com >/dev/null
gh run download "$RUN_ID" -R "$REPO" -n "$ARTIFACT" -D "$WORK"
test "$(shasum -a 256 "$WORK/n3w-t1-f4-control-package.tar" | awk '{print $1}')" = "$EXPECTED_TAR"
mkdir "$WORK/extract"
tar -C "$WORK/extract" -xf "$WORK/n3w-t1-f4-control-package.tar"
test "$(shasum -a 256 "$WORK/extract/f4-package/f4-package-manifest.json" | awk '{print $1}')" = "$EXPECTED_MANIFEST"
test "$(shasum -a 256 "$WORK/extract/f4-package/tools/n3w_t1_f4_activation_host.py" | awk '{print $1}')" = "$EXPECTED_LAUNCHER"
python3 - "$WORK/extract/f4-package" "$EXPECTED_SOURCE" "$EXPECTED_MANIFEST" "$EXPECTED_LAUNCHER" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
expected_source = sys.argv[2]
expected_manifest = sys.argv[3]
expected_launcher = sys.argv[4]

def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

manifest_path = root / "f4-package-manifest.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
assert sha256(manifest_path) == expected_manifest
assert manifest["schema"] == "gh.n3w-t1-f4-activation-package/1"
assert manifest["source_head"] == expected_source
assert manifest["production_service_start"] is False
assert manifest["secret_values_included"] is False
assert manifest["board_access"] is False
records = manifest["files"]
assert len(records) == 8
expected = {"f4-package-manifest.json"}
for record in records:
    rel = record["path"]
    expected.add(rel)
    path = root / rel
    assert path.is_file() and not path.is_symlink()
    assert path.stat().st_size == record["size"]
    assert sha256(path) == record["sha256"]
actual = {
    str(path.relative_to(root))
    for path in root.rglob("*")
    if path.is_file()
}
assert actual == expected
launcher = root / "tools/n3w_t1_f4_activation_host.py"
assert sha256(launcher) == expected_launcher
assert launcher.stat().st_size == 177919
assert launcher.read_bytes().startswith(b"#!/usr/bin/python3\n")
print("LOCAL_EXACT_PACKAGE=PASS")
PY
COLLECT="$(mktemp)"
trap 'rm -rf "$WORK"; rm -f "$COLLECT"' EXIT
cat > "$COLLECT" <<'PY'
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

TX = Path("/var/lib/n3w-t1-provisioning/F4_ACTIVATION_TRANSACTION.json")
BASE = Path("/var/tmp/n3w-t1-f4-recovery-f0bcc2ac50326b9a988405af8a2aad4c51694810")
PATHS = [
    BASE,
    Path(str(BASE) + ".tar"),
    Path(str(BASE) + ".tar.part"),
    Path(str(BASE) + ".extract.part"),
]
EXPECTED_TX = "805fb27f44d36d7e512260373be7dbb8058164d3ea4ce4c1d13659169062dbcf"
TARGET_PORTS = {1883, 8883, 18883, 8123, 47110, 47111, 47112}

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

transaction = json.loads(TX.read_text(encoding="utf-8"))
tx_sha = sha256(TX)
docker_rc, docker_out, docker_err = run([
    "docker",
    "ps",
    "--filter",
    "label=com.docker.compose.project=n3wfc4",
    "--format",
    '{{.Label "com.docker.compose.service"}}',
])
ss_rc, ss_out, ss_err = run(["ss", "-lntH"])
services = None
if docker_rc == 0:
    services = sorted(x for x in docker_out.splitlines() if x)
ports = None
if ss_rc == 0:
    ports = []
    for row in ss_out.splitlines():
        fields = row.split()
        if len(fields) < 4:
            continue
        try:
            port = int(fields[3].rsplit(":", 1)[1])
        except (ValueError, IndexError):
            continue
        if port in TARGET_PORTS:
            ports.append(port)
    ports = sorted(set(ports))
free_bytes = shutil.disk_usage("/var/tmp").free
result = {
    "transaction_sha256": tx_sha,
    "transaction_sha256_match": tx_sha == EXPECTED_TX,
    "stage": transaction.get("stage"),
    "error_code": transaction.get("error_code"),
    "rollback_proven": transaction.get("rollback_proven"),
    "rollback_error_count": transaction.get("rollback_error_count"),
    "package_source_head": transaction.get("package_source_head"),
    "package_manifest_sha256": transaction.get("package_manifest_sha256"),
    "production_service_start": transaction.get("production_service_start"),
    "persistence_enabled": transaction.get("persistence_enabled"),
    "docker_probe": "PASS" if docker_rc == 0 else "FAIL",
    "docker_error": docker_err[:300] if docker_rc else "",
    "running_services": services,
    "listener_probe": "PASS" if ss_rc == 0 else "FAIL",
    "listener_error": ss_err[:300] if ss_rc else "",
    "product_listener_ports": ports,
    "staging_paths_exist": {str(path): path.exists() or path.is_symlink() for path in PATHS},
    "var_tmp_free_bytes": free_bytes,
    "capacity_pass": free_bytes >= 67344384,
}
assert result["transaction_sha256_match"] is True
assert result["stage"] == "STOPPED_RUNTIME_ACCEPTANCE"
assert result["error_code"] == "manager_mqtt_socket_count_invalid"
assert result["rollback_proven"] is True
assert result["rollback_error_count"] == 0
assert result["package_source_head"] == "ffcbb1a890e42ac776c6d90000bf3f25195da01d"
assert result["package_manifest_sha256"] == "4df1d95b0849aa4ca574f31f8fd55e57fe118fba1c5913d2d8b3f96e286ec669"
assert result["production_service_start"] is False
assert result["persistence_enabled"] is False
assert result["docker_probe"] == "PASS"
assert result["running_services"] == []
assert result["listener_probe"] == "PASS"
assert result["product_listener_ports"] == []
assert not any(result["staging_paths_exist"].values())
assert result["capacity_pass"] is True
print("REMOTE_STAGING_PREFLIGHT=" + json.dumps(result, sort_keys=True))
print("STAGE_A_RESULT=PASS")
print("ARTIFACT_TRANSFER_TO_T1=false")
print("STOP=true")
PY
ssh -T   -o StrictHostKeyChecking=yes   -o ConnectTimeout=10   -o ConnectionAttempts=1   -o ControlMaster=no   -o ControlPath=none   -o ControlPersist=no   -o ClearAllForwardings=yes   -o RequestTTY=no   "$T1"   python3 - < "$COLLECT"
~~~

## 3. Stage A PASS condition

Required output:

~~~text
LOCAL_EXACT_PACKAGE=PASS
REMOTE_STAGING_PREFLIGHT=<all assertions passed>
STAGE_A_RESULT=PASS
ARTIFACT_TRANSFER_TO_T1=false
STOP=true
~~~

Do not run Stage B if Stage A fails or if any staging path already exists.

## 4. Stage B prepared contract

Stage B is prepared but must not be run until Stage A output is reviewed.

It will freshly re-download and re-hash the same exact artifact, transfer only
`n3w-t1-f4-control-package.tar` to the dedicated `.tar.part` path, verify remote SHA-256, atomically publish the
tar, extract into the dedicated `.extract.part` directory, validate the package, atomically publish the extracted
staging directory, and then prove the transaction/runtime remained unchanged.

A Stage B PASS will stop with:

~~~text
REMOTE_STAGING_RESULT=PASS
REMOTE_TAR_SHA256=9d1ba965ac72887dbac6cc48381d228843c6c489e92217ef65886d73cd0c309d
REMOTE_MANIFEST_SHA256=37c620daf57a3f49614a4c2824c55b7e20413ef63593cd1781e4f359fb4729b5
REMOTE_LAUNCHER_SHA256=eaf28175909479007d6d1df7522811d032890dcaa2a2280228c93e6dce128bb3
TRANSACTION_SHA256=805fb27f44d36d7e512260373be7dbb8058164d3ea4ce4c1d13659169062dbcf
STAGE=STOPPED_RUNTIME_ACCEPTANCE
RECOVERY_AUTHORIZATION_CLAIMED=false
STOP_BEFORE_RECOVERY_COMMAND=true
~~~

## 5. Gate boundary

~~~text
CURRENT_SUBSTAGE=AWAITING_STAGE_A
STAGE_B_EXECUTED=false
RECOVERY_COMMAND_EXECUTED=false
RECOVERY_AUTHORIZATION_GRANTED=false
RECOVERY_AUTHORIZATION_CLAIMED=false
RECOVERY_AUTHORIZATION_CONSUMED=false
PRODUCTION_SERVICE_START=false

AUTO_ADVANCE_WITHIN_GATE_AFTER_STAGE_A_PASS=true
CROSS_GATE_AUTO_EXECUTE=false
~~~
