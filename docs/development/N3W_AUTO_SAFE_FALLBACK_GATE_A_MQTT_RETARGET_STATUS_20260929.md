# N3-W Auto Safe Fallback Gate A MQTT Retarget Status — 2026-09-29

This document tracks the staged Gate A validation for the N3-W auto safe fallback design.

## 1. Frozen source and design authority

```text
SOURCE_HEAD=8210cf7b53e9ec934d145f1c15e9619579c923be
SOURCE_TREE=5d3e6ad7151938ffa7ac23b2b6af6663bcd10c7c
TARGET_BLOB=7279271d469958940c2b51aa4a80602078470891
PATCH_BLOB=49570a83ead08158d4d99c385740fa6d646b5e3d
ESPHOME_VERSION=2026.4.3
ESP_IDF_VERSION=5.5.4
```

Design authority:

`docs/development/N3W_AUTO_SAFE_FALLBACK_DEVELOPMENT_TEST_PLAN_V1_20260929.md`

## 2. Gate A purpose

Gate A does not implement the full fallback feature. It only proves whether the existing ESPHome/ESP-IDF MQTT backend can safely switch the runtime TCP/TLS address while keeping the original TLS identity and MQTT identity unchanged.

The required physical sequence is:

1. connected -> live alias retarget;
2. blackhole connection attempt -> restore host;
3. reconnect-wait window -> restore host.

Each blackhole recovery must return to MQTT-connected state within 25 seconds.

Until that physical timing gate passes:

```text
RUNTIME_BOUNDED_CANCEL_PROVEN=false
FULL_AUTO_FALLBACK_IMPLEMENTATION_ALLOWED=false
```

## 3. Repository and build state

```text
GATE_A_SOURCE_ADAPTER_IMPLEMENTED=true
GATE_A_SOURCE_CONTRACT_TEST_ADDED=true
GATE_A_BASELINE_CI=PASS
GATE_A_FIXTURE_CI=PASS
GATE_A_READONLY_PREFLIGHT_EXECUTOR_CI=PASS
PRIVATE_BUILD_EXECUTOR_CI=PASS
PRIVATE_BUILD_LOCAL_FAILURE_1_ROOT_CAUSE=INTEL_MACOS_CBOR2_6_NO_PREBUILT_X86_64_WHEEL_AND_NO_RUST
PRIVATE_BUILD_LOCAL_FAILURE_1_SOURCE_DEFECT=false
PRIVATE_BUILD_LOCAL_FAILURE_1_REPAIR=REUSE_EXISTING_EXACT_ESPHOME_FIRST
PRIVATE_BUILD_LOCAL=PASS
PRIVATE_BUILD_APPLICATION_SHA256=77b0fd6a98c3e837d3543eebdd30b86354790847d0c78cdab7e96f0d7d66a8ad
PRIVATE_BUILD_OTADATA_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f
PRIVATE_BUILD_CA_CERT_SHA256=66ca928aaab07eaef6aebf0a7dec9b8a0e0fac9a9d719f4e1354ea575eed0a66
PRIVATE_BUILD_SERVER_CERT_SHA256=c33bdac940da24cff4de772ff0478f0f069a3ab956dc03b1557738c4f640af4e
PRIVATE_BUILD_SERVER_KEY_SHA256=29ee45ca617fb5e4e854081e77a9ae4c468c3b07fb1d206cb0d61d86d8cbee61
PRIVATE_BUILD_ESPHOME_SOURCE=existing_exact_cli
T1_ISOLATED_LAB_EXECUTOR=IMPLEMENTED
T1_ISOLATED_LAB_EXECUTOR_CI_PENDING=false
T1_ISOLATED_LAB_EXECUTOR_CI=PASS
BOARD_B_GATE_A_WRITE_EXECUTOR=IMPLEMENTED
BOARD_B_GATE_A_WRITE_EXECUTOR_CI_PENDING=false
BOARD_B_GATE_A_WRITE_EXECUTOR_CI=PASS
KF099_ROLLBACK_EXECUTOR=IMPLEMENTED
KF099_ROLLBACK_EXECUTOR_CI_PENDING=false
KF099_ROLLBACK_EXECUTOR_CI=PASS
KF099_HISTORICAL_WRITE_AUTH_REPLAY=false
KF099_ROLLBACK_ARTIFACT_AVAILABLE=true
KF099_ROLLBACK_ARTIFACT_ID=10959875986
KF099_ROLLBACK_ARTIFACT_EXPIRES_AT=2026-10-05T08:48:09Z
```

### 3.1 Private-build CI repair

The first private-build CI attempt failed because two pytest files in different directories shared the basename `test_executor.py`. Pytest imported one under the other module name and stopped collection.

This was a CI/test-layout defect, not a firmware or Gate A source failure. The private-build test was renamed to a unique module name and the exact source/tooling CI passed.

### 3.2 2026-09-29 local private build failure and repair

The first Mac private build stopped while installing ESPHome dependencies. Python 3.11 itself was valid. On Intel macOS / CPython 3.11, `cbor2 6.1.4` had no matching prebuilt wheel, so pip fell back to a Rust source build while the Mac had no Rust toolchain.

This was not a Gate A firmware/source failure and did not access Board B or mutate T1.

The private-build executor now prefers an already installed exact ESPHome 2026.4.3 CLI and fails closed instead of automatically installing a persistent Rust toolchain on Intel macOS.

### 3.3 Private exact build passed

The Mac exact build completed using the existing ESPHome 2026.4.3 installation. Public repository evidence records only source, firmware and TLS-file hashes; it does not record LAN addresses, MQTT credentials, TLS private-key contents or the private bundle path.

### 3.4 Board B exact write gate prepared

The Board B Gate A writer is bound to the private application/otadata hashes, frozen Board B public identity hash and frozen partition-table hash.

It permits writes only to:

- `0x9000` otadata;
- `0x10000` application.

Bootloader, partition-table, product NVS and full-chip erase remain prohibited. A fresh read-only board preflight and a new one-shot authorization are required before any write.

### 3.5 Fresh KF-099 rollback gate prepared

Gate A uses a separate rollback package so that the already consumed historical KF-099 write authorization cannot be replayed. The expected restored state is the known KF-099 pairing WAIT / `repair_intent_required` baseline, not an assumed Direct MQTT baseline.

### 3.6 T1 isolated-lab fresh read-only preflight passed

2026-09-30 fresh preflight proved:

- TCP/18883 free;
- live alias unassigned;
- blackhole address unassigned;
- production Broker restart_count=0;
- Manager restart_count=0;
- no T1 mutation;
- no production Broker mutation;
- no Board access.

Public repository evidence does not store the concrete LAN addresses.

### 3.7 First T1 lab activation failed, cleanup later proved complete

The first live activation had a fresh one-shot authorization and entered `REMOTE_ACTIVATE`, then the remote Python process returned non-zero. The Mac-side exception retained only a truncated traceback, so the exact root cause was not proven from that failure output.

That activation preflight was consumed and must not be replayed.

A subsequent read-only failure forensic proved the executor's failure cleanup had completed:

```text
REMOTE_ROOT_EXISTS=false
LAB_CONTAINER_EXISTS=false
LAB_CONTAINER_RUNNING=false
LIVE_ALIAS_ACTIVE=false
PORT_18883_LISTENING=false
BROKER_RESTART_COUNT=0
MANAGER_RESTART_COUNT=0
T1_MUTATION=false
BOARD_ACCESS=false
```

Therefore:

```text
T1_ISOLATED_LAB_ACTIVATION_ATTEMPT_1=FAIL
T1_ISOLATED_LAB_PREFLIGHT_1_CONSUMED=true
T1_ISOLATED_LAB_FAILURE_CLEANUP=PASS
T1_ISOLATED_LAB_RESIDUE_STATE=CLEAN
PRODUCTION_RUNTIME_CONTINUITY=PASS
```

The first forensic occurred after the short Docker-event retention window used by the helper and therefore did not preserve the failed temporary container's exit code.

A second read-only forensic package has now been added to verify the exact production Broker image identity, PID1 effective UID/GID and the `mosquitto` account UID/GID. The current working hypothesis is a lab-file ownership/mode mismatch: the activation staged a root-owned mode-0700 directory with mode-0600 TLS/password files, while the official Mosquitto image is expected to execute the Broker under its `mosquitto` account. This remains a hypothesis until the exact T1 runtime-user forensic passes.

```text
T1_ISOLATED_LAB_PERMISSION_FORENSIC=IMPLEMENTED
T1_ISOLATED_LAB_PERMISSION_FORENSIC_CI_PENDING=true
T1_ISOLATED_LAB_PERMISSION_ROOT_CAUSE_PROVEN=false
```

## 4. Current STOP point

The next sequence is:

```text
source-contract test PASS
-> exact ESP32-C6 compile PASS
-> private exact build PASS
-> T1 isolated-lab package CI PASS
-> first fresh T1 read-only lab preflight PASS
-> first T1 activation FAIL / automatic cleanup PASS
-> exact Broker runtime-user forensic CI PENDING
-> exact Broker runtime-user forensic PENDING
-> root-cause repair PENDING
-> new fresh T1 read-only lab preflight PENDING
-> new explicit T1 mutation authorization PENDING
-> Board B exact write package CI PASS
-> Board B read-only preflight PENDING
-> Board B write authorization PENDING
-> physical timing gate PENDING
-> fresh KF099 rollback preflight PENDING
-> fresh KF099 rollback write authorization PENDING
```

Do not replay the consumed first activation preflight or its authorization.

Do not write Board B until the T1 isolated lab is successfully activated under a new fresh preflight and new explicit authorization.
