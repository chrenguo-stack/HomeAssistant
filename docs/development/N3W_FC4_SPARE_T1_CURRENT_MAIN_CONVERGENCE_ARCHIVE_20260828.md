# N3-W / FC4 Spare T1 Current-Main Convergence Archive

Date: 2026-08-28  
Scope: public-safe documentation archive only

## 1. Purpose

This document archives the Spare T1 current-main convergence work completed after the N3-W pairing/recovery simplification merge. It records the runtime convergence result, the failure chain that led to the final corrected successor, the validation-harness failures encountered during cutover, and the regression rules derived from those failures.

This archive does **not** contain passwords, Setup Secrets, private IP addresses, private host paths, raw DynSec content, raw container inspection dumps, or board identifiers.

## 2. Frozen source and image authority

The product source/image authority did not change during this convergence work.

```text
EXACT_MAIN_COMMIT=1f80d54ff5f84056e0559a7d8cc80427c5e0bb14
MANAGER_VERSION=0.4.99
MANAGER_REVISION=1f80d54ff5f84056e0559a7d8cc80427c5e0bb14
SOURCE_CHANGE_REQUIRED=false
IMAGE_CHANGE_REQUIRED=false
```

The original current-main successor used during the first deployment attempt is retained only as failure evidence:

```text
OLD_SUCCESSOR_SHA256=235a3711b5a99ae401bb743a21259a8f53177a7c5c2894fe412ffdd00698b2c7
OLD_SUCCESSOR_LIVE_REUSE_FORBIDDEN=true
```

The corrected successor that completed convergence is:

```text
CURRENT_MAIN_SUCCESSOR_SHA256=8a69fd5da27ee828b11dd11ea7e562da5f77ef762748ab4f1ee6016af038ec67
```

## 3. Credential and DynSec reconciliation

Provisioning and Manager MQTT identities were reconciled against the already-existing private credential material. No new product credential authority, role hierarchy, or application-key generation was introduced.

The successful Manager credential transaction proved that a Mosquitto Dynamic Security state-changing control operation changes both the target credential representation and the top-level `changeIndex`. The final production authority reached:

```text
MANAGER_CREDENTIAL_RECONCILIATION=PASS
PROVISIONING_CREDENTIAL_RECONCILIATION=PASS
DYNSEC_CHANGEINDEX=15
```

The important semantic rule is that a state-changing DynSec comparator must account for the mandatory `changeIndex` transition; a comparator that allows only the target object field is incomplete.

## 4. First current-main deployment failure: runtime binding false-pass

The first current-main deployment using the old successor failed with MQTT `Not authorized` even though earlier static successor checks had reported Manager identity/product-runtime binding PASS.

Read-only post-failure forensics showed that the static gate had not proven equivalence between the Manager's **effective** MQTT connection settings and a previously successful product-equivalent Manager connection authority.

The relevant configuration domains are separate:

```text
GH_MQTT_*                 = Manager's own Broker client settings
GH_N3W_NODE_BROKER_*      = node-facing Broker authority used by N3-W provisioning/runtime
```

They must not be treated as interchangeable.

The corrected successor changed only the bounded Manager runtime-composition authority required for the successful Manager MQTT endpoint/CA binding, while preserving image, credentials, N3-W feature flags, node-facing Broker settings, pairing settings, and shared state.

The corrected static gate additionally proved:

```text
CORRECTED_BINDING_GATE=PASS
OLD_SUCCESSOR_REJECTED_BY_CORRECTED_GATE=true
```

This anti-false-pass property is now part of the regression contract.

## 5. Validation-harness failure: remote quoting

The first deployment of the corrected successor established successful Manager MQTT authentication, provisioning authentication, N3-W runtime activation, product pairing activation, pairing-service ownership, unchanged Broker/Home Assistant, unchanged DynSec, and direct shared-state reuse.

The transaction nevertheless rolled back because the external stability validator suffered a remote command quoting failure that removed Python string delimiters and caused a `SyntaxError` during a read-only `changeIndex` probe.

Subsequent read-only forensics proved:

```text
VALIDATOR_ONLY_FAILURE=true
REAL_PRODUCT_FAILURE=false
CORRECTED_SUCCESSOR_PRODUCT_DEFECT_PROVEN=false
```

The candidate had remained alive for more than the required window, but elapsed wall time was correctly **not** promoted to a stability PASS because the required predicates had not been continuously observed by a valid validator.

The validator was then replaced by a transaction-private, preflighted script/argv contract with no nested remote Python quoting. The accepted validator fingerprint was:

```text
STABILITY_VALIDATOR_SHA256=d9d627b2c09066d6a7c9170a019fdb8af0d0c703ca59fc36c7a2b10c15f76806
```

## 6. Closure-schema failure: candidate state vs rollback terminal state

One failed-deployment closure exposed an evidence-model defect: fields describing the candidate were reported after rollback, making terminal values appear to describe the pre-rollback candidate.

Forensics proved the candidate had in fact been running, authenticated, N3-W active, pairing active, and owner of the pairing ports before rollback.

The closure contract was corrected to separate:

```text
CANDIDATE_*
PRE_ROLLBACK_*
FINAL_*
POST_ROLLBACK_*
```

A terminal rollback state must never overwrite or ambiguously stand in for the candidate-state evidence used to classify the product failure.

## 7. Validation-harness failure: final provisioning probe identity drift

A later corrected deployment completed a valid 60-second stability observation:

```text
STABILITY_SECONDS=60
STABILITY_SAMPLE_COUNT=13
ALL_STABILITY_SAMPLES_PASS=true
CURRENT_MAIN_MANAGER_60S_STABLE=true
```

It still rolled back because a final provisioning probe reconstructed its connection with a non-authorized Client ID. This was a harness identity drift, not a product-runtime failure.

The final cutover contract therefore froze and self-tested the exact provisioning probe identity/argv before claim, then required the final probe to reuse that exact already-proven contract rather than reconstructing it after the stability window.

## 8. Final successful cutover

The final transaction completed without rollback.

```text
CURRENT_MAIN_MANAGER_DEPLOYMENT=PASS
CURRENT_MAIN_MANAGER_60S_STABLE=true
FINAL_MANAGER_MQTT_AUTH=PASS
FINAL_PROVISIONING_MQTT_AUTH=PASS
FINAL_N3W_RUNTIME_ACTIVE=true
FINAL_N3W_PRODUCT_PAIRING_ACTIVE=true
FINAL_PAIRING_OWNER=CURRENT_MAIN_MANAGER
BROKER_RECREATED=false
BROKER_RESTARTED=false
HOMEASSISTANT_UNCHANGED=true
STATE_COPY=false
STATE_MIGRATION=false
STATE_MERGE=false
SPARE_T1_CURRENT_MAIN_CONVERGENCE=PASS
READY_FOR_FC4_THREE_BOARD_FINAL_PHYSICAL_ACCEPTANCE=true
```

The preserved legacy `fc4-manager` container was stopped but not deleted and remains a rollback artifact only. It is not part of the active product authority after convergence.

## 9. Regression rules derived from this convergence

1. **DynSec state-change comparator** — state-changing control commands must validate the target semantic change plus the expected top-level `changeIndex` transition; all unrelated state remains invariant.
2. **Effective runtime authority** — static successor gates compare effective values against a known-successful product-equivalent authority, not key presence or plausible defaults.
3. **Manager-vs-node Broker separation** — `GH_MQTT_*` and `GH_N3W_NODE_BROKER_*` remain separate authority domains.
4. **Anti-false-pass proof** — when correcting a gate after a live failure, the new gate should explicitly reject the known-bad predecessor artifact.
5. **Validator infrastructure classification** — parse/quoting/collector failures fail the transaction but do not automatically classify the product as defective.
6. **Continuous stability proof** — wall-clock lifetime is not a stability PASS unless the required predicates are continuously observed for the required duration.
7. **Phase-separated closure fields** — candidate/pre-rollback/final/post-rollback states are distinct evidence namespaces.
8. **Frozen probe identity** — final authentication probes must reuse a preflighted identity/argv contract; do not reconstruct Client IDs after claim.
9. **Rollback preservation** — already-committed credential/DynSec reconciliation is not reverted during deployment rollback; rollback restores the protected runtime baseline only.
10. **Consumed authorization** — every failed live transaction remains terminal and non-replayable; a new live attempt requires a new unique authorization.

## 10. Product/physical boundary

No ESP32-C6 board was accessed during this Spare T1 convergence sequence.

```text
BOARD_ACCESS=false
USB_SERIAL_ACCESS=false
SERIAL_OPEN=false
FLASH=false
NVS=false
RF_EXECUTION=false
```

The next product stage is the FC4 three-board final physical acceptance, beginning with read-only history/progress reconciliation before any new board action.

## 11. Public/private evidence boundary

Not committed to the public repository:

- credential contents or password-derived verifiers;
- raw Dynamic Security JSON;
- private host paths and private network addresses;
- transaction-private successor files;
- raw validator execution evidence;
- raw container/env dumps;
- board identity material.

Those remain private operational evidence. This document is the public-safe semantic archive.
