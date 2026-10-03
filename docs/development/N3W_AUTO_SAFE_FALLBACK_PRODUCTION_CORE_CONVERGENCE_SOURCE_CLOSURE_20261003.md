# N3-W Auto Safe Fallback — Production Core Convergence Source Closure

Date: 2026-10-03

## 1. Scope

This document closes the **source / automated-validation** stage that converges the validated auto safe fallback design from the reference/lab `greenhouse_n3w_core` into the actual F1.0-RC2 production component `greenhouse_n3w_product_core`.

This is **not** the physical Gate F closure.

## 2. Authority and frozen source

```text
PRODUCTION_BASE=d3c158b4376ca0577e4a3a45a18a6c5c6e994e75
PRODUCTION_BASE_PR=474
SOURCE_HEAD=b2419d17c198a85b7b50d9c1771544c2e3a0ab6b
STACKED_PR=522
```

PR #522 is stacked on the exact PR #474 production head so the PR #474 full-channel Relay discovery and multi-gateway selection work remain the production baseline.

## 3. Production convergence implemented

The production core now contains the validated auto safe fallback pieces required before physical validation:

- independent Manager discovery query/parser and filtering;
- bounded/nonblocking ESP32 discovery session;
- Broker relocation policy and candidate budgets;
- runtime-only Broker address retargeting;
- MQTT old-event fencing / retarget barrier overlay;
- Direct recovery integration through the existing Direct recovery state machine;
- RAM-only candidate promotion after successful Direct commit;
- failure rollback to the stable runtime Broker address;
- pairing discovery extraction without using ordinary pairing hello/begin as address recovery.

The convergence does not introduce a second Direct/Relay state machine.

## 4. Preserved security and durable state boundaries

The recovery path does not rewrite the durable pairing or Broker credential record when an address candidate is tested or promoted for the current boot.

The following identity/credential material remains unchanged by address recovery:

- system identity;
- CA material;
- TLS server name verification identity;
- MQTT username;
- MQTT password;
- MQTT client ID;
- credential generation;
- application/system peer keys;
- ordinary pairing trust state.

## 5. Regression boundary from PR #474

Production convergence was implemented as an additive/directed merge onto PR #474. The production regression checks explicitly preserve:

- full-channel Relay discovery fallback;
- gateway-selection behavior;
- discovery restart/restore behavior;
- existing F1.0-RC2 production target binding to `greenhouse_n3w_product_core`.

## 6. Validation evidence

Dedicated workflow:

```text
WORKFLOW=N3W auto safe fallback production core convergence CI
RUN_ID=37122275681
JOB_ID=111200588675
RESULT=SUCCESS
VALIDATED_HEAD=b2419d17c198a85b7b50d9c1771544c2e3a0ab6b
```

All required steps passed:

```text
AUTO_FALLBACK_PRODUCTION_CONVERGENCE_SOURCE_CONTRACT=PASS
PR474_FULL_CHANNEL_REGRESSION_CONTRACT=PASS
GATEWAY_SELECTION_V1_REGRESSION_CONTRACT=PASS
BROKER_RELOCATION_POLICY_HOST_TEST=PASS
PR474_FULL_CHANNEL_HOST_REGRESSION=PASS
GATEWAY_SELECTION_V1_HOST_REGRESSION=PASS
F1_0_RC2_PRODUCTION_TARGET_CONFIG=PASS
F1_0_RC2_PRODUCTION_TARGET_COMPILE=PASS
```

The first CI attempt failed only because the new source contract incorrectly required `product_runtime: true` to appear directly in `f1_0_rc2_n3w_target.yml`; the actual configuration places it in the included `packages/n3w_product_transport.yml`. The contract was corrected without changing product source, and the final source head above passed the full production convergence workflow.

## 7. Closure decision

```text
PRODUCTION_CORE_CONVERGENCE_SOURCE_COMPLETE=true
SOURCE_REPAIR_COMPLETE=true
AUTOMATED_REGRESSION_COMPLETE=true
F1_0_RC2_EXACT_COMPILE_COMPLETE=true

PHYSICAL_ACCEPTANCE_COMPLETE=false
B3_CLOSED=false
BOARD_ACCESS=false
T1_LIVE_MUTATION=false
MERGE=false
```

The source/CI stage is closed. No further product-source change is required before preparing and executing Gate F unless a new concrete defect is found.

## 8. Next gate — explicit STOP

Next gate is Gate F physical validation using an exact artifact bound to the frozen production source head.

Gate F must prove, on the actual production path, at minimum:

1. old Broker address works normally before the address change;
2. T1 IPv4 changes while T1 identity, certificate identity and account credentials remain the same;
3. the old address fails;
4. the node, without rebooting, discovers the new candidate address;
5. the new IP still passes the original TLS identity and MQTT account authentication;
6. Manager-visible Direct telemetry recovers;
7. healthy-Relay Direct probe remains within the existing 30 s ownership ceiling;
8. unreachable/invalid candidate exits within the existing parent deadline and restores Relay/backoff behavior;
9. candidate address remains RAM-only and disappears after power cycle;
10. durable pairing/Broker credential generation remains unchanged.

**STOP:** do not write a board, mutate T1, claim physical acceptance, close B3, or merge PR #522 without explicit Gate F authorization.
