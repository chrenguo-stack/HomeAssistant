# N3-W T1 OTA V1.3 R8V13-07 U10 terminal recovery health closure

Date: 2026-11-25

## Scope

This record closes the failed R8V13-07 transaction recovery only. It does not claim a fresh R8V13-07 acceptance PASS and it does not enter R8V13-08.

## Existing transaction identity

```text
TRANSACTION_ID=d86669e6d16bb9420191920bc2b02583e7f7207eff0b51ed3f9e6321f99389d4
AUTHORIZATION_ID_SHA256=6976d68fd1b6828b630fd05751c2855afd84efc65639753f1a318189fff62f50
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
INSTALL_REPLAY=false
SECOND_TRANSACTION=false
```

The original INSTALL authority was never replayed. Recovery remained bound to the same consumed-authorization transaction.

## Live repair and durable recovery outcome

The repaired recovery pyz was published successfully:

```text
LIVE_RECOVERY_PYZ_SHA256=d7915bc3e42531a829ab22ecb74a7148878c3a2310313e4f1ac07acc8785185e
```

After the live patch crossed the recovery-start boundary, the durable retry owner continued the same transaction. Intermediate recovery states included protected-data evidence pending and monitoring evidence pending before terminal rollback.

Terminal transaction:

```text
TX_STATUS=ROLLED_BACK
TX_PHASE=U13B_ROLLED_BACK
TX_FAILURE_CODE=null
TX_RECOVERY_REQUIRED=false
TX_TARGET_RELEASE_STEP=RELEASED
```

Recovered predecessor runtime:

```text
HOMEASSISTANT=local/n3w-homeassistant:2026.10.4-5881590f
HOMEASSISTANT_ID=sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365
TARGET_2026_10_0_PRESENT=false
APPLICATION_OWNER_STATE=active
BROKER_OWNER_STATE=active
IPC_SOCKET_STATE=active
```

## Final physical health verification

The bounded final health command returned:

```text
TERMINAL_TRANSACTION=PASS
RECOVERED_ENV=PASS
RECOVERED_RUNTIME_HEALTH=PASS
RETRY_TIMER_STATE=active
INSTALL_REPLAY=false
SECOND_TRANSACTION=false
RESULT=R8V13_07_U10_TERMINAL_RECOVERY_HEALTH_PASS
```

Therefore the failed R8V13-07 transaction is safely closed as terminal rollback and the T1 is back on the frozen predecessor runtime with the normal recovery timer armed.

## Newly observed false-failure semantics

The recovery path exposed one additional status-classification defect:

`ha_usb_rollback_protected_data_evidence_pending` was a recoverable evidence-wait condition but was represented as a generic error, causing the retry oneshot to exit nonzero and systemd to mark the service failed.

Source repair:

```text
SOURCE_FIX_COMMIT=5fb25e4e19346564ec502531482cea67b5d5da2a
TEST_FIX_HEAD=fb722dcacffb255c0f34455b362748ae64d39072
NEW_PENDING_STATUS=RECOVERY_PROTECTED_DATA_EVIDENCE_PENDING
EXPECTED_EXIT_CODE=0
```

The source repair does not weaken rollback health requirements. It changes only the classification of this known recoverable pending state.

The R8 focused workflow for this head completed SUCCESS, but its selected product-recovery subset does not directly select the newly extended boot-recovery test. The full Home Assistant target-binding CI is the required source closure because it runs the complete `test_n3w_t1_core_updater_ha_usb_r2.py` suite and builds a new recovery installation artifact.

## Next boundary

```text
R8V13_07_FAILED_TRANSACTION_RECOVERY=CLOSED_PASS
R8V13_07_FRESH_ACCEPTANCE=NOT_RUN_YET
R8V13_08_BLOCKED=true
BROKER_OTA=DEFERRED
HOST_REBOOT=false
USB_FORMAT_DELETE=false
MERGE=false
RELEASE=false
```

Before a fresh R8V13-07 acceptance starts:

1. complete the full HA target-binding CI for the protected-data pending classification repair;
2. bind the newly built recovery artifact to the exact source head;
3. update/deploy that recovery artifact if required by the fresh-acceptance preflight;
4. create and validate a fresh transaction/authority chain;
5. stop before R8V13-08 until fresh R8V13-07 itself passes.


## Protected-data pending source/artifact closure

The status-classification repair completed the full Home Assistant target-binding workflow on the exact source-bearing PR lineage:

```text
HA_TARGET_BINDING_CI_RUN=45522904136
HA_TARGET_BINDING_CI=SUCCESS
HA_SOURCE_TESTS=330_PASSED_1_SKIPPED
DOCKER_RELEASE_INTEGRATION=1_PASSED
```

The workflow built a new exact recovery installation candidate. Independent download/readback of the artifact ZIP confirmed:

```text
RECOVERY_ARTIFACT_SOURCE_HEAD=07eefc1e6d87eff464133771191d155fa9ee9d3d
RECOVERY_ARTIFACT_ID=14980338287
RECOVERY_ARTIFACT_DIGEST_SHA256=d47d3fc4183805e63431c105682fbd93ed1cdc56b5fdc8681f41277afcd14ed1
RECOVERY_MANIFEST_SHA256=c3071a9dcc2a5e54ca6017cfb58d1afad8d715cc47ca0640ae22493472430838
RECOVERY_PYZ_SHA256=9d69992a72c3b8dd60f33ebcf00ac7c8fcf88e255c7fadb8878d15aa86f10ffa
MANIFEST_SOURCE_HEAD=07eefc1e6d87eff464133771191d155fa9ee9d3d
ARTIFACT_SOURCE_BINDING=PASS
```

This new artifact contains the protected-data evidence pending classification repair and is not yet deployed to the spare T1.

Current live spare-T1 recovery authority remains:

```text
LIVE_RECOVERY_PYZ_SHA256=d7915bc3e42531a829ab22ecb74a7148878c3a2310313e4f1ac07acc8785185e
LIVE_HOMEASSISTANT=local/n3w-homeassistant:2026.10.4-5881590f
LIVE_HOMEASSISTANT_ID=sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365
RETRY_TIMER_STATE=active
FAILED_TRANSACTION_STATUS=ROLLED_BACK
FAILED_TRANSACTION_PHASE=U13B_ROLLED_BACK
```

Therefore the next action is not a fresh INSTALL or R8V13-08. A new conversation must first fresh-rebind the repository, PR, current state and live baseline, then prepare/run an exact read-only deployment preflight for recovery artifact `14980338287`. Any live replacement remains a separate mutation decision after that preflight.

```text
FAILED_TRANSACTION_RECOVERY=CLOSED_PASS
PROTECTED_DATA_PENDING_SOURCE_CLOSURE=PASS
NEXT_RECOVERY_ARTIFACT_BINDING=PASS
NEXT_RECOVERY_ARTIFACT_DEPLOYED=false
FRESH_R8V13_07_ACCEPTANCE=NOT_RUN_YET
R8V13_08_BLOCKED=true
```
