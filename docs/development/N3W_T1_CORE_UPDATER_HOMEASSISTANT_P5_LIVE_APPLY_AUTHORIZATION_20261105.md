# N3-W T1 Core Updater — Home Assistant P5 one-shot live apply authorization

Date: 2026-11-05

## Authorization

~~~text
TASK=N3W_T1_CORE_UPDATER_HOMEASSISTANT_P5_LIVE_APPLY_AUTHORIZATION_20261105_01

AUTHORIZATION_ID=N3W_T1_CORE_UPDATER_HOMEASSISTANT_2026_10_4_LIVE_APPLY_P5_20261105_01
AUTHORIZATION_GRANTED=true
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
AUTHORIZATION_REPLAY_PERMITTED=false

PERMITTED_APPLY_INVOCATIONS=1
SECOND_APPLY_ALLOWED=false
BLIND_EXPLICIT_ROLLBACK_ALLOWED=false

ORIGINAL_AUTHORIZED_EXECUTABLE_HEAD=ec8ba4555c022113498625cd06edd0a804ec1ebb
CURRENT_REPAIRED_EXECUTABLE_HEAD=9ab1ddf21dd191c916ef7b0dbe281d03aa8d0a2f
AUTHORIZED_MANIFEST_BLOB_SHA=1772e694e394fe9b2bfa7f041ef288ae09c0746b
LIVE_APPLY_AUTHORIZED=true

MERGE=false
BOARD_ACCESS=false
~~~

The user explicitly granted the one-shot live Home Assistant 2026.10.4 upgrade.
This authorization is scoped only to the frozen P5 target and executor.

## Frozen target

~~~text
TARGET_MANIFEST=infra/n3w-t1/upgrades/homeassistant-2026.10.4.json
TARGET_MANIFEST_BLOB_SHA=6966b4fe4d7620ccc436643cc840da9ae95e6010

PREDECESSOR_IMAGE=local/n3w-homeassistant:2026.10.0-0c73235a
TARGET_IMAGE=local/n3w-homeassistant:2026.10.4-5881590f

TARGET_ARCHIVE_SHA256=eba1da958fc9c759c30d1cb34445c364e895bcd8d5e6c0d8392ab6849ece9973
TARGET_ARCHIVE_SIZE_BYTES=835309535

ARTIFACT_RUN_ID=41976542377
ARTIFACT_ID=13391983948
ARTIFACT_DIGEST_SHA256=df95749cec1e48796d2cf3241d19739601fe7be78c48638284d10eec786e4fd2
ARTIFACT_SOURCE_HEAD=fb7cfc857003ace3d368521d76ca2320ba399736
~~~

No target artifact reproduction or target-manifest mutation is authorized.

## Required pre-claim guards

The executor must stop before claim if any of the following fail:

~~~text
SOURCE_BINDING=EXACT
ARTIFACT_IDENTITY=EXACT
P4_BASELINE_SHA256=78c3b0b58ad39cf887689658bec90c8466d30a93d58830b0289f1463dafad868
P4_TRANSACTION_SHA256=6ad39528f43407c6f48b83a07cb2d4ddfc916e808b3957aae176608c89a98fa3
RUNTIME_CLASS=TARGET_BOUND_RUNNING
HEALTH_STATE=HEALTHY
RECOVERY_REQUIRED=false
TARGET_IMAGE_PRESTATE=ABSENT
TARGET_ARCHIVE_VERIFIED=true
TEMPLATE_CONVERGENCE_PLANNED=true
ROLLBACK_AVAILABLE=true
~~~

The exact archive is downloaded and verified on the Mac before T1 staging.

## Capacity authority

~~~text
STORAGE_POLICY=infra/n3w-t1/upgrades/homeassistant-2026.10.4-storage-policy.json
STORAGE_POLICY_BLOB_SHA=01a5cec8877e2837504ed798e91ca552ab6f2a0e

HISTORICAL_FIXED_5_GIB_P5_RESERVE=RETIRED
P5_POST_PEAK_RESERVE_BYTES=1610612736
~~~

Before staging, P5 dynamically requires:

~~~text
FREE_BYTES
>=
EXACT_TARGET_ARCHIVE_BYTES
+ EXACT_DOCKER_SAVE_UNCOMPRESSED_MEMBER_BYTES
+ 1610612736
~~~

After successful apply and temporary-staging cleanup:

~~~text
POST_CLEANUP_FREE_BYTES >= 1610612736
~~~

The predecessor HA image is already resident and retained for rollback and is not
double-counted.

## Mutation boundary

Only after all preflight checks pass may the executor write the private local
authorization claim and invoke exactly one updater-owned apply.

Once the apply invocation begins:

~~~text
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
AUTHORIZATION_REPLAY_PERMITTED=false
~~~

Consumption applies regardless of apply PASS or FAIL.

The authorized apply may:

- load the exact HA 2026.10.4 image;
- converge Home Assistant binding from legacy_static to dynamic;
- stop/start the updater-owned Manager+HA service owner as required by Generic V2;
- commit the Generic V2 transaction after post verification.

It may not:

- run a second apply;
- invoke explicit rollback from the P5 executor;
- manually edit/delete updater transaction state;
- modify credentials or DynSec;
- modify Broker or Manager image bindings;
- access boards;
- merge PRs.

The Generic V2 transaction's internal automatic rollback remains the reviewed
failure-safety mechanism if the single apply fails after mutation begins.

## Success target

~~~text
APPLY_STATUS=PASS
APPLY_TRANSACTION_STATUS=COMMITTED
APPLY_T1_MUTATION=true

POST_RUNTIME_CLASS=TARGET_BOUND_RUNNING
POST_HEALTH_STATE=HEALTHY
POST_RECOVERY_REQUIRED=false

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
POST_CLEANUP_RESERVE_PASS=true
~~~

## Attempt 01 and repaired execution hold

Attempt 01 stopped in staging transport before preflight:

~~~text
ATTEMPT_01_RESULT=STOP_BEFORE_PREFLIGHT
ATTEMPT_01_REASON=command_failed:scp:1
ATTEMPT_01_APPLY_INVOKED=false
ATTEMPT_01_AUTHORIZATION_CLAIMED=false
ATTEMPT_01_AUTHORIZATION_CONSUMED=false
ATTEMPT_01_T1_MUTATION=false
~~~

Because the authorization was not claimed or consumed, the same one-shot user
authorization remains valid for one repaired retry.

The repaired executable removes the dedicated scp path and streams staging files
over the already-established SSH transport. The repaired exact executable head
must pass CI before retry.

~~~text
EXECUTION_READY=false
WAIT_FOR_REPAIRED_EXACT_HEAD_CI=true
AUTO_RETRY=false
~~~

Authority for the STOP and repair:
`docs/development/N3W_T1_CORE_UPDATER_HOMEASSISTANT_P5_LIVE_APPLY_ATTEMPT01_TRANSPORT_STOP_REPAIR_20261105.md`.
