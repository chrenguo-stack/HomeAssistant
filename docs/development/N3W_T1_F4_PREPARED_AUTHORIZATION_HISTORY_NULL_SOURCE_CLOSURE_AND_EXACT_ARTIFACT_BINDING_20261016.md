# N3-W T1 F4 Prepared Authorization History Null — Source Closure and Exact Artifact Binding

Date: 2026-10-16

~~~text
TASK=N3W_T1_F4_PREPARED_AUTHORIZATION_HISTORY_NULL_SOURCE_CLOSURE_AND_EXACT_ARTIFACT_BINDING_20261016_01
RESULT=CLOSED_PASS

SOURCE_PR=579
SOURCE_HEAD=72b796671e25c30f0d154788e2a4374f030eb7d1
SOURCE_BASE=f0bcc2ac50326b9a988405af8a2aad4c51694810
SOURCE_CI=13_OF_13_PASS

REAL_T1_STAGE=PREPARED
REAL_T1_TRANSACTION_SHA256=bd1e69c2bce2291e835e8bd341434ad889fbdae8630d9bf897a7fdb27dade1ad
REAL_T1_RUNTIME_ACCEPTANCE_AUTHORIZATION_HISTORY=null

LIVE_T1_MUTATION=false
SUCCESSOR_ACTIVATION_AUTHORIZATION_GRANTED=false
SUCCESSOR_RUNTIME_ACCEPTANCE_AUTHORIZATION_GRANTED=false
~~~

## 1. Source closure

Final source head:

~~~text
72b796671e25c30f0d154788e2a4374f030eb7d1
~~~

All 13 relevant CI workflows completed successfully, including:

~~~text
N3W T1 F4 activation source CI=PASS
N3W T1 F4 exact control package=PASS
Public repository safety CI=PASS
greenhouse-manager CI=PASS
M0 vertical slice CI=PASS
M2 private Mosquitto CI=PASS
M2 Dynamic Security CI=PASS
M2 node auth board lab CI=PASS
M2 node auth native board lab CI=PASS
M2 node auth isolated lab CI=PASS
M2 manager runtime secret ownership CI=PASS
H3 N2 Stage2B3 Pairing Runtime CI=PASS
C-07 node retirement CI=PASS
~~~

The final source repair keeps the generic malformed-history checks fail-closed and adds a dedicated exact-bound
`repair-prepared-authorization-history` path for the known durable PREPARED incident where
`runtime_acceptance_authorization_history` is exactly null.

The final reviewed path:

- requires exact current PREPARED source/manifest/launcher binding;
- requires exact preserved failed runtime-acceptance evidence;
- requires recovery authorization claimed/consumed/no-replay and recovery PASS;
- requires both retry-eligible flags true;
- requires runtime stopped and listeners empty;
- requires dedicated repair authorization fields pristine;
- checks the new repair ID against every still-readable prior F4 authorization;
- consumes the repair authorization before launcher replacement;
- allows only the launcher to differ in the successor package;
- normalizes only `runtime_acceptance_authorization_history: null -> []`;
- returns to PREPARED;
- adds the repair authorization ID to future global prior-authorization checks.

The source closure includes the review correction that binds
`runtime_acceptance_last_failure_source_head` and
`runtime_acceptance_last_failure_manifest_sha256` to the original failed acceptance source, not the recovered
PREPARED source.

## 2. Exact artifact authority

~~~text
WORKFLOW=N3W T1 F4 exact control package
WORKFLOW_RUN_ID=38836895174
ARTIFACT_ID=12019940824
ARTIFACT_NAME=n3w-t1-f4-control-package-72b796671e25c30f0d154788e2a4374f030eb7d1
ARTIFACT_EXPIRED=false
ARTIFACT_API_SIZE_BYTES=40853

GITHUB_ARTIFACT_DIGEST_SHA256=3ffdd68a97f43bc5922a7309e9697f94b3e65817d0034f4f0ea91e0f0215cfd1
INDEPENDENT_DOWNLOADED_ZIP_SHA256=3ffdd68a97f43bc5922a7309e9697f94b3e65817d0034f4f0ea91e0f0215cfd1
ARTIFACT_ZIP_DIGEST_MATCH=PASS
~~~

Artifact ZIP contains exactly:

~~~text
build-report.json
n3w-t1-f4-control-package.tar
n3w-t1-f4-control-package.tar.sha256
~~~

## 3. Exact control package

~~~text
CONTROL_TAR_SHA256=4a3126a5267f1ec5e6fca7c98c8b5da7013731ca46d69013beff2ab67f995e86
CONTROL_TAR_SIZE_BYTES=256000
CONTROL_TAR_SIDECAR_MATCH=PASS

BUILD_REPORT_STATUS=PASS
BUILD_REPORT_SOURCE_HEAD=72b796671e25c30f0d154788e2a4374f030eb7d1
BUILD_REPORT_MANIFEST_SHA256=b609642342f7fa9de72b14d02d746ad70e819634ca868d0cae246a58e9d73695
BUILD_REPORT_FILE_COUNT=8
BUILD_REPORT_BOARD_ACCESS=false
BUILD_REPORT_PRODUCTION_SERVICE_START=false
BUILD_REPORT_SECRET_VALUES_INCLUDED=false
~~~

Package manifest:

~~~text
SCHEMA=gh.n3w-t1-f4-activation-package/1
SOURCE_HEAD=72b796671e25c30f0d154788e2a4374f030eb7d1
MANIFEST_SHA256=b609642342f7fa9de72b14d02d746ad70e819634ca868d0cae246a58e9d73695
FILE_COUNT=8
BOARD_ACCESS=false
PRODUCTION_SERVICE_START=false
SECRET_VALUES_INCLUDED=false
~~~

Successor launcher:

~~~text
PATH=tools/n3w_t1_f4_activation_host.py
SHA256=d4bb8e4b91061e6ebf489806956728964a04c9b3909cffea9dd326e30d32d43b
SIZE=195883
TAR_MODE=0644
INSTALLED_TARGET_MODE=0755
COMMAND_PRESENT=repair-prepared-authorization-history
CONFIRMATION_PRESENT=REPAIR F4 PREPARED AUTHORIZATION HISTORY: YES
~~~

## 4. Package delta against currently installed recovered source package

Current recovered package authority:

~~~text
FROM_SOURCE_HEAD=f0bcc2ac50326b9a988405af8a2aad4c51694810
FROM_MANIFEST_SHA256=37c620daf57a3f49614a4c2824c55b7e20413ef63593cd1781e4f359fb4729b5
FROM_LAUNCHER_SHA256=eaf28175909479007d6d1df7522811d032890dcaa2a2280228c93e6dce128bb3
FROM_LAUNCHER_SIZE=177919
FROM_CONTROL_TAR_SHA256=9d1ba965ac72887dbac6cc48381d228843c6c489e92217ef65886d73cd0c309d
~~~

Independent package comparison:

~~~text
PACKAGE_PATH_SET_EQUAL=true
PACKAGE_FILE_COUNT=8
NON_LAUNCHER_FILE_COUNT=7
NON_LAUNCHER_BYTE_IDENTITY=PASS

ONLY_CHANGED_FILE=tools/n3w_t1_f4_activation_host.py
OLD_LAUNCHER_SHA256=eaf28175909479007d6d1df7522811d032890dcaa2a2280228c93e6dce128bb3
OLD_LAUNCHER_SIZE=177919
NEW_LAUNCHER_SHA256=d4bb8e4b91061e6ebf489806956728964a04c9b3909cffea9dd326e30d32d43b
NEW_LAUNCHER_SIZE=195883

ALLOWED_DELTA=LAUNCHER_ONLY
ALLOWED_DELTA_RESULT=PASS
~~~

Therefore the new exact package satisfies the dedicated repair path's launcher-only successor package contract at the
source/artifact level.

## 5. Superseded artifact

The earlier candidate artifact built from source head
`45e61839b31cc5b6e8d8f3b76d55dfdcf136f385` is superseded and must not be used for live repair.

Only the exact artifact bound above is eligible for the next staging gate.

## 6. Next ONE Gate

~~~text
NEXT_ONE_GATE=N3W_T1_F4_PREPARED_AUTHORIZATION_HISTORY_NULL_EXACT_ARTIFACT_STAGING_PREEXECUTION_20261016_01

NEXT_GATE_TARGET=STAGE_NEW_EXACT_PACKAGE_ONLY
NEXT_GATE_RECOVERY_HISTORY_REPAIR_EXECUTION=false
NEXT_GATE_REPAIR_AUTHORIZATION_GRANTED=false
NEXT_GATE_SUCCESSOR_ACTIVATION=false
NEXT_GATE_SUCCESSOR_RUNTIME_ACCEPTANCE=false

NEW_EXPLICIT_T1_STAGING_AUTHORIZATION_REQUIRED=true
AUTO_EXECUTE_NEXT_GATE=false
~~~

The next gate may transfer and bind this exact successor package to a new dedicated T1 staging path while preserving
the current PREPARED transaction and stopped runtime. It must stop before
`repair-prepared-authorization-history` is executed.
