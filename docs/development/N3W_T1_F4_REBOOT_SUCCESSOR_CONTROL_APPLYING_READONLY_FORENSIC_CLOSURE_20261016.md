# N3-W T1 F4 Reboot Successor — CONTROL_APPLYING Read-only Forensic Closure

Date: 2026-10-16

```text
TASK=N3W_T1_F4_REBOOT_SUCCESSOR_CONTROL_APPLYING_READONLY_FORENSIC_20261016_01
RESULT=CLOSED_PASS_FORENSIC

INSTALL_AUTHORIZATION_ID=N3W_T1_F4_REBOOT_SUCCESSOR_CONTROL_INSTALL_LIVE_20261016_01
INSTALL_AUTHORIZATION_CLAIMED=true
INSTALL_AUTHORIZATION_CONSUMED=true
INSTALL_AUTHORIZATION_REPLAY_ALLOWED=false
INSTALL_CLAIM_SHA256=6c8cad9331094bbb0abe89ff67bc75b724d66c7eb97cdf6f4117c3bce5ed4d80
INSTALL_CLAIM_STAGE=CONTROL_APPLYING

REBOOT_AUTHORIZATION_CLAIMED=false
REBOOT_EXECUTED=false
BOARD_ACCESS=false
FORENSIC_MUTATION=false

SOURCE_DEFECT_CONFIRMED=true
SOURCE_DEFECT=f4_runtime_contract_requires_nonexistent_board_access_field
SOURCE_REPAIR_PR=605
SOURCE_REPAIR_HEAD=99e0c4aecb013cf0dc8b350f851a38d670b9d6e7
SOURCE_REPAIR_CI=13_SUCCESS_0_FAILURE_0_PENDING

REPAIR_ARTIFACT_ID=12029738934
REPAIR_ARTIFACT_ZIP_SHA256=9fda3a2b21bf37484018f9d58bed60bb0f5ba28bc977a5a2ff33c8063c5bb03c
REPAIR_CONTROL_TAR_SHA256=3f23029c601e8d66661ca36941467021af0eb376929c87a42ce258a4e4d98291
REPAIR_MANIFEST_SHA256=085e3fd1c56ee4f4d35f1acc9408a4874f5a09dde90bc93d4df84a87ba90d43d
REPAIR_GUARD_SHA256=0bf84b4459e0ce86d45f9713f8d583f74d76ca49b002381867dbe39716913d38

NEXT_ONE_GATE=N3W_T1_F4_REBOOT_SUCCESSOR_POSTCLAIM_RECOVERY_SOURCE_DESIGN_20261016_01
AUTO_EXECUTE_LIVE_RECOVERY=false
```

## Live forensic result

The read-only forensic confirmed that the failed live control-install is a deterministic post-claim source defect,
not a product runtime failure.

The consumed install claim is present and stopped at:

```text
stage=CONTROL_APPLYING
source_head=5368acc1eb50f1fc62bbd7c16ff9e64139131a29
control_manifest_sha256=2f2ae69dbf78d5f578fa60bbee7fb269a5d0c3b17a00e2f697bc65d3ed91c40c
f4_transaction_sha256=49e7839ffe5d9e00391577a78c7c6ceb9c85a9a7cdd240ee22cc38485a3e569b
pre_runtime_snapshot_sha256=29183afd73d71d4e85d8481d96f062b7c099d6721b46708a49495d58a39994f0
pre_certificate_snapshot_sha256=68264cf00af8a5748fc20c17edb4969533d326905bb3e959960b3f2ab0103947
control_repair_authorization_claimed=true
control_repair_authorization_consumed=true
control_repair_authorization_replay_allowed=false
installation_apply_started=true
installation_verified=null
```

The install authority lock exists with root:root 0600 metadata. No reboot claim exists.

## Exact partially installed control

All five installed control targets are present and exactly match the old source/artifact that entered the live gate:

```text
/usr/local/sbin/n3w-t1-f4-certificate-runtime-guard
sha256=06f122d478176271f0db8f7f6222ef6ce618e94bf958f72ca62474ca2d76d57c
mode=0755

/usr/local/sbin/n3w-t1-f4-reboot-authority
sha256=b132ec94ae115766b580480b2d58850ee052639d772ab21dbec4c83f0c769822
mode=0755

/usr/local/sbin/n3w-t1-f4-reboot-verify
sha256=ab1b5a31c265643be00575688dd09248359794f3cb230b24f8ce9025e3c7408b
mode=0755

/etc/systemd/system/n3wfc4-broker-certificate-lifecycle.service.d/10-runtime-status-evolution.conf
sha256=9a731615268cee76819e28fa2aede8993f4f59ab65b48c5a6c8e09ebdee2c256
mode=0644

/usr/local/share/n3w-t1-f4-reboot-successor/reboot-successor-manifest.json
sha256=2f2ae69dbf78d5f578fa60bbee7fb269a5d0c3b17a00e2f697bc65d3ed91c40c
mode=0644
```

The installed manifest records exactly four control files and source head
`5368acc1eb50f1fc62bbd7c16ff9e64139131a29`.

The successor systemd drop-in is loaded.

## Deterministic guard defect reproduced

The installed guard fails exactly as observed during the live install:

```text
INSTALLED_GUARD_RC=2
error_code=f4_runtime_contract_invalid
```

The frozen F4 host reports:

```json
{"broker_active_state":"active","production_service_start":true,"running_services":["broker","homeassistant","manager"],"runtime_service_probe":"PASS","services_active_state":"active"}
```

and explicitly has no `board_access` field.

The failing PR #600 guard required:

```text
runtime.get("board_access") is False
```

which can never be true for the actual frozen F4 `_runtime_activity()` schema. This independently confirms the
source defect.

## Product state remains healthy

The tail forensic completed and proved:

```text
CONTROL_APPLYING_CLAIM=PASS
BROKER_ACTIVE=active
SERVICES_ACTIVE=active
CERT_TIMER_ENABLED=enabled
CERT_TIMER_ACTIVE=inactive
CERT_SERVICE_ACTIVE=inactive
PRODUCT_LISTENER_PORTS=1883,8123,8883

TX_UNCHANGED=true
RUNTIME_ACCEPTANCE_UNCHANGED=true
CERT_STATUS_UNCHANGED=true
BOOT_ID_UNCHANGED=true
RUNTIME_IDENTITY_UNCHANGED=true
CERTIFICATE_IDENTITY_UNCHANGED=true

INSTALL_AUTHORIZATION_ALREADY_CONSUMED=true
INSTALL_AUTHORIZATION_REPLAY_ALLOWED=false
REBOOT_AUTHORIZATION_CLAIMED=false
REBOOT_EXECUTED=false
BOARD_ACCESS=false
FORENSIC_MUTATION=false
FORENSIC_TAIL_RESULT=CLOSED_PASS
```

The T1 must therefore be treated as a healthy product runtime with a partially completed successor-control
installation at `CONTROL_APPLYING`.

## PR #605 source repair review

PR #605 changes exactly two files:

- `tools/n3w_t1_f4_certificate_runtime_guard.py`;
- `tests/tools/test_n3w_t1_f4_certificate_runtime_guard.py`.

The production delta removes only the impossible `board_access` field requirement from the runtime-activity
check. It retains:

- `production_service_start == true`;
- exact running-service set Broker + Manager + Home Assistant;
- F4 provisioning binding;
- F4 transaction binding;
- factory binding;
- installed-material verification;
- certificate status/material/fingerprint checks.

Regression tests cover both the actual frozen F4 runtime-activity shape without `board_access` and rejection of an
incomplete runtime service set.

All 13 workflows observed on exact PR #605 HEAD
`99e0c4aecb013cf0dc8b350f851a38d670b9d6e7` passed.

The exact repaired successor artifact is:

```text
ARTIFACT_ID=12029738934
ZIP_SHA256=9fda3a2b21bf37484018f9d58bed60bb0f5ba28bc977a5a2ff33c8063c5bb03c
CONTROL_TAR_SHA256=3f23029c601e8d66661ca36941467021af0eb376929c87a42ce258a4e4d98291
MANIFEST_SHA256=085e3fd1c56ee4f4d35f1acc9408a4874f5a09dde90bc93d4df84a87ba90d43d
```

The repaired manifest still contains exactly four control files. Only the runtime guard content hash changes from
the installed old package:

```text
old_guard_sha256=06f122d478176271f0db8f7f6222ef6ce618e94bf958f72ca62474ca2d76d57c
repaired_guard_sha256=0bf84b4459e0ce86d45f9713f8d583f74d76ca49b002381867dbe39716913d38
```

The authority, verifier and drop-in hashes remain unchanged.

## Recovery boundary

The consumed install authorization must never be replayed.

A simple overwrite of only the guard is also insufficient because the installed manifest and the consumed
`CONTROL_APPLYING` claim are bound to the old source head and old guard hash. A safe recovery therefore needs a
new repository-owned post-claim recovery authority that:

1. validates the exact existing `CONTROL_APPLYING` claim and old installed control state;
2. validates the exact repaired artifact and its new manifest;
3. obtains and durably consumes a new, distinct recovery authorization before mutation;
4. replaces only the exact changed/required control material;
5. preserves the original consumed install authorization history;
6. updates the durable control record to a fully verified `CONTROL_READY` state with explicit recovery
   provenance;
7. verifies current F4/runtime/certificate/boot identities did not drift;
8. leaves reboot authorization unclaimed.

No live recovery mutation is authorized by this closure.

```text
REPLAY_OLD_INSTALL_AUTHORIZATION=false
RAW_FILE_OVERWRITE_FORBIDDEN=true
RAW_REBOOT_FORBIDDEN=true
RECOVERY_AUTHORIZATION_GRANTED=false
```
