# N3-W T1 F4 Stopped Runtime Acceptance Recovery — Exact Artifact Binding and Live Preexecution Preparation

Date: 2026-10-16

~~~text
TASK=N3W_T1_F4_STOPPED_RUNTIME_ACCEPTANCE_RECOVERY_EXACT_ARTIFACT_BINDING_AND_LIVE_PREEXECUTION_PREPARATION_20261015_01
STATUS=CLOSED_PASS

SOURCE_REPAIR_PR=571
SOURCE_REPAIR_HEAD=f0bcc2ac50326b9a988405af8a2aad4c51694810
SOURCE_REPAIR_CI=PASS
SOURCE_REPAIR_EXACT_PACKAGE_CI=PASS

SOURCE_CLOSURE_PR=572
SOURCE_CLOSURE_HEAD=5981cf6eb480632e23eec7d5cb6d115ef7eaff61
SOURCE_CLOSURE_CI=PASS

T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
ARTIFACT_TRANSFER_TO_T1=false
PRODUCTION_SERVICE_START=false
PERSISTENCE_ENABLED=false
CERTIFICATE_TIMER_ENABLE=false
BOARD_ACCESS=false
REBOOT=false
MERGE=false
~~~

## 1. Fresh repository / CI rebind

PR #571 remains OPEN/DRAFT/unmerged and mergeable at exact product source
`f0bcc2ac50326b9a988405af8a2aad4c51694810`.

All 13 relevant exact-head PR workflows are completed/success, including:

~~~text
N3W_T1_F4_ACTIVATION_SOURCE_CI=PASS
N3W_T1_F4_EXACT_CONTROL_PACKAGE_CI=PASS
GREENHOUSE_MANAGER_CI=PASS
PUBLIC_REPOSITORY_SAFETY_CI=PASS
M2_PRIVATE_MOSQUITTO_CI=PASS
M2_DYNAMIC_SECURITY_CI=PASS
M2_MANAGER_RUNTIME_SECRET_OWNERSHIP_CI=PASS
M2_NODE_AUTH_BOARD_LAB_CI=PASS
M2_NODE_AUTH_NATIVE_BOARD_LAB_CI=PASS
M2_NODE_AUTH_ISOLATED_LAB_CI=PASS
H3_N2_STAGE2B3_PAIRING_RUNTIME_CI=PASS
M0_VERTICAL_SLICE_CI=PASS
C07_NODE_RETIREMENT_CI=PASS
~~~

PR #572 also remains OPEN/DRAFT/unmerged and mergeable. Its latest documentation-only closure head
`5981cf6eb480632e23eec7d5cb6d115ef7eaff61` has all 12 triggered workflows completed/success.

No product-source drift was found after the PR #571 closure head.

## 2. Successor exact artifact authority

~~~text
SOURCE_HEAD=f0bcc2ac50326b9a988405af8a2aad4c51694810

WORKFLOW_RUN_ID=38767114055
WORKFLOW_JOB_ID=116533101018
WORKFLOW_JOB_NAME=exact-f4-package

ARTIFACT_ID=11990381805
ARTIFACT_NAME=n3w-t1-f4-control-package-f0bcc2ac50326b9a988405af8a2aad4c51694810
ARTIFACT_SIZE_BYTES=39632
ARTIFACT_EXPIRED=false
ARTIFACT_ZIP_SHA256=7c633170dfcbe2f9587fd51eaa48455505069c21b2c76df48e9d9ef54249b225

CONTROL_PACKAGE_TAR_SHA256=9d1ba965ac72887dbac6cc48381d228843c6c489e92217ef65886d73cd0c309d
CONTROL_PACKAGE_TAR_SIZE_BYTES=235520

PACKAGE_MANIFEST_SHA256=37c620daf57a3f49614a4c2824c55b7e20413ef63593cd1781e4f359fb4729b5
PACKAGE_SCHEMA=gh.n3w-t1-f4-activation-package/1
PACKAGE_FILE_COUNT=8

SUCCESSOR_LAUNCHER_SHA256=eaf28175909479007d6d1df7522811d032890dcaa2a2280228c93e6dce128bb3
SUCCESSOR_LAUNCHER_SIZE_BYTES=177919

BUILD_REPORT_STATUS=PASS
BUILD_REPORT_SOURCE_HEAD=f0bcc2ac50326b9a988405af8a2aad4c51694810
BUILD_REPORT_MANIFEST_SHA256=37c620daf57a3f49614a4c2824c55b7e20413ef63593cd1781e4f359fb4729b5
BUILD_REPORT_SECRET_VALUES_INCLUDED=false
BUILD_REPORT_PRODUCTION_SERVICE_START=false
BUILD_REPORT_BOARD_ACCESS=false
~~~

GitHub artifact metadata reports the ZIP digest above. The artifact was independently re-downloaded and byte-rehashed;
the downloaded ZIP SHA-256 equals the GitHub artifact digest exactly.

The embedded `n3w-t1-f4-control-package.tar.sha256` sidecar equals the independently computed tar SHA-256 exactly.

The embedded build report, manifest and package files were independently extracted and rehashed. The manifest SHA-256
equals the build report exactly, and the launcher SHA-256/size equal its manifest record exactly.

## 3. Failed-source artifact authority

The real T1 stopped state is bound to the previously installed exact control package:

~~~text
FAILED_SOURCE_HEAD=ffcbb1a890e42ac776c6d90000bf3f25195da01d

FAILED_WORKFLOW_RUN_ID=38753221987
FAILED_ARTIFACT_ID=11982052678
FAILED_ARTIFACT_NAME=n3w-t1-f4-control-package-ffcbb1a890e42ac776c6d90000bf3f25195da01d
FAILED_ARTIFACT_ZIP_SHA256=beb128f237d2e07f29a5f9a32d35a535de1bf8b2a099a5a3c55fbfff7d34071b

FAILED_CONTROL_PACKAGE_TAR_SHA256=9d24125d136ed5a2c5e8f98687a2718a8caa50c565a8fa0d389e4ceabd09c074
FAILED_PACKAGE_MANIFEST_SHA256=4df1d95b0849aa4ca574f31f8fd55e57fe118fba1c5913d2d8b3f96e286ec669
FAILED_LAUNCHER_SHA256=f7f742505f439675fb19ecf8f98b8235703d6e2a1c5c9217ecfe01a025be3c8b
FAILED_LAUNCHER_SIZE_BYTES=157616
~~~

The failed-source artifact was also independently re-downloaded and rehashed. Its ZIP digest matches GitHub artifact
metadata, its tar digest matches its sidecar, and its manifest/launcher hashes reproduce the exact bindings already
recorded by the real T1 failure evidence.

## 4. Launcher-only delta proof

Both old and successor package manifests contain exactly the same eight package paths.

The only manifest binding that changed is:

~~~text
tools/n3w_t1_f4_activation_host.py
~~~

Old:

~~~text
SHA256=f7f742505f439675fb19ecf8f98b8235703d6e2a1c5c9217ecfe01a025be3c8b
SIZE=157616
~~~

Successor:

~~~text
SHA256=eaf28175909479007d6d1df7522811d032890dcaa2a2280228c93e6dce128bb3
SIZE=177919
~~~

The other seven files are byte-for-byte identical between the two exact artifacts:

~~~text
infra/n3w-t1/NetworkManager/dispatcher.d/90-n3wfc4-broker-ingress-guard
  116e21eb30a4766817ac799a4cde196dad2245f62cfd559b8c253338b91cecab

infra/n3w-t1/f4/n3wfc4-broker-activation.service
  af8453a9643e8c1828f198a2f66f8f316dffd458a02f81d0606d94cccfb96ce3

infra/n3w-t1/f4/n3wfc4-broker-certificate-lifecycle.service
  4f948f9cf27a03d684cc4fb1845072d97914ec77ecd1870cdfac3d9a17f5b81b

infra/n3w-t1/f4/n3wfc4-services-activation.service
  cb205fb4136204ee2c4ce163a893495531ced8b051941f0c1d0a525d8ce0b47e

infra/n3w-t1/systemd/n3wfc4-broker-certificate-lifecycle.timer
  9a56f05c8541645708dc2bf57c240cbdce94a9ab07a74bb95f389e8d230f7a6f

tools/n3w_broker_certificate_lifecycle.py
  6ea40200152a1f1aa72807e1780ee41004d2ed99fb9687a86a159eaef4b87779

tools/n3w_t1_broker_authenticated_readiness.py
  f5814cbbed511f0937e70c3e49050100cc60e3a30db30c3c2d696f81d0511c56
~~~

Therefore:

~~~text
PACKAGE_PATH_SET_EQUAL=true
NON_LAUNCHER_FILE_COUNT=7
NON_LAUNCHER_BYTE_IDENTITY=PASS
ALLOWED_DELTA=LAUNCHER_ONLY
~~~

This independently proves the exact package satisfies the recovery source's launcher-only delta contract.

## 5. Successor launcher content binding

The extracted successor launcher has:

~~~text
SHEBANG=#!/usr/bin/python3
RECOVERY_COMMAND_PRESENT=true
RECOVERY_CONFIRMATION_PRESENT=true
FAILED_SOURCE_HEAD_CONSTANT_PRESENT=true
FAILED_MANIFEST_CONSTANT_PRESENT=true
FAILED_LAUNCHER_CONSTANT_PRESENT=true
MANAGER_SOCKET_PROBE_INHERITS_CONTAINER_USER=true
~~~

The fixed `_container_established_socket_count()` uses:

~~~text
docker exec <container> python3 ...
~~~

and no longer forces `--user 0:0` in that socket-count function.

The package tar stores the launcher as mode 0644. This is acceptable for staging because the recovery command will be
invoked explicitly through `python3 <package-launcher>`. The atomic installed-target replacement remains bound to
mode 0755 by `INSTALL_MAP`.

The future live command MUST NOT attempt to execute the staged launcher directly as an executable file.

## 6. Prospective authorization namespace

The following IDs are reserved for later gates only:

~~~text
PROSPECTIVE_RECOVERY_AUTHORIZATION=N3W_T1_F4_STOPPED_RUNTIME_ACCEPTANCE_RECOVERY_LIVE_20261016_01
PROSPECTIVE_SUCCESSOR_ACTIVATION_AUTHORIZATION=N3W_T1_F4_RUNTIME_ACTIVATION_SUCCESSOR_LIVE_20261016_01
PROSPECTIVE_SUCCESSOR_ACCEPTANCE_AUTHORIZATION=N3W_T1_F4_RUNTIME_ACCEPTANCE_SUCCESSOR_LIVE_20261016_01

PROSPECTIVE_RECOVERY_AUTHORIZATION_GRANTED=false
PROSPECTIVE_SUCCESSOR_ACTIVATION_AUTHORIZATION_GRANTED=false
PROSPECTIVE_SUCCESSOR_ACCEPTANCE_AUTHORIZATION_GRANTED=false
~~~

These are not live authorizations. No authorization is claimed or consumed by this preparation gate.

A fresh real-T1 read-only preexecution must prove all three IDs are absent from the current F4 authorization ledger
before the first one can be granted.

## 7. Future staging path

Reserved future staging root:

~~~text
/var/tmp/n3w-t1-f4-recovery-f0bcc2ac50326b9a988405af8a2aad4c51694810
~~~

The read-only preexecution must prove this path is absent before any transfer.

Later transfer must be a separate gate. The prepared transport contract is:

~~~text
LOCAL_ARTIFACT_ZIP_SHA256=7c633170dfcbe2f9587fd51eaa48455505069c21b2c76df48e9d9ef54249b225
LOCAL_CONTROL_TAR_SHA256=9d1ba965ac72887dbac6cc48381d228843c6c489e92217ef65886d73cd0c309d
REMOTE_TRANSFER_TARGET=<reserved-staging>.tar.part
REMOTE_FINAL_TAR=<reserved-staging>.tar
ATOMIC_PUBLICATION_REQUIRED=true
REMOTE_EXTRACT_ONLY_AFTER_TAR_HASH_PASS=true
RECOVERY_EXECUTION_ONLY_AFTER_REMOTE_MANIFEST_AND_LAUNCHER_HASH_PASS=true
~~~

No transfer is performed in this gate.

## 8. Real-T1 read-only preexecution contract

The next live gate is strictly read-only. It must fresh-check:

1. transaction stage exactly `STOPPED_RUNTIME_ACCEPTANCE`;
2. error exactly `manager_mqtt_socket_count_invalid`;
3. rollback proven and rollback error count zero;
4. failed runtime-acceptance authorization claimed/consumed/no-replay;
5. failed source/manifest/installed launcher exactly match the failed exact artifact above;
6. no runtime-acceptance report exists;
7. installed-material bindings still match actual files;
8. Docker runtime query succeeds and has zero running `n3wfc4` services;
9. product listener set is empty;
10. Broker and Services are disabled and in a known non-running active state;
11. certificate timer is disabled/inactive and certificate service inactive;
12. ingress guard remains active;
13. persistence is false;
14. future staging path does not exist;
15. enough free space exists in `/var/tmp`;
16. all three prospective authorizations are distinct from every current/history F4 authorization.

The read-only collector is versioned separately in:

~~~text
docs/development/N3W_T1_F4_STOPPED_RUNTIME_ACCEPTANCE_RECOVERY_LIVE_READONLY_PREEXECUTION_RUNBOOK_20261016.md
~~~

## 9. PASS / FAIL boundary

PASS requires all artifact binding and preparation checks above.

A future real-T1 read-only preexecution PASS does not itself grant the recovery authorization.

Any mismatch in source/manifest/launcher, installed-material binding, authorization history, stopped runtime state,
listener state, systemd state or staging residue is a hard STOP before artifact transfer.

## 10. Stop/status

~~~text
EXACT_SUCCESSOR_ARTIFACT_BINDING=PASS
FAILED_SOURCE_ARTIFACT_RECONSTRUCTION=PASS
LAUNCHER_ONLY_DELTA=PASS
SUCCESSOR_RECOVERY_COMMAND_BINDING=PASS
LIVE_READONLY_PREEXECUTION_PLAN=PREPARED_NOT_EXECUTED

CURRENT_REAL_T1_STAGE=STOPPED_RUNTIME_ACCEPTANCE
ARTIFACT_TRANSFER_TO_T1=false
RECOVERY_AUTHORIZATION_GRANTED=false
LIVE_RUNTIME_MUTATION=false

NEXT_ONE_GATE=N3W_T1_F4_STOPPED_RUNTIME_ACCEPTANCE_RECOVERY_LIVE_READONLY_PREEXECUTION_20261016_01
AUTO_EXECUTE_NEXT_GATE=false
~~~
