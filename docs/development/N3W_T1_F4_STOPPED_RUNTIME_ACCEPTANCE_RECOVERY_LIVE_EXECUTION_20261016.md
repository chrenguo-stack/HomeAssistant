# N3-W T1 F4 Stopped Runtime Acceptance Recovery — Live Execution

Date: 2026-10-16

~~~text
TASK=N3W_T1_F4_STOPPED_RUNTIME_ACCEPTANCE_RECOVERY_LIVE_EXECUTION_20261016_01
STATUS=AUTHORIZED_NOT_EXECUTED

PREDECESSOR_GATE=N3W_T1_F4_STOPPED_RUNTIME_ACCEPTANCE_RECOVERY_EXACT_ARTIFACT_STAGING_PREEXECUTION_20261016_01
PREDECESSOR_RESULT=CLOSED_PASS

SOURCE_HEAD=f0bcc2ac50326b9a988405af8a2aad4c51694810
PACKAGE_MANIFEST_SHA256=37c620daf57a3f49614a4c2824c55b7e20413ef63593cd1781e4f359fb4729b5
STAGED_LAUNCHER_SHA256=eaf28175909479007d6d1df7522811d032890dcaa2a2280228c93e6dce128bb3
INSTALLED_OLD_LAUNCHER_SHA256=f7f742505f439675fb19ecf8f98b8235703d6e2a1c5c9217ecfe01a025be3c8b
PRE_EXECUTION_TRANSACTION_SHA256=805fb27f44d36d7e512260373be7dbb8058164d3ea4ce4c1d13659169062dbcf

PACKAGE_ROOT=/var/tmp/n3w-t1-f4-recovery-f0bcc2ac50326b9a988405af8a2aad4c51694810
PACKAGE_ENTRYPOINT=/var/tmp/n3w-t1-f4-recovery-f0bcc2ac50326b9a988405af8a2aad4c51694810/tools/n3w_t1_f4_activation_host.py

RECOVERY_AUTHORIZATION_ID=N3W_T1_F4_STOPPED_RUNTIME_ACCEPTANCE_RECOVERY_LIVE_20261016_01
RECOVERY_AUTHORIZATION_GRANTED=true
RECOVERY_AUTHORIZATION_CLAIMED=false
RECOVERY_AUTHORIZATION_CONSUMED=false
RECOVERY_AUTHORIZATION_REPLAY_ALLOWED=false

TARGET_TRANSITION=STOPPED_RUNTIME_ACCEPTANCE_TO_PREPARED
SUCCESSOR_ACTIVATION=false
SUCCESSOR_RUNTIME_ACCEPTANCE=false
PERSISTENCE=false
CERTIFICATE_TIMER=false
BOARD_ACCESS=false
REBOOT=false
MERGE=false
~~~

## Authority

The user explicitly authorized this next live recovery gate after exact artifact staging CLOSED_PASS.

This grant applies only to the single one-shot recovery authorization ID above. It does not grant successor activation,
successor runtime acceptance, persistence, certificate lifecycle, reboot or board access.

## Exact recovery command contract

The only mutating product command authorized in this gate is:

~~~text
python3 <exact staged launcher>
  repair-stopped-runtime-acceptance
  --confirm "RECOVER F4 STOPPED RUNTIME ACCEPTANCE: YES"
  --authorization-id N3W_T1_F4_STOPPED_RUNTIME_ACCEPTANCE_RECOVERY_LIVE_20261016_01
  --package-root <exact staged package root>
  --package-manifest-sha256 37c620daf57a3f49614a4c2824c55b7e20413ef63593cd1781e4f359fb4729b5
  --package-source-head f0bcc2ac50326b9a988405af8a2aad4c51694810
~~~

The staged launcher must be invoked through `python3`; the staged file is not treated as an installed executable.

## Expected PASS transition

On PASS:

~~~text
stage=PREPARED
package_source_head=f0bcc2ac50326b9a988405af8a2aad4c51694810
package_manifest_sha256=37c620daf57a3f49614a4c2824c55b7e20413ef63593cd1781e4f359fb4729b5

installed_launcher_sha256=eaf28175909479007d6d1df7522811d032890dcaa2a2280228c93e6dce128bb3
installed_launcher_size=177919
installed_launcher_mode=0755

runtime_acceptance_recovery_passed=true
runtime_acceptance_recovery_authorization_claimed=true
runtime_acceptance_recovery_authorization_consumed=true
runtime_acceptance_recovery_authorization_replay_allowed=false

failed_runtime_acceptance_authorization_id=N3W_T1_F4_RUNTIME_ACCEPTANCE_LIVE_20261015_01
failed_runtime_acceptance_authorization_preserved=true

activation_retry_eligible=true
runtime_acceptance_retry_eligible=true

running_services=[]
product_listener_ports=[]
production_service_start=false
persistence_enabled=false
certificate_timer_enabled=false
~~~

## Failure boundary

The authorization is one-shot.

If the recovery command reaches the claim point, the authorization becomes consumed/no-replay even if the command later
fails. The operator must not rerun the command with the same authorization ID.

Any non-PASS output therefore hard-stops the gate for forensic review.

## Stop after PASS

Even after PASS:

~~~text
SUCCESSOR_ACTIVATION_AUTHORIZATION_GRANTED=false
SUCCESSOR_RUNTIME_ACCEPTANCE_AUTHORIZATION_GRANTED=false
PRODUCTION_SERVICE_START=false

NEXT_ONE_GATE=N3W_T1_F4_STOPPED_RUNTIME_ACCEPTANCE_RECOVERY_POSTEXECUTION_READONLY_CLOSURE_20261016_01
AUTO_EXECUTE_NEXT_GATE=true
~~~

The next substep is read-only postexecution closure. It does not start the product runtime.
