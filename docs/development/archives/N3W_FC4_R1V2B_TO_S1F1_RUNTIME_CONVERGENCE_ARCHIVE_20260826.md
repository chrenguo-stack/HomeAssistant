# N3-W / FC4 R1-V2B → R1-V2C-S1-F1 Runtime Convergence Archive

- Date: 2026-08-26
- Repository: `chrenguo-stack/HomeAssistant`
- Frozen product baseline: `1f80d54ff5f84056e0559a7d8cc80427c5e0bb14`
- Frozen tree: `f3b8095c62e8a4838eb1b614f05c932f54f5226d`
- Scope: FC4 Spare-T1 current-main convergence evidence and failure classification
- Product source mutation: **false**
- Firmware mutation: **false**
- Board access in this archive chain: **false**

> Public-safe archive. It intentionally excludes private IP addresses, host filesystem paths, credentials, Setup Secrets, private keys, raw hardware identities, and private evidence bodies.

## 1. Purpose

This archive preserves the minimum durable history needed to understand why the FC4 Spare-T1 path moved from local cross-architecture build recovery to native ARM64 validation, why the first current-main Manager live convergence failed, and what remained unresolved at the R1-V2C-S1-F1 handoff boundary.

The product route did not change:

```text
N3-W exact current-main
→ production-equivalent Spare T1
→ current-main Manager/Broker convergence
→ three-board FC4 final physical acceptance
→ N3-W product closure
```

## 2. Exact product authority

```text
MAIN=1f80d54ff5f84056e0559a7d8cc80427c5e0bb14
TREE=f3b8095c62e8a4838eb1b614f05c932f54f5226d
```

The baseline is the PR #336 N3-W pairing/recovery simplification V2 merge.

Candidate built from that exact source on native ARM64:

```text
IMAGE_ID=sha256:de19ff39546b1958344790aabe1d1af569c69c64818b7e068f6936f11b1ae8bd
OS=linux
ARCH=arm64
VERSION=0.4.99
UID=999
GID=999
```

## 3. R1-V2B — local x86_64 → ARM64 build route stopped

The original local build authorization was claimed and consumed. The legacy Docker builder issued the real ARM64 build command and failed in the first compound package/user/directory setup `RUN` with exit code 2.

Subsequent read-only analysis could not identify a failing subcommand. The base image was confirmed `linux/arm64`, and `qemu-aarch64` binfmt was present/enabled with `OCF` flags.

No product-source defect was proven.

Because the actual target platform was already native ARM64, the FC4 route abandoned further Mac/QEMU/buildx/Colima work and moved to a native Spare-T1 build. The consumed R1-V2B authorization is permanently non-replayable.

## 4. R1-V2N — native ARM64 candidate and pre-live validation PASS

A new native-build authorization was claimed and consumed on Spare T1.

Results:

```text
NATIVE_ARM64_BUILD=PASS
CANDIDATE_LABEL_BINDING=PASS
CANDIDATE_UID_GID_BINDING=PASS
RESOLVER_PROBE_RESULT=PASS
SUCCESSOR_COMPOSE_VALIDATION=PASS
DEPLOYMENT_GATE_RESULT=PASS
```

The candidate image identity is the frozen authority shown in section 2.

This result proves that the production Manager Dockerfile and exact current-main source are buildable and runnable on the target ARM64 class; the earlier local cross-architecture failure is therefore not evidence of a product Dockerfile defect.

## 5. R1-V2C — first live convergence

The first live-convergence authorization was claimed and consumed.

Broker convergence succeeded, including both LAN TLS 8883 and the required loopback TLS 8883 publication.

The current-main Manager candidate entered a restart loop. The execution rolled back successfully to the previous stable Manager/Broker/Home Assistant runtime. No credential rotation, application-key rotation, system peer-key rotation, pairing reset/replay, direct database mutation, DynSec mutation, or board access occurred.

## 6. Read-only elimination steps

### 6.1 Private-state metadata

The candidate private-state audit found:

```text
owner binding = PASS for UID/GID 999
private modes = PASS (0600/0700 as applicable)
path/type binding = PASS
```

Therefore broad `chown -R` / `chmod -R` repair was rejected as unjustified.

### 6.2 Cutover chronology

The old Manager had exited before the candidate first start, with approximately six seconds between old-manager death and candidate start.

```text
OLD_MANAGER_RUNNING_AT_CANDIDATE_FIRST_START=false
PAIRING_PORT_COLLISION_PROVEN=false
AUTO_RESTART_COLLISION_PROVEN=false
```

The cutover order was therefore classified as correct, while the candidate startup failure remained unresolved.

## 7. R1-V2C-D1 — one-shot startup diagnostic

A dedicated one-shot authorization was used to eliminate the evidence-loss problem from rollback/removal.

The diagnostic guaranteed:

```text
restart=no
candidate start count=1
old Manager stopped
UDP 47111 free
TCP 47112 free
```

The candidate exited with code 2 after roughly seven seconds. The exact startup error was captured:

```text
GH_MQTT_CA_FILE is required when GH_MQTT_TLS=true
```

Classification:

```text
MQTT_CONFIGURATION_FAILURE
ROOT_CAUSE_CONFIDENCE=HIGH
```

This proved a successor runtime configuration omission, not a candidate image defect.

## 8. R1-V2C-S1 — MQTT CA binding correction

A new successor authorization corrected only the Manager→Broker MQTT TLS CA binding.

The correction added the existing Broker CA as a read-only Manager mount and bound `GH_MQTT_CA_FILE` to the in-container CA path.

Verification:

```text
TLS_CHAIN_VERIFY=PASS
TLS_IDENTITY_VERIFY=PASS
CA_CONFIGURATION_ERROR_ABSENT=true
candidate one-shot running for 60s=true
```

The CA correction was semantically isolated:

```text
S1_CA_ONLY_DIFF_BINDING=PASS
```

However the candidate still failed product acceptance because MQTT returned `Not authorized`, and the pairing socket was absent. S1 rolled back successfully without applying final current-main convergence.

## 9. R1-V2C-S1-F1 — latest read-only classification

### 9.1 Manager MQTT identity drift

Recovered Broker result:

```text
MQTT_REASON_CODE=CONNACK_NOT_AUTHORIZED
MQTT_REASON_TEXT=Not authorized
BROKER_REJECTED_CONNECTION=true
```

Candidate metadata:

```text
CANDIDATE_MQTT_CLIENT_ID=greenhouse-manager
CANDIDATE_MQTT_USERNAME_CONFIGURED=false
CANDIDATE_MQTT_PASSWORD_CONFIGURED=true
```

Broker-side Manager identity existed, was enabled, role-bound, and connect-authorized. Password material matched the authorized Manager identity, while the candidate identity binding did not.

Final classification:

```text
MQTT_IDENTITY_BINDING=CLIENT_ID_MISMATCH
MQTT_FAILURE_CLASS=MQTT_AUTH_BINDING_ALREADY_WRONG_IN_BASE_SUCCESSOR
```

No secret value is archived here. The exact authorized identity must be recovered read-only before any correction.

### 9.2 Final-product runtime disabled in base successor

The same read-only classification found:

```text
GH_N3W_RUNTIME_ENABLED=false
GH_N3W_PRODUCT_PAIRING_ENABLED=false
EXPECTED_MANAGER_SERVICE=BASE_MANAGER
PAIRING_SOCKET_EXPECTED=false
```

Therefore the absent pairing socket was expected behavior for the runtime that was actually selected; it was not evidence of a pairing-socket implementation failure.

Classification:

```text
PAIRING_FAILURE_CLASS=PRODUCT_PAIRING_DISABLED_IN_SUCCESSOR_RUNTIME
```

## 10. Current blockers

Only two runtime-binding blockers remain at this archive boundary:

1. **Manager MQTT identity binding drift** in the base successor runtime.
2. **Final N3-W product runtime disabled** in the base successor runtime.

The already-proven MQTT CA correction must be retained.

No source change or image rebuild is justified by current evidence.

## 11. Authorization ledger

The following mutation authorizations were claimed and consumed and must never be replayed:

```text
R1-V2B-CANDIDATE-IMAGE-MATERIALIZATION-AND-RESOLVER-PRECLAIM-20260826-01
R1-V2N-SPARE-T1-NATIVE-ARM64-CANDIDATE-BUILD-AND-PRELIVE-VALIDATION-20260826-01
R1-V2C-SPARE-T1-CURRENT-MAIN-LIVE-CONVERGENCE-20260826-01
R1-V2C-D1-SPARE-T1-CANDIDATE-ONE-SHOT-STARTUP-DIAGNOSTIC-20260826-01
R1-V2C-S1-SPARE-T1-MQTT-CA-BINDING-AND-CURRENT-MAIN-CONVERGENCE-20260826-01
```

Read-only classifiers did not grant or consume new live authority.

## 12. Next route

The next session must begin read-only:

```text
recover exact Broker/DynSec Manager identity authority
+
recover exact current-main final-product runtime environment/path authority
+
preserve the proven MQTT CA binding
```

Only after those authorities are complete should a new, unique live successor authorization be requested for the smallest runtime-binding correction.

Target after that correction:

```text
Spare T1 current-main convergence PASS
→ freeze T1
→ FC4 three-board final physical acceptance
→ N3W_THREE_BOARD_FINAL_PRODUCT_E2E=PASS
```

## 13. Navigation guard

This incident reinforced the Navigator rule:

> Test the product, not the test framework.

Do not return to Mac/QEMU/build tooling, add a generalized executor framework, or start deferred N3-L/control-node work unless a new demonstrated blocker directly requires it.
