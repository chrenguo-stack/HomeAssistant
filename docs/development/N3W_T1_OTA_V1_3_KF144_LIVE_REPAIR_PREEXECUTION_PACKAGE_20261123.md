# N3-W T1 Core Stack OTA V1.3 — KF-144 live repair pre-execution package（2026-11-23）

## 0. Result

```text
TASK=N3W_T1_OTA_V1_3_KF144_LIVE_REPAIR_PREEXECUTION
STATUS=PREEXECUTION_PACKAGE_READY
LIVE_MUTATION_AUTHORIZATION_GRANTED=false
T1_MUTATION=false

READONLY_PREFLIGHT_RAW=STOP_DRIFT
READONLY_PREFLIGHT_CLASSIFICATION=SAFE_EQUIVALENT_PASS
FALSE_STOP_REASON=KNOWN_EXPIRED_PREPARE_AUTHORITY_RESIDUE
KF144_STATUS=SOURCE_CI_CLOSED_LIVE_REPAIR_PENDING
```

The fresh spare-T1 read-only preflight found no runtime, transaction, updater, USB, image, compose or service drift. The only failed local-helper condition was the helper's stronger-than-product assumption that `ha-prepare-authority.json` must be absent at U4.

That residue is not a new product failure. It is the exact historical schema-v2 prepare authority issued during the previously archived U3→U4 live acceptance:

```text
PREPARE_AUTHORITY_SHA256=113ee964ba0e271947632b75b6bd1b3da3dbaf816ee7c26e0c691dd5dae322e4
PREPARE_AUTHORITY_EXPIRES_AT_UNIX=1795426972
PREPARE_AUTHORITY_EXPIRED=true
OBSERVED_NOW_UNIX=1795440811
```

The source contract for `--retire-precutover-failure` does not require the prepare-authority file to be absent. It admits only an exact no-cutover U4 failure, verifies the live predecessor binding and target-image absence, validates any existing install authority, terminalizes the transaction, and removes the install-authority file. An expired prepare authority is not read by that retirement path. Future prepare-authority publication may replace an expired predecessor record; it must never replay it.

Therefore the observed state is classified as a safe equivalent of the expected U4 failure baseline, and the earlier `STOP_DRIFT` is a preflight-oracle false stop rather than live system drift.

## 1. Fresh live entry authority

```text
TRANSACTION_STATUS=ACTIVE
TRANSACTION_PHASE=U4_READY_TO_INSTALL
TRANSACTION_FILE_SHA256=a22a4260401ddb04318afba1b03495edb23a32c68196372987501b50154c2a66
TRANSACTION_ID_SHA256=760dc8bdab1c9ceee2b0d3dfb2797111f24e69a9e7569efb6907bc64325d71fe
FAILURE_CODE=ha_usb_predecessor_acceptance_baseline_unavailable
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
AUTHORIZATION_ID_SHA256=null

LIVE_HOMEASSISTANT=local/n3w-homeassistant:2026.10.4-5881590f
LIVE_HOMEASSISTANT_IMAGE_ID=sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365
LIVE_MANAGER=local/greenhouse-manager:fresh-44e7d7472714
LIVE_MANAGER_IMAGE_ID=sha256:1471828ab07cf9b71c01a6e78994711a5954f0a178b8be087a28bb65a967c7d2
LIVE_BROKER=local/n3w-mosquitto:2.1.2-3184566d
LIVE_BROKER_IMAGE_ID=sha256:df265f1e2b2e3dc35d5eb194e698c598e01c5ebca370da307b34332f9bf0a563
LIVE_RUNTIME_RESTART_COUNT_ALL=0

LIVE_UPDATER_PYZ_SHA256=0ec63d6527be8e583b087576cda20c543edc707401a01344c20f8a0f354a0e51
TARGET_HA_10_0_IMAGE_LOADED=false

USB_FILESYSTEM=ext4
USB_LABEL=N3W-UPDATE
USB_TRANSACTION_BINDING=PASS
USB_DEVICE_PRESENT=true

INSTALL_AUTHORITY_SHA256=ad1588f23ae8dc11afb56f486bee5e783c401257361e8a36c569c4197f050c4f
INSTALL_AUTHORITY_EXPIRES_AT_UNIX=1795435177
INSTALL_AUTHORITY_EXPIRED=true

RELEASE_PIN_SHA256=ba01bf1fa1a18a4b2c0ccef343c45360db5e0436559be43fc6e1cb3990fec59d
RELEASE_PIN_EXPIRES_AT_UNIX=1795436977
RELEASE_PIN_EXPIRED=true

ACTIVE_HA_MONITORING_COMPONENT=false
```

No prior install authority, prepare authority or release pin is reusable.

## 2. Exact HA recovery successor

Source/artifact authority:

```text
EXECUTABLE_SOURCE_HEAD=1fbe674e25edb4c6fb1a3740042778adc55def68
HA_RECOVERY_RUN_ID=45175810759
HA_RECOVERY_ARTIFACT_ID=14818806074
HA_RECOVERY_ARTIFACT_ZIP_SHA256=46bc0cc890b791de8219cabb12eb162136027c2ad7d6ef1c4fb4d3c21a2f009d
HA_RECOVERY_INSTALL_MANIFEST_SHA256=ef8e040fabe2fa1619d1ee28fce1785a535ef85edd15f8f4d416ed780e08fe07
NEW_HA_RECOVERY_PYZ_SHA256=eee49d52ae4ea7f9ecb20a27d1fc467e66708d4fc7df28493acf7bb7f8a049cf
NEW_HA_RECOVERY_PYZ_SIZE_BYTES=493865
RETIRE_PRECUTOVER_FAILURE_FLAG_PRESENT=true
```

The currently installed updater came from historical recovery artifact `14808549839`:

```text
OLD_RECOVERY_ARTIFACT_ID=14808549839
OLD_RECOVERY_ARTIFACT_ZIP_SHA256=d43c59569e13b1a6c66f5138b1f77e32fe1c21a9fbc11fafc6472cda3b059cb1
OLD_HA_RECOVERY_PYZ_SHA256=0ec63d6527be8e583b087576cda20c543edc707401a01344c20f8a0f354a0e51
OLD_NON_PYZ_LIVE_VERIFIED_COUNT=10
```

Independent artifact-to-artifact comparison proves all ten non-pyz installation payloads are byte-identical between old artifact `14808549839` and repaired artifact `14818806074`. Only `ha-recovery.pyz` changed.

```text
NON_PYZ_FILE_COUNT=10
NON_PYZ_OLD_NEW_PARITY=PASS
ONLY_CHANGED_INSTALL_PAYLOAD=ha-recovery.pyz
```

This permits a bounded updater-only patch while the U4 transaction is still active. Running the full recovery installer before retirement is forbidden because its source contract requires all transactions to be terminal/idle.

## 3. Exact Manager successor

```text
MANAGER_A_TO_B_RUN_ID=45175810919
MANAGER_PACKAGE_ARTIFACT_ID=14819845760
MANAGER_PACKAGE_ZIP_SHA256=362c300922816730d4209d450b376769c19319a34d594d2c3a90ea2e31ab143a
GENERIC_V2_UPDATER_PYZ_SHA256=d43036f333872e2e25272b26552809c8d40cd822efc8f0d414e71878594bf2bc

MANAGER_PREDECESSOR=local/greenhouse-manager:fresh-44e7d7472714
MANAGER_TARGET=local/greenhouse-manager:fresh-1cae18039eee
MANAGER_TARGET_IMAGE_ID=sha256:9547078268e5f2550b46583abbd87d9f0a6bbaa727a0af2c19379ca906954867
MANAGER_TAR_SHA256=bbce0ee5c399b2fbc315dcf34affb6391f54864144faba4f9efb983b160c8734
MANAGER_TAR_SIZE_BYTES=62953984
MANAGER_BASELINE_CANONICAL_SHA256=78404869cda4b6fe14226b514623880b76045cd9a58a149f063d61edf57dd199
MANAGER_COMPATIBILITY_REVIEW_SHA256=5046d2e180db6a0c620cfc91a58577d80a9fac2199b7155ff20015ca61caae03
ROLLBACK_COMPATIBLE=true
BROKER_CHANGE_REQUIRED=false
HOMEASSISTANT_CHANGE_REQUIRED=false
```

Generic V2 apply confirmation remains `T1_CORE_UPDATER_APPLY`; a fresh bounded authorization ID is required and must match the Generic V2 authorization schema. No previous authorization may be reused.

## 4. Bounded live-repair sequence

The intended order remains:

```text
PATCH_EXACT_HA_RECOVERY_UPDATER
→ RETIRE_PROVEN_NO_MUTATION_U4_FAILURE
→ GENERIC_V2_MANAGER_SUCCESSOR fresh-44e7... → fresh-1cae...
→ ACTIVATE_CANDIDATE_MONITORING_RUNTIME
→ MANAGER_BROKER_HA_SELF_TEST=PASS
→ FRESH_HA_PREPARE
→ REENTER_10.4_TO_10.0_NORMAL_TRANSACTION
```

### Phase A — updater-only patch

Entry checks must re-prove the complete section-1 live state immediately before mutation.

Allowed mutation:

- temporarily quiesce only the recovery retry/IPC control plane needed to prevent concurrent updater execution;
- atomically replace only `/opt/n3w-t1-core-updater/ha-recovery.pyz`;
- old pyz must be exactly `0ec63d65...`;
- new staged pyz must be exactly `eee49d52...`;
- fsync and readback are mandatory;
- transaction bytes must remain exactly `a22a4260...`;
- HA/Manager/Broker must remain running and unchanged;
- target HA 10.0 must remain absent.

Patch rollback: before transaction retirement, any patch/readback failure restores the exact old pyz and re-arms the previous control plane only after old-pyz readback and transaction non-drift are proven.

### Phase B — retire the proven no-cutover U4 failure

Use the repaired updater's `--retire-precutover-failure`.

Expected terminal result:

```text
STATUS=PRE_CUTOVER_FAILURE_RETIRED
TRANSACTION_STATUS=ROLLED_BACK
TRANSACTION_PHASE=U4_READY_TO_INSTALL
FAILURE_CODE=ha_usb_predecessor_acceptance_baseline_unavailable
INSTALL_AUTHORITY_PRESENT=false
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
TARGET_HA_10_0_IMAGE_LOADED=false
```

The expired historical prepare-authority file may remain present after retirement. It is not executable authority and must not be replayed. Its persistence alone is not a failure.

After retirement, the recovery package is idle-admissible. Because all ten non-pyz files already match the repaired artifact, full package verification/install is expected to be idempotent; any unexpected non-pyz drift must STOP before Manager mutation.

### Phase C — Generic V2 Manager successor

Before apply:

- Generic V2 `baseline`, `inspect --component manager` and `plan` must PASS;
- current Manager must still be `fresh-44e7d7472714`;
- HA and Broker identities must match the archived baseline;
- no active HA business transaction may exist;
- target Manager tar and target manifest must match section 3 exactly.

Apply only the Manager component. The Generic V2 transaction must either COMMIT the exact target or execute its existing rollback path. A failed or unresolved Manager transaction stops the KF-144 route; do not continue to candidate activation.

### Phase D — candidate monitoring runtime + self-test

Entry requires Manager successor COMMITTED and healthy.

Activation must preserve:

- Home Assistant image `2026.10.4-5881590f`;
- Broker image `2.1.2-3184566d`;
- Manager target `fresh-1cae18039eee`;
- protected data mounts and hard authority;
- no business HA transaction.

The candidate runtime must mount/activate `n3w_ota_monitoring`, bind the installed HA version to the compose env authority, and prove the real Manager→Broker→HA maintenance self-test round trip. `natural_only` is not an acceptance path.

If activation or self-test fails, use the source-defined candidate activation rollback and require the prior healthy runtime before stopping.

### Phase E — fresh HA transaction

Only after self-test PASS:

1. create/materialize fresh exact HA candidate authority;
2. issue a fresh prepare authority; never reuse the expired `113ee964...`;
3. PREPARE a new 10.4→10.0 transaction;
4. reuse existing valid USB only through the normal V1.3 capacity/identity checks;
5. advance through normal pre-cutover preparation.

The repair package does not pre-authorize a future destructive install/cutover. A later install/live-authorization boundary remains separately bound to the new transaction.

## 5. Hard STOP conditions

STOP the affected route on any of the following:

- PR/source/artifact hash drift;
- transaction no longer equals the section-1 U4 failure before Phase A;
- any prior authority becomes unexpired or appears newly issued without explicit authorization;
- HA/Manager/Broker runtime or restart-count drift before the relevant mutation;
- USB binding/identity drift;
- target HA 10.0 unexpectedly loaded before the fresh transaction admits it;
- updater patch changes anything except the pyz;
- U4 retirement reports anything except the exact no-cutover terminal result;
- Generic V2 Manager plan/apply baseline mismatch;
- Manager successor unresolved or rollback unhealthy;
- candidate runtime activation changes Broker or HA image identity;
- self-test unavailable/fails;
- rollback cannot restore the last healthy runtime.

Broker OTA, reboot/power-cycle, PR merge and release remain out of scope.

## 6. Authorization boundary

```text
CURRENT_NEW_LIVE_AUTHORIZATION=NONE
PROPOSED_NEXT_GATE=N3W_T1_V1_3_KF144_LIVE_REPAIR_20261123_01
PROPOSED_SCOPE=PHASE_A_THROUGH_PHASE_D
FRESH_HA_PREPARE_AFTER_SELF_TEST=SEPARATE_SUBBOUNDARY_WITHIN_SAME_TASK_CHAIN
BROKER_MUTATION=false
REBOOT=false
MERGE=false
RELEASE=false
```

No live mutation may begin until the user explicitly grants the next live gate. The first live mutation boundary is quiescing the updater retry/IPC control plane for the atomic pyz replacement.

## 7. Archive status

```text
PUBLIC_SOURCE_ARCHIVED=true
PUBLIC_TESTS_ARCHIVED=true
PUBLIC_DOCS_ARCHIVED=true
PRIVATE_RAW_EVIDENCE_PRESENT=false
PRIVATE_RAW_EVIDENCE_PUBLICLY_EXPOSED=false
IMPORTANT_ENVIRONMENT_FACTS_ARCHIVED=true
UNARCHIVED_CRITICAL_RESULT_COUNT=0
TEAM_SHARED_WORKSPACE=GITHUB
TEAM_SHARE_COMPLETENESS=PASS
NEXT_SAFE_ENTRY_POINT=EXPLICIT_LIVE_AUTHORIZATION_FOR_KF144_REPAIR
```
