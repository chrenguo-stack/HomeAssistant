## 2026-10-16 Stage A closure

~~~text
STAGE_A_RESULT=PASS
LOCAL_EXACT_PACKAGE=PASS

REAL_T1_STAGE=PREPARED
REAL_T1_TRANSACTION_SHA256=bd1e69c2bce2291e835e8bd341434ad889fbdae8630d9bf897a7fdb27dade1ad
REAL_T1_RUNTIME_ACCEPTANCE_AUTHORIZATION_HISTORY=null

INSTALLED_LAUNCHER_SHA256=eaf28175909479007d6d1df7522811d032890dcaa2a2280228c93e6dce128bb3
INSTALLED_MATERIAL_BINDING_PASS=true

RECOVERY_AUTHORIZATION_CLAIMED=true
RECOVERY_AUTHORIZATION_CONSUMED=true
RECOVERY_AUTHORIZATION_REPLAY_ALLOWED=false

ACTIVATION_RETRY_ELIGIBLE=true
RUNTIME_ACCEPTANCE_RETRY_ELIGIBLE=true

REPAIR_AUTHORIZATION_ID=null
REPAIR_AUTHORIZATION_CLAIMED=null
REPAIR_AUTHORIZATION_CONSUMED=null
REPAIR_AUTHORIZATION_REPLAY_ALLOWED=null
PROSPECTIVE_REPAIR_AUTHORIZATION_COLLISION=false

RUNNING_SERVICES=[]
PRODUCT_LISTENER_PORTS=[]
BROKER_ENABLED=disabled
SERVICES_ENABLED=disabled
CERTIFICATE_TIMER_ENABLED=disabled
RUNTIME_ACCEPTANCE_REPORT_PRESENT=false

ALL_NEW_STAGING_PATHS_ABSENT=true
VAR_TMP_FREE_BYTES=6245912576
CAPACITY_PASS=true

ARTIFACT_TRANSFER_TO_T1=false
REPAIR_AUTHORIZATION_GRANTED=false
LIVE_RUNTIME_MUTATION=false
~~~

Stage A satisfies all frozen preconditions. Stage B is eligible inside the same staging gate and remains limited to
the dedicated new staging paths. It must stop before the history-repair command.

# N3-W T1 F4 Prepared Authorization History Null — Exact Artifact Staging Preexecution

Date: 2026-10-16

~~~text
TASK=N3W_T1_F4_PREPARED_AUTHORIZATION_HISTORY_NULL_EXACT_ARTIFACT_STAGING_PREEXECUTION_20261016_01
STATUS=PREPARED_AWAITING_STAGE_A

SOURCE_HEAD=72b796671e25c30f0d154788e2a4374f030eb7d1
ARTIFACT_ID=12019940824
ARTIFACT_NAME=n3w-t1-f4-control-package-72b796671e25c30f0d154788e2a4374f030eb7d1

CONTROL_TAR_SHA256=4a3126a5267f1ec5e6fca7c98c8b5da7013731ca46d69013beff2ab67f995e86
CONTROL_TAR_SIZE=256000
MANIFEST_SHA256=b609642342f7fa9de72b14d02d746ad70e819634ca868d0cae246a58e9d73695
LAUNCHER_SHA256=d4bb8e4b91061e6ebf489806956728964a04c9b3909cffea9dd326e30d32d43b
LAUNCHER_SIZE=195883

EXPECTED_TRANSACTION_SHA256=bd1e69c2bce2291e835e8bd341434ad889fbdae8630d9bf897a7fdb27dade1ad
EXPECTED_STAGE=PREPARED
EXPECTED_CURRENT_LAUNCHER_SHA256=eaf28175909479007d6d1df7522811d032890dcaa2a2280228c93e6dce128bb3
EXPECTED_RUNTIME_ACCEPTANCE_AUTHORIZATION_HISTORY=null

PROSPECTIVE_REPAIR_AUTHORIZATION_ID=N3W_T1_F4_PREPARED_AUTHORIZATION_HISTORY_REPAIR_LIVE_20261016_01
PROSPECTIVE_REPAIR_AUTHORIZATION_GRANTED=false

STAGING_ROOT=/var/tmp/n3w-t1-f4-prepared-history-repair-72b796671e25c30f0d154788e2a4374f030eb7d1
STAGING_TAR=/var/tmp/n3w-t1-f4-prepared-history-repair-72b796671e25c30f0d154788e2a4374f030eb7d1.tar
STAGING_TAR_PART=/var/tmp/n3w-t1-f4-prepared-history-repair-72b796671e25c30f0d154788e2a4374f030eb7d1.tar.part
STAGING_EXTRACT_PART=/var/tmp/n3w-t1-f4-prepared-history-repair-72b796671e25c30f0d154788e2a4374f030eb7d1.extract.part

STAGE_A_T1_MUTATION=false
STAGE_B_T1_FILESYSTEM_STAGING_ONLY=true
REPAIR_COMMAND_EXECUTION=false
SUCCESSOR_ACTIVATION=false
SUCCESSOR_RUNTIME_ACCEPTANCE=false
~~~

## Stage A

Stage A is read-only on T1. It must freshly download the exact artifact on the Mac, re-hash tar/manifest/launcher, and
prove the T1 has not drifted:

- transaction SHA remains exact;
- stage remains PREPARED;
- installed launcher is still the recovered launcher;
- installed material binding remains valid;
- runtime-acceptance history remains exactly null;
- recovery authorization remains consumed/no-replay;
- activation/runtime-acceptance retry flags remain true;
- product runtime/listeners remain stopped;
- Broker/Services/certificate timer remain disabled;
- no runtime-acceptance report exists;
- all four new dedicated staging paths are absent;
- the prospective repair authorization ID does not collide with any readable current/history authorization ID;
- enough /var/tmp free space exists.

STOP after Stage A.

## Stage B

Only after reviewed Stage A PASS, Stage B may transfer the exact tar into the dedicated new staging paths, verify it,
extract it, validate all package files, and atomically publish the staging root.

Stage B must not execute `repair-prepared-authorization-history`, replace the installed launcher, edit the transaction,
start product services, or grant/consume the repair authorization.

## Hard stop

~~~text
REPAIR_AUTHORIZATION_GRANTED=false
REPAIR_COMMAND_EXECUTED=false
AUTO_EXECUTE_REPAIR=false
~~~
