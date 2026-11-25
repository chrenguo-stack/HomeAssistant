#!/bin/bash
set -euo pipefail

test "${N3W_T1_R8V13_07_RECOVERY_PYZ_REPLACEMENT_APPROVED:-}" = "YES"

HOST="${N3W_T1_SSH_TARGET:?N3W_T1_SSH_TARGET required}"
REPO="chrenguo-stack/HomeAssistant"

OLD_ARTIFACT_ID="14939405227"
OLD_ARTIFACT_SHA256="9843b55453ba0025cbedae228c20e10da6b45b8284e559d2c8035876d98d42e5"
OLD_MANIFEST_SHA256="489aa375fda2b0fba76ee4e9bd30ab168ce9ee00feff05ee074af5b656d1eca8"
OLD_SOURCE_HEAD="a9b76d77c2a930a21089af7fe0cc814f4db60a9a"
OLD_PYZ_SHA256="d7915bc3e42531a829ab22ecb74a7148878c3a2310313e4f1ac07acc8785185e"

NEW_ARTIFACT_ID="14980338287"
NEW_ARTIFACT_SHA256="d47d3fc4183805e63431c105682fbd93ed1cdc56b5fdc8681f41277afcd14ed1"
NEW_MANIFEST_SHA256="c3071a9dcc2a5e54ca6017cfb58d1afad8d715cc47ca0640ae22493472430838"
NEW_SOURCE_HEAD="07eefc1e6d87eff464133771191d155fa9ee9d3d"
NEW_PYZ_SHA256="9d69992a72c3b8dd60f33ebcf00ac7c8fcf88e255c7fadb8878d15aa86f10ffa"

TX_ID="d86669e6d16bb9420191920bc2b02583e7f7207eff0b51ed3f9e6321f99389d4"
TX_SHA256="795c89ce2a7b10246da381ed205e7bf3f77c2561197d1d6a6e4ac2fb9e332eed"
ENV_SHA256="d139286ebd1379af96851321755a78c8cee795edb64f93ec7b74f2bb1e152d4b"
RECOVERED_LAUNCH_SHA256="67877cffd28b1c94de17f6b8eecabd1b579649f7e282fdfc65e4bcfcfd5fdc26"
USB_UUID="b72ac2fc-79a0-4fb8-888e-f35b0114f959"
HA_REF="local/n3w-homeassistant:2026.10.4-5881590f"
HA_ID="sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365"
TARGET_REF="local/n3w-homeassistant:2026.10.0-0c73235a"
TARGET_ID="sha256:c261fa53f30508951833492ba2a19af6cfbb6aa8f2806b531d8f5c6599265306"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
OLD_ZIP="$TMP/old-recovery.zip"
NEW_ZIP="$TMP/new-recovery.zip"
NEW_PYZ="$TMP/new-ha-recovery.pyz"
REMOTE_STAGE="/tmp/n3w-r8v13-07-recovery-pyz-replacement-20261125-01"

echo PHASE=LOCAL_ARTIFACT_DELTA_BINDING
gh api "repos/$REPO/actions/artifacts/$OLD_ARTIFACT_ID/zip" > "$OLD_ZIP"
gh api "repos/$REPO/actions/artifacts/$NEW_ARTIFACT_ID/zip" > "$NEW_ZIP"
test "$(shasum -a 256 "$OLD_ZIP" | awk '{print $1}')" = "$OLD_ARTIFACT_SHA256"
test "$(shasum -a 256 "$NEW_ZIP" | awk '{print $1}')" = "$NEW_ARTIFACT_SHA256"

python3 -   "$OLD_ZIP" "$OLD_MANIFEST_SHA256" "$OLD_SOURCE_HEAD" "$OLD_PYZ_SHA256"   "$NEW_ZIP" "$NEW_MANIFEST_SHA256" "$NEW_SOURCE_HEAD" "$NEW_PYZ_SHA256" "$NEW_PYZ" <<'PY'
import hashlib
import json
import stat
import sys
import zipfile
from pathlib import Path, PurePosixPath

(
    old_zip, old_manifest_sha, old_source, old_pyz_sha,
    new_zip, new_manifest_sha, new_source, new_pyz_sha, new_pyz_path,
) = sys.argv[1:10]

def load(path, expected_manifest_sha, expected_source, expected_pyz):
    with zipfile.ZipFile(path) as zf:
        infos = zf.infolist()
        names = [info.filename for info in infos]
        if len(names) != len(set(names)):
            raise SystemExit("ARTIFACT_DUPLICATE_MEMBER")
        for info in infos:
            member = PurePosixPath(info.filename)
            if member.is_absolute() or ".." in member.parts or info.is_dir():
                raise SystemExit(f"ARTIFACT_MEMBER_INVALID:{info.filename}")
            mode = (info.external_attr >> 16) & 0xFFFF
            if mode and not stat.S_ISREG(mode):
                raise SystemExit(f"ARTIFACT_MEMBER_NOT_REGULAR:{info.filename}")
        raw = zf.read("manifest.json")
        if hashlib.sha256(raw).hexdigest() != expected_manifest_sha:
            raise SystemExit("MANIFEST_SHA_DRIFT")
        manifest = json.loads(raw)
        if manifest.get("schema") != "gh.n3w-t1-ha-recovery-install/1":
            raise SystemExit("MANIFEST_SCHEMA_DRIFT")
        if manifest.get("source_head") != expected_source:
            raise SystemExit("MANIFEST_SOURCE_DRIFT")
        files = manifest.get("files")
        if not isinstance(files, dict) or set(names) != set(files) | {"manifest.json"}:
            raise SystemExit("ARTIFACT_FILE_SET_DRIFT")
        for name, expected in files.items():
            if hashlib.sha256(zf.read(name)).hexdigest() != expected:
                raise SystemExit(f"ARTIFACT_FILE_DIGEST_DRIFT:{name}")
        if files.get("ha-recovery.pyz") != expected_pyz:
            raise SystemExit("MANIFEST_PYZ_DRIFT")
        return files, zf.read("ha-recovery.pyz")

old_files, _ = load(old_zip, old_manifest_sha, old_source, old_pyz_sha)
new_files, new_pyz = load(new_zip, new_manifest_sha, new_source, new_pyz_sha)
if set(old_files) != set(new_files):
    raise SystemExit("ARTIFACT_PAYLOAD_SET_DRIFT")
changed = sorted(name for name in old_files if old_files[name] != new_files[name])
if changed != ["ha-recovery.pyz"]:
    raise SystemExit("NON_PYZ_PAYLOAD_DRIFT:" + ",".join(changed))
Path(new_pyz_path).write_bytes(new_pyz)
if hashlib.sha256(new_pyz).hexdigest() != new_pyz_sha:
    raise SystemExit("EXTRACTED_PYZ_DRIFT")
print("ARTIFACT_DELTA_BINDING=PASS")
print("CHANGED_PAYLOADS=ha-recovery.pyz")
print("NON_PYZ_PAYLOAD_DRIFT=false")
PY

echo PHASE=REMOTE_STAGE_CANDIDATE
ssh "$HOST" "set -euo pipefail; rm -rf '$REMOTE_STAGE'; install -d -m 700 '$REMOTE_STAGE'"
scp -q "$NEW_PYZ" "$HOST:$REMOTE_STAGE/new-ha-recovery.pyz"

ssh "$HOST" 'bash -s' --   "$TX_ID" "$TX_SHA256" "$ENV_SHA256" "$OLD_PYZ_SHA256" "$NEW_PYZ_SHA256"   "$RECOVERED_LAUNCH_SHA256" "$USB_UUID" "$HA_REF" "$HA_ID" "$TARGET_REF" "$TARGET_ID"   "$REMOTE_STAGE" <<'REMOTE_EOF'
set -euo pipefail
EXPECTED_TX_ID="$1"
EXPECTED_TX_SHA256="$2"
EXPECTED_ENV_SHA256="$3"
EXPECTED_OLD_PYZ_SHA256="$4"
EXPECTED_NEW_PYZ_SHA256="$5"
EXPECTED_RECOVERED_LAUNCH_SHA256="$6"
EXPECTED_USB_UUID="$7"
EXPECTED_HA_REF="$8"
EXPECTED_HA_ID="$9"
EXPECTED_TARGET_REF="${10}"
EXPECTED_TARGET_ID="${11}"
STAGE="${12}"

LIVE=/opt/n3w-t1-core-updater/ha-recovery.pyz
TX_FILE=/var/lib/n3w-t1-core-updater/homeassistant-usb-upgrade.json
ENV=/etc/n3wfc4/docker-compose.env
NEW="$STAGE/new-ha-recovery.pyz"
OLD="$STAGE/old-ha-recovery.pyz"

PATCH_PUBLISHED=false
CONTROL_QUIESCED=false
COMPLETED=false
PRE_RETRY_TIMER_STATE=unknown
PRE_IPC_SOCKET_STATE=unknown
PRE_IPC_SERVICE_STATE=unknown

atomic_publish() {
  src="$1"
  dst="$2"
  python3 - "$src" "$dst" <<'PY'
import os
import sys
import tempfile

src, dst = sys.argv[1:3]
directory = os.path.dirname(dst)
fd, temporary = tempfile.mkstemp(prefix=".ha-recovery.pyz.r8v13-07.", dir=directory)
try:
    with os.fdopen(fd, "wb") as output, open(src, "rb") as source:
        os.fchmod(output.fileno(), 0o644)
        while True:
            block = source.read(1024 * 1024)
            if not block:
                break
            output.write(block)
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, dst)
    descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
finally:
    try:
        os.unlink(temporary)
    except FileNotFoundError:
        pass
PY
}

restore_control_plane() {
  case "$PRE_IPC_SOCKET_STATE" in
    active|activating) systemctl start n3w-t1-ha-ota-ipc.socket ;;
  esac
  case "$PRE_IPC_SERVICE_STATE" in
    active|activating) systemctl start n3w-t1-ha-ota-ipc.service ;;
  esac
  case "$PRE_RETRY_TIMER_STATE" in
    active|activating) systemctl start n3w-t1-ha-recovery-retry.timer ;;
  esac
  CONTROL_QUIESCED=false
}

rollback_on_error() {
  rc=$?
  set +e
  if [ "$COMPLETED" != true ]; then
    if [ "$PATCH_PUBLISHED" = true ] && [ -f "$OLD" ]; then
      systemctl stop n3w-t1-ha-recovery-retry.timer
      systemctl stop n3w-t1-ha-recovery-retry.service
      systemctl stop n3w-t1-ha-ota-ipc.socket
      systemctl stop n3w-t1-ha-ota-ipc.service
      CONTROL_QUIESCED=true
      atomic_publish "$OLD" "$LIVE"
      if [ "$(sha256sum "$LIVE" | awk '{print $1}')" = "$EXPECTED_OLD_PYZ_SHA256" ]; then
        echo PYZ_ROLLBACK=PASS
      else
        echo PYZ_ROLLBACK=FAIL
      fi
    fi
    if [ "$CONTROL_QUIESCED" = true ]; then
      restore_control_plane || true
    fi
  fi
  echo RESULT=R8V13_07_RECOVERY_ARTIFACT_CONTROLLED_PYZ_REPLACEMENT_STOP
  exit "$rc"
}
trap rollback_on_error EXIT

echo PHASE=PREMUTATION_EXACT_RECHECK
test -f "$LIVE"
test -f "$TX_FILE"
test -f "$ENV"
test -f "$NEW"
test "$(sha256sum "$LIVE" | awk '{print $1}')" = "$EXPECTED_OLD_PYZ_SHA256"
test "$(sha256sum "$TX_FILE" | awk '{print $1}')" = "$EXPECTED_TX_SHA256"
test "$(sha256sum "$ENV" | awk '{print $1}')" = "$EXPECTED_ENV_SHA256"
test "$(sha256sum "$NEW" | awk '{print $1}')" = "$EXPECTED_NEW_PYZ_SHA256"

python3 - "$TX_FILE" "$EXPECTED_TX_ID" <<'PY'
import json
import sys

document = json.load(open(sys.argv[1], encoding="utf-8"))
expected = {
    "transaction_id_sha256": sys.argv[2],
    "status": "ROLLED_BACK",
    "phase": "U13B_ROLLED_BACK",
    "failure_code": None,
    "recovery_required": False,
    "authorization_claimed": True,
    "authorization_consumed": True,
    "authorization_id_sha256": "6976d68fd1b6828b630fd05751c2855afd84efc65639753f1a318189fff62f50",
}
for key, value in expected.items():
    if document.get(key) != value:
        raise SystemExit(f"TERMINAL_TX_DRIFT:{key}:{document.get(key)!r}")
print("TERMINAL_TRANSACTION=PASS")
PY

test "$(docker image inspect "$EXPECTED_HA_REF" --format '{{.Id}}')" = "$EXPECTED_HA_ID"
if docker image inspect "$EXPECTED_TARGET_REF" >/dev/null 2>&1; then
  echo TARGET_IMAGE_UNEXPECTEDLY_PRESENT=true
  exit 31
fi
if docker image inspect "$EXPECTED_TARGET_ID" >/dev/null 2>&1; then
  echo TARGET_IMAGE_ID_UNEXPECTEDLY_PRESENT=true
  exit 32
fi
MOUNT_TARGET="$(findmnt --list --noheadings --source "UUID=$EXPECTED_USB_UUID" --output TARGET | awk 'NF{print; exit}')"
test -n "$MOUNT_TARGET"

PRE_RETRY_TIMER_STATE="$(systemctl is-active n3w-t1-ha-recovery-retry.timer || true)"
PRE_RETRY_SERVICE_STATE="$(systemctl is-active n3w-t1-ha-recovery-retry.service || true)"
PRE_IPC_SOCKET_STATE="$(systemctl is-active n3w-t1-ha-ota-ipc.socket || true)"
PRE_IPC_SERVICE_STATE="$(systemctl is-active n3w-t1-ha-ota-ipc.service || true)"
test "$PRE_RETRY_TIMER_STATE" = active
case "$PRE_RETRY_SERVICE_STATE" in inactive|failed) ;; *) exit 33 ;; esac
test "$PRE_IPC_SOCKET_STATE" = active

/usr/bin/python3 -I - "$LIVE" "$TX_FILE" "$EXPECTED_RECOVERED_LAUNCH_SHA256" <<'PY'
import json
import sys
sys.path.insert(0, sys.argv[1])
from n3w_t1_core_updater_ha_recovery_startup import LocalHaPredecessorRuntime

document = json.load(open(sys.argv[2], encoding="utf-8"))
runtime = LocalHaPredecessorRuntime()
binding, _ = runtime._restart_binding()
if binding != document["predecessor_start"]:
    raise SystemExit("RECOVERED_BINDING_DRIFT")
if binding["launch_sha256"] != sys.argv[3]:
    raise SystemExit("RECOVERED_LAUNCH_SHA_DRIFT")
runtime.verify_resident_predecessor_health(document)
print("PREMUTATION_RUNTIME_HEALTH=PASS")
PY

echo PHASE=QUIESCE_RECOVERY_CONTROL_PLANE
systemctl stop n3w-t1-ha-recovery-retry.timer
systemctl stop n3w-t1-ha-recovery-retry.service
systemctl stop n3w-t1-ha-ota-ipc.socket
systemctl stop n3w-t1-ha-ota-ipc.service
CONTROL_QUIESCED=true

test "$(systemctl is-active n3w-t1-ha-recovery-retry.timer || true)" = inactive
case "$(systemctl is-active n3w-t1-ha-recovery-retry.service || true)" in inactive|failed) ;; *) exit 34 ;; esac
case "$(systemctl is-active n3w-t1-ha-ota-ipc.socket || true)" in inactive|failed) ;; *) exit 35 ;; esac
case "$(systemctl is-active n3w-t1-ha-ota-ipc.service || true)" in inactive|failed) ;; *) exit 36 ;; esac

echo PHASE=POST_QUIESCE_EXACT_RECHECK
test "$(sha256sum "$LIVE" | awk '{print $1}')" = "$EXPECTED_OLD_PYZ_SHA256"
test "$(sha256sum "$TX_FILE" | awk '{print $1}')" = "$EXPECTED_TX_SHA256"
test "$(sha256sum "$ENV" | awk '{print $1}')" = "$EXPECTED_ENV_SHA256"
test "$(docker image inspect "$EXPECTED_HA_REF" --format '{{.Id}}')" = "$EXPECTED_HA_ID"
if docker image inspect "$EXPECTED_TARGET_REF" >/dev/null 2>&1; then exit 37; fi
if docker image inspect "$EXPECTED_TARGET_ID" >/dev/null 2>&1; then exit 38; fi

echo PHASE=ATOMIC_PYZ_REPLACEMENT
install -m 0644 "$LIVE" "$OLD"
test "$(sha256sum "$OLD" | awk '{print $1}')" = "$EXPECTED_OLD_PYZ_SHA256"
atomic_publish "$NEW" "$LIVE"
PATCH_PUBLISHED=true
test "$(sha256sum "$LIVE" | awk '{print $1}')" = "$EXPECTED_NEW_PYZ_SHA256"
/usr/bin/python3 -I "$LIVE" --help >/dev/null

echo PHASE=RESTORE_CONTROL_PLANE
restore_control_plane
test "$(systemctl is-active n3w-t1-ha-recovery-retry.timer)" = active
test "$(systemctl is-enabled n3w-t1-ha-recovery-retry.timer)" = enabled
test "$(systemctl is-active n3w-t1-ha-ota-ipc.socket)" = active
test "$(systemctl is-enabled n3w-t1-ha-ota-ipc.socket)" = enabled
case "$PRE_IPC_SERVICE_STATE" in
  active|activating) test "$(systemctl is-active n3w-t1-ha-ota-ipc.service)" = active ;;
esac

echo PHASE=POST_REPLACEMENT_HEALTH
test "$(sha256sum "$LIVE" | awk '{print $1}')" = "$EXPECTED_NEW_PYZ_SHA256"
test "$(sha256sum "$TX_FILE" | awk '{print $1}')" = "$EXPECTED_TX_SHA256"
test "$(sha256sum "$ENV" | awk '{print $1}')" = "$EXPECTED_ENV_SHA256"
test "$(docker image inspect "$EXPECTED_HA_REF" --format '{{.Id}}')" = "$EXPECTED_HA_ID"
if docker image inspect "$EXPECTED_TARGET_REF" >/dev/null 2>&1; then exit 39; fi
if docker image inspect "$EXPECTED_TARGET_ID" >/dev/null 2>&1; then exit 40; fi

/usr/bin/python3 -I - "$LIVE" "$TX_FILE" "$EXPECTED_RECOVERED_LAUNCH_SHA256" <<'PY'
import json
import sys
sys.path.insert(0, sys.argv[1])
from n3w_t1_core_updater_ha_recovery_startup import LocalHaPredecessorRuntime

document = json.load(open(sys.argv[2], encoding="utf-8"))
runtime = LocalHaPredecessorRuntime()
binding, _ = runtime._restart_binding()
if binding != document["predecessor_start"]:
    raise SystemExit("POST_REPLACEMENT_BINDING_DRIFT")
if binding["launch_sha256"] != sys.argv[3]:
    raise SystemExit("POST_REPLACEMENT_LAUNCH_DRIFT")
runtime.verify_resident_predecessor_health(document)
print("POST_REPLACEMENT_RUNTIME_HEALTH=PASS")
PY

rm -rf "$STAGE"
COMPLETED=true
trap - EXIT

echo LIVE_RECOVERY_PYZ_SHA256="$EXPECTED_NEW_PYZ_SHA256"
echo TX_FILE_SHA256="$EXPECTED_TX_SHA256"
echo COMPOSE_ENV_SHA256="$EXPECTED_ENV_SHA256"
echo TERMINAL_TRANSACTION_UNCHANGED=true
echo TARGET_2026_10_0_PRESENT=false
echo NEW_TRANSACTION=false
echo INSTALL_REPLAY=false
echo R8V13_08_AUTO_ADVANCE=false
echo RESULT=R8V13_07_RECOVERY_ARTIFACT_CONTROLLED_PYZ_REPLACEMENT_PASS
REMOTE_EOF
