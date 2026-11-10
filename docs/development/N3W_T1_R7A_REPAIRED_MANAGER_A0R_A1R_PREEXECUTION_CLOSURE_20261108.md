# 温室环境监测系统（ESP32-C6）
# N3-W T1 R7A repaired Manager A0R / A1R preexecution closure — 2026-11-08

```text
GATE=N3W_T1_R7A_REPAIRED_MANAGER_EXACT_ARTIFACT_AND_FRESH_A1_REACTIVATION_PREEXECUTION_20261108_01
RESULT=CLOSED_PASS

REPOSITORY=chrenguo-stack/HomeAssistant
PR=800
EXECUTABLE_HEAD=813acb95401612585fc73455e05c81e3e6b86009
EXECUTABLE_TREE=fdea2402ab30f1f6139268d2d450eb75a9f85226

REPAIRED_MANAGER_SOURCE_HEAD=7807271e4c48161f2fad96a7886fa4c24b038321
REPAIRED_MANAGER_TARGET=local/greenhouse-manager:fresh-7807271e4c48
EXPECTED_PREDECESSOR=local/greenhouse-manager:fresh-bf38e388497b

FROZEN_A0R_PACKAGE_RUN_ID=42480154921
FROZEN_A0R_PACKAGE_ARTIFACT_ID=13616844356
FROZEN_A0R_PACKAGE_ARTIFACT_DIGEST_SHA256=3c07406cd51258c8ef95f02e1e6cc80d09eb7235c218e7ead74a02a5521442fd
FROZEN_A0R_PACKAGE_CONTROL_HEAD=4c883c02fbf3a64d944548a1dda8c7431d59ae61
FROZEN_A0R_UPDATER_PYZ_SHA256=c0461a5097d8af0f8a6e7f3a175b7dadc82b55a436c6c229092262cd35521b44
FROZEN_A0R_MANAGER_TAR_SHA256=9746222b145df33d98056f1349456780377875534b28f633b736360c528a0c67
FROZEN_A0R_MANAGER_BUILD_IMAGE_ID=sha256:b1875c6ed969df108d2df768d61369a0c93956d146f284276b392c686c13a4f9

FOCUSED_CI_RUN_ID=42482476119
FOCUSED_SOURCE=SUCCESS
FOCUSED_SOURCE_PYTEST=274_PASS
FOCUSED_EXACT_MANAGER_SLICE=SUCCESS
FOCUSED_PRE_U1_V2_SIMULATION=SUCCESS
FOCUSED_REVALIDATION_ARTIFACT_ID=13617877441
FOCUSED_REVALIDATION_ARTIFACT_DIGEST_SHA256=6852a1241115891b5134d76eca291dd0d12a15d870a59359b56dcacca452ddd5
FOCUSED_REVALIDATION_UPDATER_PYZ_SHA256=2200610bf6c817f7d4b17f6059f2c1b3ac61d21e07b39834fa46408acebb0445
FOCUSED_REVALIDATION_MANAGER_TAR_SHA256=9746222b145df33d98056f1349456780377875534b28f633b736360c528a0c67
FOCUSED_REVALIDATION_MANAGER_BUILD_IMAGE_ID=sha256:b1875c6ed969df108d2df768d61369a0c93956d146f284276b392c686c13a4f9
FOCUSED_PACKAGE_BINDING=PASS

A0R_LIVE_EXECUTION_AUTHORIZED=false
A1R_LIVE_EXECUTION_AUTHORIZED=false
T1_ACCESS=false
T1_MUTATION=false
SERVICE_RESTART=false
A1_REACTIVATION=false
PREPARE=false
USB_MUTATION=false
BOARD_ACCESS=false
MERGE=false
```

## 1. Closure conclusion

The repaired Manager package and both successor preexecution paths are source-closed.

A0R is an isolated Manager-only path from `fresh-bf38e388497b` to repaired
`fresh-7807271e4c48`. A1R is a separate OTA-wiring reactivation path that cannot
start until the repaired Manager V2 transaction is terminal `COMMITTED` and a fresh
post-A0R read-only check still passes.

The old A0/A1 execution packages remain historical evidence and were not modified or
reactivated.

## 2. Exact authority split

The live A0R executor intentionally remains bound to the already frozen package authority:

```text
run=42480154921
artifact=13616844356
control_head=4c883c02fbf3a64d944548a1dda8c7431d59ae61
```

The focused executor repair at `813acb...` does not alter the frozen package bytes.
The current-head workflow rebuilt a second verification package and passed exact binding,
but that artifact is validation evidence only and is not promoted to live A0R authority.

This separation is deliberate: package authority is immutable while later operator-side
executor safety guards may be strengthened without recursively changing package authority.

## 3. Independent focused review finding and repair

The first A1R draft correctly required:

- Manager transaction component = manager;
- status/phase = COMMITTED;
- `authorization_consumed=true`;
- target = repaired `fresh-7807271e4c48`.

However, the manifest additionally claimed that the transaction must come from the exact
new A0R authorization, while the executor did not yet verify
`authorization_id_sha256`. That mismatch was a potential false-PASS route.

Focused repair head `813acb...` now requires:

```text
A0R post-apply:
  authorization_consumed=true
  authorization_id_sha256=SHA256(A0R_AUTHORIZATION)

A1R preflight:
  authorization_id_sha256=SHA256(the same exact A0R authorization)
  target=local/greenhouse-manager:fresh-7807271e4c48
  status=COMMITTED
  phase=COMMITTED
```

A1R local-source validation also enforces the manifest authorization-separation contract.

No architecture change, product image rebuild, T1 access, runtime mutation or authorization
grant was introduced by this focused repair.

## 4. CI evidence

Gate-specific workflow run `42482476119` completed:

- source: SUCCESS;
- source test set: 274 passed;
- exact-manager-slice: SUCCESS;
- pre-u1-v2-simulation: SUCCESS;
- exact package post-upload binding: PASS.

The exact Manager tar and build image identity are unchanged from the frozen repaired
Manager source artifact. The current-head verification package has a different control-head
binding/updater package identity and therefore remains verification evidence rather than a
replacement live authority.

## 5. Live-state boundary

No fresh T1 runtime read occurred in this gate.

Last accepted recovery evidence before this gate was the OTA-disabled healthy path with
Manager `fresh-bf38e388497b`; the user additionally reported that after reboot the
Home Assistant web administration UI could be logged into successfully. That operator
observation supports current usability but does not prove exact Manager/HA/Broker runtime
identity and is not a substitute for fresh read-only eligibility.

Therefore:

```text
FRESH_MANAGER_RUNTIME=UNKNOWN_FRESH
FRESH_HOMEASSISTANT_RUNTIME=UNKNOWN_FRESH
FRESH_BROKER_RUNTIME=UNKNOWN_FRESH
OPERATOR_HOMEASSISTANT_POST_REBOOT_WEB_LOGIN=PASS
```

## 6. Authorization state

```text
A0R_PROPOSED_AUTHORIZATION=N3W_T1_CORE_UPDATER_R7A_REPAIRED_MANAGER_A0R_LIVE_APPLY_20261108_01
A0R_GRANTED=false

A1R_PROPOSED_AUTHORIZATION=N3W_T1_R7A_REPAIRED_MANAGER_A1R_LIVE_REACTIVATION_20261108_01
A1R_GRANTED=false

OLD_A0_AUTH_REPLAY=false
OLD_A1_AUTH_REPLAY=false
OLD_BOUNDARY_B_AUTH_REPLAY=false
```

A0R and A1R must remain separate one-shot authorizations.

## 7. Next bounded gate

```text
NEXT_ONE_GATE=N3W_T1_R7A_REPAIRED_MANAGER_A0R_FRESH_LIVE_READONLY_ELIGIBILITY_20261108_01
LIVE_RUNTIME_MUTATION=false
SERVICE_RESTART=false
T1_FILE_WRITE=false
USB_MUTATION=false
BOARD_ACCESS=false
MERGE=false
AUTO_EXECUTE_AFTER_PASS=false
```

The next gate may only establish fresh real-T1 eligibility for A0R. It must confirm the
predecessor stack, updater recovery state, OTA-disabled residue state and zero-USB condition.
It must not stage the package, invoke plan/apply, restart services, activate A1R or enter
Boundary B.

After that read-only gate passes, real A0R apply still requires a separate explicit
authorization.

## 8. KF-144 disposition

```text
KF144_SOURCE_REPAIR=CLOSED_PASS
KF144_A0R_A1R_PREEXECUTION=CLOSED_PASS
KF144_LIVE_REVALIDATION=PENDING
```

KF-144 is not live-closed until repaired Manager is deployed and A1R is reactivated on the
real T1 with the required stability checks passing.
