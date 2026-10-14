# N3-W T1 per-device fresh Armbian automated deployment — F2 live read-only preflight closure

Date: 2026-10-14

```text
GATE=N3W_T1_PER_DEVICE_FRESH_ARMBIAN_AUTOMATED_DEPLOYMENT_F2_FRESH_T1_READONLY_PREFLIGHT_20261014_01
RESULT=CLOSED_PASS

BASE_MAIN=3e05e82a7d7e871d2966e78e8cb5caff601a0152
PR=542
F2_SOURCE_HEAD=33bf71de0cf35984af74e1614aca72a893890b38
F2_SOURCE_TREE=0ee122fcafb424ef94a79ab14c79dcb292a7a030
F2_SOURCE_CI=12_SUCCESS_0_FAILURE_0_PENDING

ARTIFACT_RUN_ID=38536117520
ARTIFACT_ID=11880082975
ARTIFACT_NAME=n3w-t1-fresh-bootstrap-deployable-3e05e82a7d7e871d2966e78e8cb5caff601a0152
ARTIFACT_DIGEST=sha256:de6228bd453b0c9de31cb80778b9b50e6df8620a4c2131dcebd8fa3ff29c1f97
ARTIFACT_SIZE_BYTES=2535580472
ARTIFACT_SOURCE_HEAD=3e05e82a7d7e871d2966e78e8cb5caff601a0152

TARGET_SHA256=2b149655aab07a3941fa76d0fd03e6b632e628077d5cddcf4eafa0e2c9e313fd
F2_STATUS=PASS
FAILURES=[]

READ_ONLY=true
T1_FILE_WRITE=false
LIVE_RUNTIME_MUTATION=false
PRODUCTION_SERVICE_START=false
AUTHORIZATION_CLAIMED=false
F3_AUTHORIZED=false
BOARD_ACCESS=false
MERGE=false
```

## 1. What was proven

The exact F2 source and exact merged-main deployable artifact were exercised against the selected fresh
Armbian T1. The final execution reached the acceptance decision and returned `PASS` with an empty failure
list.

The successful preflight proves the current target satisfies the F2 host-readiness contract needed before
requesting F3:

- exact Armbian OS/board/architecture binding;
- completed Armbian first boot and synchronized host identity;
- SSH management, NetworkManager, default route, DNS and synchronized time;
- no product containers/images/volumes/paths/units/listeners or old provisioning/authorization/staging residue;
- Docker/Compose is not yet installed, but the fresh-host prebaseline capacity model passes;
- the fresh host has the expected Ubuntu ports / resolute / universe source configuration;
- the exact one-image-at-a-time deployable artifact and capacity contract are valid for this target.

F2 does not prove F3 deployment, package installation, provisioning, service activation, F4 acceptance,
board pairing or reboot stability after product installation.

## 2. Live evidence-driven repairs completed before PASS

### 2.1 Fresh-host SSH authentication

The first real attempt stopped before host evaluation because the executor forced
`BatchMode=yes`. Direct read-only evidence proved the host was reachable and interactive password SSH
worked. The executor was repaired to allow one normal OpenSSH password prompt without storing or passing
the password as a CLI argument.

### 2.2 Armbian firstrun durable completion

A later F2 attempt stopped on `firstboot` because the executor required a nonzero
`ExecMainStartTimestampMonotonic`. Real target evidence instead showed the durable completed state:

```text
ActiveState=inactive
UnitFileState=disabled
Result=success
ExecMainStatus=0
ExecMainStartTimestampMonotonic=0
```

The final contract therefore uses the durable disabled/inactive/success/zero-exit state and does not require
a volatile monotonic timestamp to survive as completion proof.

### 2.3 Fresh empty APT index

The same attempt stopped on `docker_packages`. Read-only evidence proved:

```text
APT_LIST_FILE_COUNT=0
UBUNTU_PORTS_SOURCE=true
RESOLUTE_SOURCE=true
UNIVERSE_COMPONENT=true
DOCKER_IO_LOCAL_CANDIDATE=NONE
DOCKER_COMPOSE_V2_LOCAL_CANDIDATE=NONE
```

F2 must not run `apt update` merely to create local candidate metadata. The final contract accepts this
genuinely fresh state only when the local package index is empty and the exact Ubuntu ports / resolute /
universe source is configured. If an index exists but candidates are absent, or the expected source
components are missing, the gate still fails closed.

All three repairs were implemented in repository source/tests, completed fresh exact-head CI, and were
re-exercised on the real target before F2 was closed.

## 3. Evidence boundary

Private raw F2 evidence remains in the operator-managed private local evidence area and is intentionally not
committed to the public repository. The public closure retains only safe hashes, exact source/artifact
authority and the bounded acceptance result.

```text
PRIVATE_RAW_EVIDENCE_IN_PUBLIC_GIT=false
PUBLIC_SAFE_TARGET_BINDING=SHA256_ONLY
SECRET_VALUES_IN_PUBLIC_GIT=false
```

## 4. F2 closure boundary

```text
F2_LIVE_ACCEPTANCE=CLOSED_PASS
F3_TARGET_EXECUTION=NOT_STARTED
F3_AUTHORIZED=false
PACKAGE_INDEX_REFRESH_EXECUTED=false
PACKAGE_INSTALL_EXECUTED=false
DOCKER_MUTATION_EXECUTED=false
PRODUCT_DEPLOYMENT_EXECUTED=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
```

F2 PASS means only that the selected fresh T1 is eligible to proceed to the separately authorized F3 route
after repository merge/source rebind. It does not itself grant any F3 mutation authority.

## 5. Next route

```text
NEXT_ONE_GATE=N3W_T1_PER_DEVICE_FRESH_ARMBIAN_AUTOMATED_DEPLOYMENT_F2_PR542_MERGE_CLOSURE_20261014_01
AUTO_EXECUTE_F3=false
```

PR #542 must be merged first while preserving the exact F2 source commit in history. After merge, main and
post-merge CI must be freshly rebound before any F3 authorization or target mutation is considered.
