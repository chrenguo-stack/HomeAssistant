# N3-W R10 T1 candidate live upgrade — preexecution and authorization

Date: 2026-10-28

## 1. Gate

```text
TASK=N3W_SCAN_TRIGGERED_FIRST_PAIRING_R10_T1_CANDIDATE_LIVE_UPGRADE_PREEXECUTION_AND_AUTHORIZATION_20261028_01

PACKAGE_HEAD=81546685bbb7d9d6aad9cf574d871277ca4b44b1
ARTIFACT_ID=12792592683
ARTIFACT_NAME=n3w-r10-t1-upgrade-81546685bbb7
ARTIFACT_DIGEST=sha256:e4f236387c67a2ac88623bb2166201fcc44589dc99504aded4b9df688ad5dc9c
MANIFEST_SHA256=4c9eca65c535cc7c5fd1f48891844f381338719d2d422d0f5464cc8f7a660664

T1_ACCESS=false
T1_MUTATION=false
SERVICE_STOP_START=false
BOARD_ACCESS=false
T1_UPGRADE_AUTHORIZATION_GRANTED=false
UPGRADE_AUTHORIZATION_CONSUMED=false
MERGE=false
```

This gate prepares the exact operator package and authorization boundary for the later live T1 production-software upgrade.

It does not stage the artifact onto T1 and does not execute the upgrade.

## 2. Authoritative artifact

```text
WORKFLOW_RUN_ID=40634208155
PACKAGE_HEAD=81546685bbb7d9d6aad9cf574d871277ca4b44b1

ARTIFACT_ID=12792592683
ARTIFACT_NAME=n3w-r10-t1-upgrade-81546685bbb7
ARTIFACT_SIZE_BYTES=61540313
ARTIFACT_DIGEST=sha256:e4f236387c67a2ac88623bb2166201fcc44589dc99504aded4b9df688ad5dc9c

MANIFEST_SHA256=4c9eca65c535cc7c5fd1f48891844f381338719d2d422d0f5464cc8f7a660664

MANAGER_TAR_SHA256=de0a5de5f0922dafc3485414ad7add1e31ecdd61c1cf8e473e00c5350eb83e1e
MANAGER_TAR_SIZE_BYTES=61439488

MANAGER_IMAGE_ID=sha256:bf5a1f7def35849dec43c232f2caad9e429723b5ce86878a73b3b7a7e5a50169
MANAGER_IMAGE_SIZE_BYTES=201686995

EXECUTOR_SHA256=214fef4a1feb6c446aad25847d7615a6f48cca054f6d09ce8b5c7b3825d5d1a4
EXECUTOR_SIZE_BYTES=65222

PYTHON_DISTRIBUTIONS_SHA256=c29bbdd603c74aa7c36f33a32f22d86e5dacb6c34ec2266fc55eb8660cac0ae6
PYTHON_DISTRIBUTION_COUNT=17
```

The exact artifact expires on GitHub around 2026-11-27T04:48:56Z.

## 3. Preauthorization Mac-only artifact acquisition

Artifact download and verification may be performed on the Mac before live-upgrade authorization because it does not mutate T1.

Required local work root:

```text
$HOME/N3W_R10_T1_CANDIDATE_LIVE_UPGRADE_20261028_01
```

Recommended exact commands:

```bash
set -e
ROOT="$HOME/N3W_R10_T1_CANDIDATE_LIVE_UPGRADE_20261028_01"
ZIP="$ROOT/n3w-r10-t1-upgrade-81546685bbb7.zip"
PKG="$ROOT/package"
test ! -e "$ROOT"
mkdir -m 700 "$ROOT"
gh api "/repos/chrenguo-stack/HomeAssistant/actions/artifacts/12792592683/zip" > "$ZIP"
test "$(shasum -a 256 "$ZIP" | awk '{print $1}')" = "e4f236387c67a2ac88623bb2166201fcc44589dc99504aded4b9df688ad5dc9c"
mkdir -m 700 "$PKG"
unzip -q "$ZIP" -d "$PKG"
test "$(shasum -a 256 "$PKG/manifest.json" | awk '{print $1}')" = "4c9eca65c535cc7c5fd1f48891844f381338719d2d422d0f5464cc8f7a660664"
test "$(shasum -a 256 "$PKG/greenhouse-manager-arm64.tar" | awk '{print $1}')" = "de0a5de5f0922dafc3485414ad7add1e31ecdd61c1cf8e473e00c5350eb83e1e"
test "$(stat -f %z "$PKG/greenhouse-manager-arm64.tar")" = "61439488"
test "$(shasum -a 256 "$PKG/upgrade-executor.py" | awk '{print $1}')" = "214fef4a1feb6c446aad25847d7615a6f48cca054f6d09ce8b5c7b3825d5d1a4"
test "$(stat -f %z "$PKG/upgrade-executor.py")" = "65222"
test "$(shasum -a 256 "$PKG/manager-python-distributions.json" | awk '{print $1}')" = "c29bbdd603c74aa7c36f33a32f22d86e5dacb6c34ec2266fc55eb8660cac0ae6"
python3 - "$PKG/manifest.json" <<'PY'
import json,sys
m=json.load(open(sys.argv[1],encoding="utf-8"))
assert m["schema"]=="gh.n3w.r10-t1-candidate-upgrade-package/1"
assert m["package_head"]=="81546685bbb7d9d6aad9cf574d871277ca4b44b1"
assert m["predecessor_source"]=="03dab2bd04e7e8cb71faa1bd13a027ace8cecdf6"
assert m["target_source"]=="e299c937a7b89bb8a7b9a7432186ba46a416cd44"
assert m["manager"]["image_id"]=="sha256:bf5a1f7def35849dec43c232f2caad9e429723b5ce86878a73b3b7a7e5a50169"
assert m["manager"]["image_size_bytes"]==201686995
assert m["manager"]["tar_sha256"]=="de0a5de5f0922dafc3485414ad7add1e31ecdd61c1cf8e473e00c5350eb83e1e"
assert m["executor"]["sha256"]=="214fef4a1feb6c446aad25847d7615a6f48cca054f6d09ce8b5c7b3825d5d1a4"
assert m["policy"]["homeassistant_image_included"] is False
assert m["policy"]["broker_image_included"] is False
assert m["policy"]["t1_access"] is False
assert m["policy"]["t1_mutation"] is False
print("LOCAL_ARTIFACT_VERIFY=PASS")
PY
```

Expected public output:

```text
LOCAL_ARTIFACT_VERIFY=PASS
```

No artifact content, private key or private backup should be pasted into chat.

## 4. Separate T1 staging boundary

Copying the verified package from Mac to T1 is a T1 write and is therefore forbidden before explicit live-upgrade authorization.

After authorization only, the package will be staged into a new root-owned private directory under:

```text
/var/lib/n3w-r10-candidate-upgrade-staging/<authorization-hash>/
```

The staging transaction must:

- create the directory with mode 0700;
- copy only the 10 artifact files from the verified Mac package;
- set regular file permissions to non-world-writable;
- verify manifest SHA and every member binding locally on T1;
- not load the Manager image yet;
- not stop services yet;
- not change Compose/systemd/firewall/database yet.

If staging verification fails, the directory is removed and no one-shot live authorization is claimed.

## 5. Fresh live preclaim

Even after staging, the executor performs a fresh live preclaim before one-shot authorization claim.

It must re-prove:

```text
CURRENT_MANAGER_IMAGE=local/greenhouse-manager:fresh-03dab2bd04e7
BROKER_IMAGE=local/n3w-mosquitto:2.1.2-3184566d
HOMEASSISTANT_IMAGE=local/n3w-homeassistant:2026.10.0-0c73235a

SERVICES_ACTIVATION=active/loaded
BROKER_ACTIVATION=active/loaded
BROKER_INGRESS_GUARD=active/loaded

47110_TCP=0
47111_UDP=0
47112_TCP=0

REGISTRATION_GUARD_PREDECESSOR=absent
REGISTRATION_TLS_PREDECESSOR=absent
TRUSTED_LAN_RUNTIME_PREDECESSOR=absent

PAIRING_WINDOW=CLOSED
DATABASE_INTEGRITY=PASS
CURRENT_REGISTRATION_COUNT=1
FIRST_REGISTRATION_TABLE_PRESENT=false

TARGET_MANAGER_IMAGE_PREEXISTING=false
F4_SERVICES_ELIGIBILITY=PASS
BROKER_DYNSEC=regular/private/readable
LIVE_PREDECESSOR_FILES=exact
CAPACITY=PASS
```

A failure here occurs before the one-shot authorization claim.

## 6. One-shot live authorization

This upgrade requires a new authorization separate from the already existing board-write authorization.

Frozen authorization ID:

```text
N3W_R10_T1_CANDIDATE_UPGRADE_20261028_01
```

Frozen operator confirmation consumed by the executor:

```text
APPLY R10 T1 CANDIDATE UPGRADE: YES
```

Chat authorization is not the same as the executor confirmation string.

The user must explicitly authorize the live T1 upgrade in chat before package staging begins.

Recommended chat authorization wording:

```text
批准 T1 生产软件升级：
N3W_R10_T1_CANDIDATE_UPGRADE_20261028_01
```

Before that explicit approval:

```text
T1_UPGRADE_AUTHORIZATION_GRANTED=false
UPGRADE_AUTHORIZATION_CONSUMED=false
```

## 7. Live mutation order after authorization

Frozen high-level order:

```text
1. Mac exact artifact already verified
2. stage exact package to T1 private directory
3. T1 local package verification
4. fresh live preclaim
5. one-shot authorization claim
6. private static/F4 rollback capture
7. load exact Manager image
8. generate dedicated registration TLS in private staging
9. stop n3wfc4-services-activation.service
10. prove Broker container continuity
11. prove Manager=0 and HA=0 running containers
12. capture quiescent /var/lib/greenhouse-manager archive
13. install bounded live files
14. change GH_MANAGER_IMAGE only
15. install registration TLS
16. daemon-reload
17. enable/start registration guard
18. rebind exactly three F4 installed-file entries
19. preserved F4 eligibility PASS
20. start production services unit
21. bounded successor readiness
22. strict postcheck
23. commit F4 successor
24. commit upgrade transaction
```

## 8. Terminal success contract

PASS requires:

```text
TARGET_MANAGER_IMAGE_ID=sha256:bf5a1f7def35849dec43c232f2caad9e429723b5ce86878a73b3b7a7e5a50169

BROKER_CONTAINER_CONTINUITY=true
BROKER_DYNSEC_SHA_UNCHANGED=true
HOMEASSISTANT_IMAGE_UNCHANGED=true

REGISTRATION_GUARD_ACTIVE=true
TRUSTED_PRODUCT_LAN_READY=true

47110_TCP=1
47111_UDP=1
47112_TCP=0

PAIRING_WINDOW=CLOSED

DATABASE_INTEGRITY=PASS
FIRST_REGISTRATION_TABLE_PRESENT=true
UNRESOLVED_FIRST_REGISTRATION=0
CURRENT_REGISTRATION_COUNT=1

F4_SERVICES_ELIGIBILITY=PASS
F4_HISTORICAL_PACKAGE_BINDING_UNCHANGED=true
F4_SUCCESSOR_INSTALLED_FILES_BOUND=true

BOARD_ACCESS=false
```

## 9. Rollback boundary

Any post-claim failure enters rollback.

Rollback is allowed to restore Manager state/config only after proving:

```text
RUNNING_MANAGER_CONTAINER_COUNT=0
RUNNING_HOMEASSISTANT_CONTAINER_COUNT=0
```

If that cannot be proven, rollback stops as:

```text
ROLLBACK_FAILED
```

without overwriting Manager state.

Broker remains running throughout.

If Broker container continuity or Broker DynSec SHA changes unexpectedly, PASS is impossible and rollback cannot claim full predecessor restoration.

## 10. Board boundary

This gate does not access the ESP32-C6 board.

The original R10 board-write authorization remains separate and unconsumed.

After the T1 upgrade reaches PASS, the R10 T1+board read-only physical preflight is rerun before any board write.

## 11. Current stop

```text
PREEXECUTION_PACKAGE=FROZEN
LOCAL_MAC_ARTIFACT_VERIFY=NOT_YET_EXECUTED_BY_OPERATOR
T1_STAGING=NOT_STARTED
T1_UPGRADE_AUTHORIZATION_GRANTED=false
UPGRADE_AUTHORIZATION_CONSUMED=false

STOP_REASON=EXPLICIT_LIVE_T1_UPGRADE_AUTHORIZATION_REQUIRED
```
