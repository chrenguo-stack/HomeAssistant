# FC4 R1-V2C-S1-F1 Known-Failures Addendum

- Date: 2026-08-26
- Scope: Spare-T1 current-main convergence
- Baseline: `1f80d54ff5f84056e0559a7d8cc80427c5e0bb14`
- Product source mutation: **false**
- Status: **public-safe pending reconciliation into the canonical known-failures index**

> This addendum intentionally does **not** allocate global `KF-###` IDs. Multiple documentation PRs currently touch the canonical `KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`; allocating IDs independently would create avoidable collisions. These incidents are durable and must be folded into the canonical index when those documentation branches are reconciled.

## A. Local cross-architecture ARM64 build path produced non-diagnostic failure

**Primary domain:** INFRASTRUCTURE / PHYSICAL_HARNESS boundary

### Symptom

An x86_64 host using QEMU binfmt and the legacy Docker builder attempted the exact current-main `linux/arm64` Manager build. The first compound `RUN` exited with code 2, but no subcommand-specific stderr survived.

### Root cause

Not proven. The available evidence was insufficient to distinguish QEMU/runtime, legacy-builder, or shell/subcommand behavior.

### Important negative evidence

A later native ARM64 build of the same production Dockerfile and exact source on Spare T1 passed completely.

Therefore the local failure is **not evidence of a product Dockerfile defect**.

### Fix / avoidance rule

For FC4 target acceptance, prefer native ARM64 build on the production-equivalent target class instead of extending the Mac/QEMU/buildx/Colima tooling branch.

Do not modify product source merely to make the local emulation path pass.

### Regression guard

When a cross-architecture build fails before producing actionable command-level evidence:

```text
1. distinguish product-source failure from emulation/tooling failure;
2. verify exact source on native target architecture if available;
3. if native target passes, stop treating the emulation route as product authority.
```

Status: **RESOLVED for FC4 route by native target build**.

---

## B. TLS-enabled Manager successor omitted `GH_MQTT_CA_FILE`

**Primary domain:** INFRASTRUCTURE

### Symptom

The exact current-main Manager candidate exited during startup with:

```text
GH_MQTT_CA_FILE is required when GH_MQTT_TLS=true
```

### Root cause

The successor runtime enabled Manager→Broker MQTT TLS but did not bind the authoritative Broker CA into the Manager runtime or set `GH_MQTT_CA_FILE`.

### Fix

Bind the existing authoritative Broker CA read-only into the Manager container and set `GH_MQTT_CA_FILE` to the in-container CA path.

The correction was verified with:

```text
TLS_CHAIN_VERIFY=PASS
TLS_IDENTITY_VERIFY=PASS
CA_CONFIGURATION_ERROR_ABSENT=true
```

### Regression guard

Any successor/preflight with:

```text
GH_MQTT_TLS=true
```

must fail before live cutover unless all of the following are proven:

```text
GH_MQTT_CA_FILE is configured
CA path is present and readable in-container
certificate chain verification passes
hostname/IP identity verification passes
```

Never fix this by disabling hostname verification or weakening TLS.

Status: **RESOLVED in S1 correction; guard still needs canonical integration**.

---

## C. Base successor Manager MQTT identity did not match Broker authority

**Primary domain:** INFRASTRUCTURE / SECURITY binding

### Symptom

After TLS CA correction, the candidate remained alive but Broker returned:

```text
CONNACK_NOT_AUTHORIZED
Not authorized
```

Read-only classification found:

```text
CANDIDATE_MQTT_CLIENT_ID=greenhouse-manager
CANDIDATE_MQTT_USERNAME_CONFIGURED=false
CANDIDATE_MQTT_PASSWORD_CONFIGURED=true
BROKER_MANAGER_IDENTITY_EXISTS=true
BROKER_MANAGER_IDENTITY_ENABLED=true
BROKER_MANAGER_IDENTITY_ROLE_BOUND=true
BROKER_MANAGER_IDENTITY_CONNECT_ALLOWED=true
CANDIDATE_PASSWORD_MATERIAL_EQUALS_AUTHORIZED_MANAGER_IDENTITY=true
MQTT_IDENTITY_BINDING=CLIENT_ID_MISMATCH
```

### Root cause

The base successor runtime carried an incorrect Manager MQTT identity binding. The problem predated the S1 CA-only correction.

### Current fix state

**Not yet closed at this archive boundary.**

The exact authorized Manager identity must first be recovered read-only from Broker/DynSec and the stable old Manager runtime. No credential value should be printed or rotated.

### Fix / avoidance rule

Before any successor Manager cutover, compare safe identity metadata against Broker authority:

```text
client-id binding
username configured/binding
password-source equality without secret disclosure
identity enabled
role bound
connect permission
```

Do not respond to `Not authorized` by creating a new identity, weakening ACLs, enabling anonymous access, or rotating credentials without an explicit security reason.

Status: **OPEN**.

---

## D. Base successor disabled final N3-W product runtime

**Primary domain:** INFRASTRUCTURE

### Symptom

The current-main candidate ran, but the final product pairing socket was absent.

Read-only classification found:

```text
GH_N3W_RUNTIME_ENABLED=false
GH_N3W_PRODUCT_PAIRING_ENABLED=false
EXPECTED_MANAGER_SERVICE=BASE_MANAGER
PAIRING_SOCKET_EXPECTED=false
```

### Root cause

The base successor runtime never enabled the final N3-W runtime/product-pairing selector. The socket absence was therefore expected behavior for the selected service and not a socket implementation defect.

### Current fix state

**Not yet closed at this archive boundary.**

The exact existing final-product runtime authority must be recovered before enabling the selectors. Required values include the pairing Manager identity, provisioning identity, node-Broker TLS settings, private state paths, and pairing-socket path.

### Fix / avoidance rule

A final-product successor must explicitly prove, before live cutover:

```text
GH_N3W_RUNTIME_ENABLED=true
GH_N3W_PRODUCT_PAIRING_ENABLED=true
expected service = SIMPLIFIED_PRODUCT_PAIRING_MANAGER
all required product-runtime environment/path bindings are complete
```

Do not mechanically set the two booleans to `true` without proving the dependent configuration authority.

Status: **OPEN**.

---

## E. Diagnostic evidence must be captured before rollback/removal

**Primary domain:** PHYSICAL_HARNESS

### Symptom

The first failed current-main live convergence rolled back cleanly, but the failed candidate container had already been removed and its startup error could not be recovered. Multiple read-only analyses could only classify the failure as evidence-insufficient.

### Root cause

Rollback/removal happened before durable capture of candidate `logs + inspect + exit state`.

### Fix

The later one-shot diagnostic used:

```text
restart=no
candidate start count=1
capture logs/inspect before removal
rollback only after evidence is durable
```

This immediately exposed the `GH_MQTT_CA_FILE` startup error.

### Regression guard

For a bounded candidate startup diagnostic:

```text
start once
→ do not auto-restart
→ do not remove on failure
→ capture logs + inspect + exit code/OOM/signal
→ freeze evidence hashes
→ only then rollback/remove
```

Status: **RESOLVED as execution practice; canonical guard integration pending**.

---

## Reconciliation note

When the canonical `KNOWN_FAILURES_AND_REGRESSION_GUARDS.md` documentation branches are reconciled, fold these incidents into the primary index without duplicating an existing root cause. Preserve the canonical rule that the same underlying root cause should not receive multiple IDs merely because it appeared under multiple authorization names.
