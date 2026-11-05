# N3-W T1 Core Updater — Home Assistant P5 live apply preauthorization review

Date: 2026-11-05

## Gate

~~~text
TASK=N3W_T1_CORE_UPDATER_HOMEASSISTANT_P5_LIVE_APPLY_PREAUTHORIZATION_REVIEW_20261105_01
STATE=SOURCE_PREAUTH_PREPARATION

P4_RESULT=CLOSED_PASS
P4_EXECUTION_HEAD=8232707eb2c91d3fa9881e4cadba6b78eefc1494
P4_FINAL_DOCS_PARENT=d6b6d0f89837a85d94d60b4df45ab9eb4000d764

PROPOSED_AUTHORIZATION=N3W_T1_CORE_UPDATER_HOMEASSISTANT_2026_10_4_LIVE_APPLY_P5_20261105_01
AUTHORIZATION_GRANTED=false
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
AUTHORIZATION_REPLAY_PERMITTED=false

T1_ACCESS=false
T1_MUTATION=false
SERVICE_RESTART=false
IMAGE_LOAD=false
UPDATER_APPLY=false
UPDATER_ROLLBACK=false
BOARD_ACCESS=false
MERGE=false
~~~

P5 preparation does not itself grant or consume live authorization.

## Frozen target

~~~text
TARGET_MANIFEST=infra/n3w-t1/upgrades/homeassistant-2026.10.4.json
TARGET_MANIFEST_BLOB_SHA=6966b4fe4d7620ccc436643cc840da9ae95e6010

TARGET_IMAGE=local/n3w-homeassistant:2026.10.4-5881590f
PREDECESSOR_IMAGE=local/n3w-homeassistant:2026.10.0-0c73235a

ARTIFACT_RUN_ID=41976542377
ARTIFACT_ID=13391983948
ARTIFACT_NAME=n3w-t1-core-updater-homeassistant-2026.10.4-arm64-fb7cfc857003ace3d368521d76ca2320ba399736
ARTIFACT_DIGEST_SHA256=df95749cec1e48796d2cf3241d19739601fe7be78c48638284d10eec786e4fd2
ARTIFACT_SOURCE_HEAD=fb7cfc857003ace3d368521d76ca2320ba399736

TARGET_ARCHIVE_SHA256=eba1da958fc9c759c30d1cb34445c364e895bcd8d5e6c0d8392ab6849ece9973
TARGET_ARCHIVE_SIZE_BYTES=835309535
~~~

Fresh GitHub artifact metadata confirmed the artifact remains present and unexpired.

## P4 predecessor authority

P5 refuses to claim authorization unless the fresh live preflight still matches P4:

~~~text
P4_BASELINE_SHA256=78c3b0b58ad39cf887689658bec90c8466d30a93d58830b0289f1463dafad868
P4_TRANSACTION_SHA256=6ad39528f43407c6f48b83a07cb2d4ddfc916e808b3957aae176608c89a98fa3

EXPECTED_RUNTIME_CLASS=TARGET_BOUND_RUNNING
EXPECTED_HEALTH_STATE=HEALTHY
EXPECTED_RECOVERY_REQUIRED=false

EXPECTED_MANAGER=local/greenhouse-manager:fresh-5b32e1ae8210
EXPECTED_HOMEASSISTANT=local/n3w-homeassistant:2026.10.0-0c73235a
EXPECTED_BROKER=local/n3w-mosquitto:2.1.2-3184566d

EXPECTED_MANAGER_BINDING_MODE=dynamic
EXPECTED_HOMEASSISTANT_BINDING_MODE=legacy_static
EXPECTED_BROKER_BINDING_MODE=legacy_static
~~~

A changed baseline or transaction is a STOP before claim.

## Versioned execution package

~~~text
tools/execution_packages/n3w/u2/ha_p5_live_apply/executor.py
tools/execution_packages/n3w/u2/ha_p5_live_apply/remote_live.py
tools/execution_packages/n3w/u2/ha_p5_live_apply/manifest.json
~~~

The Mac-side executor:

1. validates exact local Git head and source bindings;
2. re-reads GitHub artifact metadata;
3. downloads the exact frozen artifact;
4. verifies exact file set, archive size/SHA, upstream binding and portable identity;
5. opens an SSH ControlMaster using a short `/tmp` control path;
6. creates a private temporary T1 staging directory only;
7. stages exact source and exact HA archive;
8. runs fresh read-only preflight;
9. stops before claim on any drift;
10. claims the one-shot authorization only immediately before the single apply invocation;
11. runs at most one updater-owned apply;
12. on apply failure, runs read-only diagnosis and stops;
13. on apply PASS, performs post-apply status/runtime/inspect verification;
14. removes temporary T1 staging material.

## Fresh preflight required before claim

The live preflight must return:

~~~text
STATUS=PASS
RUNTIME_CLASS=TARGET_BOUND_RUNNING
HEALTH_STATE=HEALTHY
RECOVERY_REQUIRED=false

BASELINE_DOUBLE_READ_STABLE=true
BASELINE_SHA256=78c3b0b58ad39cf887689658bec90c8466d30a93d58830b0289f1463dafad868
TRANSACTION_SHA256=6ad39528f43407c6f48b83a07cb2d4ddfc916e808b3957aae176608c89a98fa3

TARGET_IMAGE_PRESTATE=ABSENT
TARGET_ARCHIVE_VERIFIED=true
TEMPLATE_CONVERGENCE_PLANNED=true
ROLLBACK_AVAILABLE=true

AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
~~~

Only after all of these checks pass may an explicitly granted authorization be claimed.

## Single-apply contract

If explicit authorization is later granted:

~~~text
PERMITTED_APPLY_INVOCATIONS=1
SECOND_APPLY_ALLOWED=false
BLIND_EXPLICIT_ROLLBACK_ALLOWED=false
UPDATER_APPLY_CONFIRMATION=T1_CORE_UPDATER_APPLY
~~~

The single updater-owned apply is allowed to:

- load the exact HA 2026.10.4 image;
- converge HA binding `legacy_static -> dynamic`;
- change only the HA image binding;
- stop/start the shared Manager+HA owner as required by the updater transaction;
- verify Manager/Broker peer runtime authority;
- verify A1 hard/soft contracts;
- commit the V2 transaction.

No manual Compose/env edit, transaction edit/delete, second apply, credential/DynSec mutation or board access is allowed.

## Failure boundary

Before apply invocation:

- any preflight failure leaves authorization unclaimed/unconsumed;
- no product mutation is permitted.

After apply invocation begins:

- the authorization is treated as claimed and consumed regardless of PASS/FAIL;
- no second apply is allowed;
- no blind explicit rollback is allowed;
- the executor may only collect read-only `status`, `runtime-state` and `inspect`;
- recovery requires a separate decision/authorization boundary.

The updater's own automatic rollback inside the single apply transaction remains part of the already reviewed generic V2 safety model.

## PASS target

A successful P5 live apply must prove:

~~~text
APPLY_STATUS=PASS
APPLY_TRANSACTION_STATUS=COMMITTED
APPLY_T1_MUTATION=true

POST_RECOVERY_REQUIRED=false
POST_RUNTIME_CLASS=TARGET_BOUND_RUNNING
POST_HEALTH_STATE=HEALTHY

POST_MANAGER=local/greenhouse-manager:fresh-5b32e1ae8210
POST_HOMEASSISTANT=local/n3w-homeassistant:2026.10.4-5881590f
POST_BROKER=local/n3w-mosquitto:2.1.2-3184566d

POST_MANAGER_BINDING_MODE=dynamic
POST_HOMEASSISTANT_BINDING_MODE=dynamic
POST_BROKER_BINDING_MODE=legacy_static

MANAGER_MQTT_AUTHENTICATED=true
HOMEASSISTANT_MQTT_AUTHENTICATED=true
HOMEASSISTANT_HTTP=200_OR_401
LISTENER_CONTRACT=PASS
~~~

P5 apply success is not final Home Assistant product closure. Real explicit rollback proof and final target reapply/acceptance remain later gates.

## Current boundary

~~~text
P5_SOURCE_PREPARATION=IN_PROGRESS
LIVE_HA_APPLY_AUTHORIZED=false
AUTO_EXECUTE_LIVE_APPLY=false
MERGE=false
~~~

After source review and CI closure, the next boundary is an explicit user decision whether to grant:

~~~text
N3W_T1_CORE_UPDATER_HOMEASSISTANT_2026_10_4_LIVE_APPLY_P5_20261105_01
~~~
