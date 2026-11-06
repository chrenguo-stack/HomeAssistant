# 温室环境监测系统（ESP32-C6） / N3-W / T1 Core Updater
# Home Assistant P4 fresh read-only premutation baseline CLOSED_PASS
# Closure — 2026-11-05

## 1. Closure

~~~text
=== N3W_T1_CORE_UPDATER_HOMEASSISTANT_P4_FRESH_READONLY_PREMUTATION_BASELINE_20261105_01 CLOSURE ===

P4_EXECUTION_HEAD=8232707eb2c91d3fa9881e4cadba6b78eefc1494
P3_EXECUTABLE_SOURCE_HEAD=b4409c11beda99f2aef43353b8129003760634b7
P3_FINAL_DOCS_ALIGNMENT_HEAD=bb845f5cca4f2fc3e4710d14b6176a043d2a4523

PR786=OPEN_DRAFT
PR786_MERGEABLE=true
MERGE=false

TARGET_MANIFEST=infra/n3w-t1/upgrades/homeassistant-2026.10.4.json
TARGET_MANIFEST_BLOB_SHA=6966b4fe4d7620ccc436643cc840da9ae95e6010
TARGET_ARTIFACT_ID=13391983948
TARGET_ARCHIVE_SHA256=eba1da958fc9c759c30d1cb34445c364e895bcd8d5e6c0d8392ab6849ece9973
TARGET_IMAGE=local/n3w-homeassistant:2026.10.4-5881590f
PREDECESSOR_IMAGE=local/n3w-homeassistant:2026.10.0-0c73235a

P4_CI=13_OF_13_SUCCESS
P4_REAL_T1_ATTEMPT_1=STOP_TRANSPORT_ONLY
P4_REAL_T1_ATTEMPT_1_MUTATION=false
P4_REAL_T1_ATTEMPT_2=PASS

RUNTIME_CLASS=TARGET_BOUND_RUNNING
HEALTH_STATE=HEALTHY
RECOVERY_REQUIRED=false

MANAGER_BINDING=local/greenhouse-manager:fresh-5b32e1ae8210
HOMEASSISTANT_BINDING=local/n3w-homeassistant:2026.10.0-0c73235a
BROKER_BINDING=local/n3w-mosquitto:2.1.2-3184566d

MANAGER_BINDING_MODE=dynamic
HOMEASSISTANT_BINDING_MODE=legacy_static
BROKER_BINDING_MODE=legacy_static

BASELINE_DOUBLE_READ_STABLE=true
BASELINE_SHA256=78c3b0b58ad39cf887689658bec90c8466d30a93d58830b0289f1463dafad868
PLAN_SHA256=6137cb33f290113610a4f0db0021cb0a99b3c5e9aa62d2fce94a0d3c53a48d32
TRANSACTION_SHA256=6ad39528f43407c6f48b83a07cb2d4ddfc916e808b3957aae176608c89a98fa3
PRODUCT_SNAPSHOT_SHA256=b79e50d176cd1377cef5ebe34173b20043f7cce9cc08e21071049a6b14d1e4f8
STATE_SNAPSHOT_SHA256=ced70dfa0bc357e7427a7d4e3ee0aba35dffc7c3910f89ffff59a33243e06ce1
SERVICE_SNAPSHOT_SHA256=f72036f48bf7fcfad4d9d6edd1842d728c057befee20cbc866f6abb111decbd3

TARGET_IMAGE_PRESTATE=ABSENT
TARGET_ARCHIVE_VERIFIED=false
TEMPLATE_CONVERGENCE_PLANNED=true
ROLLBACK_AVAILABLE=true
READONLY_STATE_STABLE=true

T1_ACCESS=true
T1_MUTATION=false
PERSISTENT_T1_FILE_WRITE=false
TEMPORARY_SCRATCH_WRITE=true
SERVICE_RESTART=false
IMAGE_LOAD=false
UPDATER_APPLY=false
UPDATER_ROLLBACK=false
BOARD_ACCESS=false

P4_RESULT=CLOSED_PASS
LIVE_HA_APPLY_AUTHORIZED=false
NEXT_ONE_GATE=N3W_T1_CORE_UPDATER_HOMEASSISTANT_P5_LIVE_APPLY_PREAUTHORIZATION_REVIEW_20261105_01
AUTO_EXECUTE_NEXT_GATE=false
STOP=true

=== END ===
~~~

## 2. First execution attempt disposition

The first real-T1 P4 attempt used exact source head
`cf189435118b56efaa718c391526f067355c8ff7` and stopped with
`remote_report_json_invalid`.

Independent source review proved the STOP was in the execution-package transport layer:
the remote runner handed non-seekable SSH stdin directly to
`tarfile.open(..., mode="r:*")`. The remote probe had not started, no product
path was written, no service was restarted, no image was loaded, and no updater
apply or rollback was invoked.

The bounded repair:

- buffers the small source bundle under a 4 MiB hard limit;
- parses the buffered bytes through `io.BytesIO`;
- preserves path/symlink validation;
- returns structured STOP JSON for remote-runner failures;
- adds a regression test using pipe-backed stdin.

Repair/execution head:
`8232707eb2c91d3fa9881e4cadba6b78eefc1494`.

All 13 workflows observed on that exact head completed SUCCESS.

## 3. Successful real-T1 evidence

The second execution used exact source head
`8232707eb2c91d3fa9881e4cadba6b78eefc1494`.

The executor returned `PASS` with:

- `TARGET_BOUND_RUNNING / HEALTHY`;
- `recovery_required=false`;
- Manager B unchanged and dynamic;
- Home Assistant predecessor unchanged and legacy-static;
- Broker unchanged and legacy-static;
- two consecutive baseline captures byte-stable;
- product files unchanged;
- updater transaction/state tree unchanged;
- service activation/restart state unchanged;
- frozen target image absent on T1;
- read-only plan included updater-owned Home Assistant template convergence;
- rollback remained available.

The operator-local private evidence root is:

~~~text
/tmp/n3w-ha-p4-evidence-20261105-02-67116
~~~

Raw private evidence is intentionally not committed to the public repository.

## 4. Meaning of P4 PASS

P4 proves that immediately before any Home Assistant live mutation:

1. the accepted real T1 is healthy and not in recovery;
2. the current Manager/HA/Broker image bindings match repository authority;
3. the current Home Assistant binding is the expected `legacy_static` predecessor;
4. the generic V2 updater can construct a valid HA 2026.10.4 read-only plan;
5. the planned transaction includes runtime-template convergence;
6. no target image is already present on T1;
7. no read-only operation altered updater state, product files or service state.

P4 does **not** authorize live apply. It also does not claim the target archive
was verified on the T1; `target_archive_verified=false` is expected because
P4 intentionally did not stage the 835 MB exact image archive.

## 5. Next boundary

The next gate is a repository/source-only preauthorization review:

~~~text
NEXT_ONE_GATE=N3W_T1_CORE_UPDATER_HOMEASSISTANT_P5_LIVE_APPLY_PREAUTHORIZATION_REVIEW_20261105_01
LIVE_HA_APPLY_AUTHORIZED=false
~~~

P5 must prepare a single-use live executor that:

- re-downloads and verifies frozen artifact ID `13391983948`;
- re-captures a fresh baseline and requires it to match the P4 baseline authority;
- stages only temporary exact source/artifact material;
- performs an archive-verified read-only plan before authorization claim;
- claims a fresh one-shot authorization only immediately before the single updater-owned apply;
- allows no second apply and no blind explicit rollback after failure;
- preserves Manager and Broker peer authority;
- stops at a separate recovery decision boundary on any apply failure.

No live Home Assistant mutation is authorized by this closure.
