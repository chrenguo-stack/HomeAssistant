# N3-W T1 OTA V1.3 R8V13-07 U10 live-repair Attempt 01 stop diagnosis

Date: 2026-11-25

## Physical execution result

Attempt 01 entered the exact live-repair executor after the prior read-only preflight had passed.

Observed output:

```text
PHASE=LOCAL_ARTIFACT_BINDING
LOCAL_ARTIFACT_BINDING=PASS
PHASE=REMOTE_STAGE
PHASE=LIVE_REPAIR_PRECHECK
TRANSACTION_EXACT=PASS
TARGET_ENV_EXACT=PASS
CANDIDATE_RECOVERY_NORMALIZATION=PASS
PHASE=QUIESCE_RECOVERY_CONTROL_PLANE
RECOVERY_STARTED=false
RESULT=R8V13_07_U10_LIVE_REPAIR_AND_RECOVERY_STOP
```

No `PHASE=ATOMIC_RECOVERY_PYZ_PATCH` was reached. Therefore the successor recovery pyz was not published by this attempt.

## Source-level false-STOP defect

The Attempt 01 executor admitted the retry service before mutation when its state was either `inactive` or `failed`, but after stopping the recovery control plane it required the same service to be exactly `inactive`.

That is internally inconsistent: a failed service is already quiesced and can remain in `failed` after `systemctl stop`. Treating `failed` as non-quiesced at the second gate can produce a false STOP without any application/recovery mutation.

The exact quiesce gate was repaired to:

- require retry timer = `inactive`;
- accept retry service = `inactive` or `failed`;
- accept IPC socket/service = `inactive` or `failed`;
- emit all four quiesced states before later hash/candidate checks.

The executor fix commit is `eb8fa691ce73c7df89f9bcb5c56e948795c473c7`.
The focused regression test commit is `507c80bf7c872fda6eac8793e4f604036bd898fd`.

## Current boundary

```text
INSTALL_REPLAY_ALLOWED=false
SECOND_TRANSACTION_ALLOWED=false
RECOVERY_STARTED=false
SUCCESSOR_PYZ_PUBLISHED_BY_ATTEMPT01=false
R8V13_08_BLOCKED=true
LIVE_REPAIR_RETRY_PENDING_EXACT_CI=true
```

Focused CI run for exact head `507c80bf7c872fda6eac8793e4f604036bd898fd`:
`45514240797`.

At the time of this archival update it had not reached a terminal result. Per project polling policy no additional active polling is performed after three non-terminal checks.

Before another live-repair attempt, run the bounded read-only post-stop forensic check and require exact transaction/env/old-pyz state to remain compatible with the original U10 preflight. Then require the new focused CI to complete SUCCESS.


## Post-Attempt-01 physical forensic evidence

The bounded read-only forensic check after Attempt 01 reported:

```text
RETRY_TIMER_STATE=active
RETRY_SERVICE_STATE=activating
IPC_SOCKET_STATE=active
IPC_SERVICE_STATE=inactive
TX_FILE_SHA256=4c68793fb1909366aa9acee7c06b74f3bac12dfae8681b1c4a6407abd6d2bd44
COMPOSE_ENV_SHA256=8f4a73bfa8126f9e4ee993197cece40fddcdf140c994687a391014d627c0e8cc
LIVE_PYZ_SHA256=5208dadc14c2cf0024c0711de60ce0f70f5a19ea27de4e74f290d4c3c8bcfe0a
STAGED_NEW_PYZ_PRESENT=true
STAGED_NEW_PYZ_SHA256=d7915bc3e42531a829ab22ecb74a7148878c3a2310313e4f1ac07acc8785185e
TX_STATUS='ACTIVE'
TX_PHASE='U10_INTERNAL_PREDECESSOR_CAPACITY_RELEASED'
TX_RECOVERY_REQUIRED=True
TX_AUTHORIZATION_CLAIMED=True
TX_AUTHORIZATION_CONSUMED=True
TX_PREDECESSOR_RELEASE_OBSERVED=True
TX_TARGET_ACTIVATION='BINDING'
TARGET_IMAGE_ID=sha256:c261fa53f30508951833492ba2a19af6cfbb6aa8f2806b531d8f5c6599265306
PREDECESSOR_IMAGE_ID=absent
USB_MOUNT_TARGET=/mnt/n3w-ha-r8-predecessor
```

This proves the transaction/env/live-pyz binding remained exact after the STOP, while the restored retry timer immediately raced the old retry worker back into `activating`.

## Second race repair

The live-repair executor was further repaired so it no longer requires the retry worker to already be quiet before entering the quiesce phase.

New ordering:

1. read-only exact snapshot;
2. record pre-quiesce retry/timer/IPC states without requiring retry service `inactive`;
3. stop retry timer first, then retry service and IPC control plane;
4. require all control-plane owners to be quiet;
5. perform a post-quiesce exact recheck of transaction hash, compose-env hash, old/new pyz hashes, target/predecessor image bindings, manager/broker IDs, USB mount, predecessor launch binding and candidate normalization;
6. only then publish the repaired pyz.

Exact source/test head: `651caca136e74e96c07dc5213360058ecbba90f6`.

Changed files relative to the Attempt-01 archive point are limited to:
- `tools/execution_packages/n3w/t1_ota_r8v13_07/N3W_T1_R8V13_07_U10_LIVE_REPAIR_AND_RECOVER_20261125_01.sh`
- `tests/tools/test_n3w_t1_ota_r8v13_07_u10_live_repair_and_recover.py`

Focused CI run: `45515176542`.

At the third check the run remained `in_progress`; active polling stopped per project policy.

Current physical boundary remains:

```text
INSTALL_REPLAY_ALLOWED=false
SECOND_TRANSACTION_ALLOWED=false
SUCCESSOR_PYZ_PUBLISHED=false
RECOVERY_STARTED=false
R8V13_08_BLOCKED=true
```


## Frozen-site failure-path closure

A final source review found that a pre-patch failure still unconditionally re-armed the retry timer, which would undo an intentionally frozen recovery control plane. This was repaired without changing product recovery semantics:

- when `RECOVERY_STARTED=true`, failure handling still arms IPC + retry timer so the repaired recovery owner can continue;
- before recovery has started, failure handling restores the pre-quiesce control-plane state instead of unconditionally arming the timer;
- when the site was intentionally frozen before the attempt, a pre-patch STOP therefore remains frozen.

Executor repair commit: `8232bcd2584946c3a0bc370a1cd167fa7e7862c8`.
Regression-test head: `9d6f6b19ee52673e3c372cc35e3e52d6461b5270`.

Focused CI run for this exact head: `45516331111`.

After three checks the run had been created but remained `queued`; active polling stopped per project policy.

Current physical state remains intentionally frozen and exact:

```text
RETRY_TIMER_STATE=inactive
RETRY_SERVICE_STATE=failed
TX_FILE_SHA256=4c68793fb1909366aa9acee7c06b74f3bac12dfae8681b1c4a6407abd6d2bd44
COMPOSE_ENV_SHA256=8f4a73bfa8126f9e4ee993197cece40fddcdf140c994687a391014d627c0e8cc
LIVE_PYZ_SHA256=5208dadc14c2cf0024c0711de60ce0f70f5a19ea27de4e74f290d4c3c8bcfe0a
TX_STATUS=ACTIVE
TX_PHASE=U10_INTERNAL_PREDECESSOR_CAPACITY_RELEASED
TX_RECOVERY_REQUIRED=True
```

No second live-repair attempt is authorized to execute until exact focused CI `45516331111` reaches SUCCESS and the final executor binding is rechecked.


## Final focused CI and executor binding closure

The earlier exact-source run `45516331111` was cancelled after the PR advanced. This was a superseded run, not a test failure.

The latest PR head `d78fd6068f96a3b18b7cc462257365bc44725950` reran the same focused workflow and completed SUCCESS:

- focused workflow run: `45516392976`
- focused job: SUCCESS
- focused tests: `68 passed`
- product recovery subset: `25 passed, 73 deselected`
- executor blob: `618d2470856cf20b3e1ef47ab3e70e0bff7d42af`
- executor SHA256 emitted by CI: `57f7b2014290687a9ed06d9490821d87bf727f76f31750958c6988c6292b83ad`

Compare `9d6f6b19ee52673e3c372cc35e3e52d6461b5270 -> d78fd6068f96a3b18b7cc462257365bc44725950` changes only this diagnostic document. Therefore the executor tested by the successful latest-head run is the same exact executable content reviewed for the frozen-site retry.

Physical retry remains bound to the existing transaction only. INSTALL replay and second transaction remain forbidden.


## Attempt 02 durable recovery terminal evidence

Attempt 02 successfully crossed the live-patch boundary and published the repaired recovery archive. The immediate synchronous `systemctl start n3w-t1-ha-recovery-retry.service` returned nonzero, so the wrapper correctly reported STOP with `RECOVERY_STARTED=true` and intentionally retained the repaired live pyz.

Subsequent durable retry processing on the same transaction progressed through:

- repeated historical `ha_usb_predecessor_launch_binding_drift` records from the pre-repair recovery implementation;
- repaired recovery reaching `ha_usb_rollback_protected_data_evidence_pending`;
- `RECOVERY_MONITORING_EVIDENCE_PENDING`;
- terminal `ROLLED_BACK`.

Post-recovery forensic evidence:

```text
TX_TRANSACTION_ID_SHA256=d86669e6d16bb9420191920bc2b02583e7f7207eff0b51ed3f9e6321f99389d4
TX_STATUS=ROLLED_BACK
TX_PHASE=U13B_ROLLED_BACK
TX_FAILURE_CODE=None
TX_RECOVERY_REQUIRED=False
TX_AUTHORIZATION_CLAIMED=True
TX_AUTHORIZATION_CONSUMED=True
TX_PREDECESSOR_RELEASE_OBSERVED=True
TX_TARGET_ACTIVATION=BINDING
TX_TARGET_RELEASE_STEP=RELEASED
ENV_HA_IMAGE=local/n3w-homeassistant:2026.10.4-5881590f
ENV_HA_VERSION=2026.10.4
TARGET_IMAGE_ID=absent
PREDECESSOR_IMAGE_ID=sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365
APPLICATION_OWNER_STATE=active
BROKER_OWNER_STATE=active
IPC_SOCKET_STATE=active
HOMEASSISTANT_CONTAINER=local/n3w-homeassistant:2026.10.4-5881590f
MANAGER_CONTAINER=local/greenhouse-manager:fresh-1cae18039eee
BROKER_CONTAINER=local/n3w-mosquitto:2.1.2-3184566d
LIVE_RECOVERY_PYZ_SHA256=d7915bc3e42531a829ab22ecb74a7148878c3a2310313e4f1ac07acc8785185e
```

This proves the existing consumed-authorization transaction recovered to the predecessor without INSTALL replay or a second transaction.

The forensic command intentionally stopped the retry timer before collecting the journal. Therefore the final product-health closure still requires:

1. exact resident predecessor health verification with the repaired pyz;
2. recovery timer restoration to its normal enabled + active state;
3. archival closure before deciding whether to run a fresh R8V13-07 acceptance transaction.

### Newly observed false-failure semantics

The recovery code treats `ha_usb_rollback_protected_data_evidence_pending` as a generic `UpdaterError`, causing `--resume-pending` to exit nonzero and systemd to mark the oneshot failed even though the journal remains recoverable and later retries can succeed. Monitoring pending already has a dedicated non-error pending status.

This is a product/test-harness false-failure issue to review before the next fresh R8V13-07 acceptance. It does not invalidate the terminal rollback evidence above.
