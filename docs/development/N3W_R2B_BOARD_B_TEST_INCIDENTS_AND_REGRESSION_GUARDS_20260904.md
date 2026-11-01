# N3-W R2B Board B Test Incidents and Regression Guards

Date: 2026-09-04

## Scope

This document is the public-safe incident ledger for the Board B R2 closeout stage of
`N3W_THREE_BOARD_REGRESSION_RETEST`.

It records every material executor/oracle/artifact-integrity issue encountered in the
final Board B runtime-liveness and Broker-observability work. None of the incidents
below proves a Board B or deployed-product regression.

```text
FC4_FINAL_PHYSICAL_ACCEPTANCE=FROZEN_PASS
BOARD_B_R2=FROZEN_PASS
PRODUCT_REGRESSION_PROVEN=false
BOARD_C_ACCESS=false
```

Raw identities, topics, private paths, credentials and raw runtime logs are omitted.

## Incident inventory

### INC-R2B-01 — local executor materialization quote collision

**Phenomenon**

The first local authoring attempt for the Broker observability `_01` shell artifact
failed before artifact materialization because the outer raw triple-single-quoted
Python authoring string was terminated by an inner `r'''` sequence.

**Boundary**

```text
GATE_EXECUTED=false
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
T1_MUTATION=false
```

**Disposition**

The authoring wrapper was rematerialized with a non-colliding outer quoting form and
then required shell syntax, embedded-Python AST/compile and synthetic self-tests.
This is an artifact-authoring/harness incident, not a product failure.

**Existing guard mapping:** executor materialization/transport discipline under
KF-078 and the general exact-executor preflight rules.

---

### INC-R2B-02 — result envelope could report OK while evidence was incomplete

**Phenomenon**

Broker observability attempt `_01` returned a remote result envelope with
`REMOTE_RESULT_OK=true`, while the observation fields remained UNKNOWN and
`EVIDENCE_COMPLETE=false` after a `RuntimeError`.

**Root cause**

The executor result serialization did not make semantic success depend on completion
of the observation object. The high-level adjudicator correctly treated evidence
completeness and UNKNOWN facts as authoritative instead of the envelope boolean.

**Guard**

- `REMOTE_RESULT_OK` must never substitute for evidence-completeness criteria.
- Exception class/hash must be emitted in a secret-safe form.
- Unobserved facts remain `UNKNOWN_NOT_PASS`.
- A claimed authorization remains consumed even when the evidence envelope is
  incomplete.

**Existing guard mapping:** KF-072 (`UNKNOWN` propagation / execution-state
serialization).

---

### INC-R2B-03 — host-path atomic replacement is not live bind-mount authority

**Phenomenon**

Attempt `_01` used an atomic host-path replacement to append temporary Broker debug
configuration. The host pathname changed but the running Broker did not observe the
candidate configuration.

**Important evidence boundary**

The later read-only audit proves current host-path vs live-container inode divergence.
It does not retroactively prove with certainty that `_01` created the divergence.
That historical causal link remains a high-confidence inference only.

**Guard**

Do not treat Docker inspect `Mounts[].Source` pathname identity as sufficient live
object authority for a running single-file bind mount after rename/replacement.

---

### INC-R2B-04 — inode-preserving host write still targeted the wrong live object

**Phenomenon**

Attempt `_02` preserved the host pathname inode and proved the host candidate SHA,
but the running Broker still saw the original bytes.

A subsequent read-only authority audit proved:

```text
BROKER_CONFIG_MOUNT_TYPE=bind
HOST_AND_PROCROOT_SAME_DEV_INODE=false
HOST_AND_PROCROOT_SAME_BYTES=true
PROCROOT_AND_CONTAINER_SAME_BYTES=true
```

**Root cause**

The current Docker-inspect host pathname and the object already bound into the running
Broker namespace were different inodes. The restored bytes happened to be equal,
which hid the authority split during normal operation.

**Guard**

For single-file live bind-mount authority classification, compare at least:

1. Docker inspect mount metadata;
2. host pathname object;
3. `/proc/<running-pid>/root/...` object;
4. container-visible object;
5. dev/inode and byte hash where safe.

---

### INC-R2B-05 — container `test -w` was not actual write authority

**Phenomenon**

Attempt `_03` moved the candidate write to the exact running Broker container
namespace. A preflight `test -w` had succeeded, but the actual truncate/write was
rejected before candidate validation.

Fresh read-only recovery proved:

```text
CONFIG_EXPECTED=true
DYNSEC_EXPECTED=true
BROKER_CONFIG_MOUNT_TYPE=bind
BROKER_CONFIG_MOUNT_RW=false
BROKER_MOUNT_OPTIONS_CONTAINS_RO=true
CONTAINER_TEST_WRITABLE=true
BROKER_RESTART_COUNT=0
MANAGER_RESTART_COUNT=0
```

**Root cause**

The running Broker config is a read-only bind mount. `test -w` reflected pathname
permission semantics but did not prove the mount would accept `O_TRUNC`/write.

**Guard**

- Docker `Mounts[].RW` and live mount options are authoritative for mount
  writeability.
- `test -w` alone must never authorize mutation of a mounted file.
- If the live config mount is RO, do not attempt in-place observability mutation.
- If packet debug is genuinely required in the future, use a separately authorized
  staging successor/recreate design rather than mutating the current RO config.

---

### INC-R2B-06 — packet-level PUBACK capture was over-promoted as a closeout blocker

**Phenomenon**

After the physical Board B runtime observation had already established 10/10 Direct
telemetry, exact replay correlation and same-boot canonical-cursor advancement, the
route temporarily held final R2 closure for a Board-A-style wire/debug PUBACK oracle.

**Adjudication correction**

The durable end-to-end chain already proved application-level QoS1 acceptance,
Broker-to-Manager delivery and Manager durable processing. The separate statement
`WIRE_LEVEL_PUBACK_FRAME_DIRECTLY_OBSERVED=false` remains true, but the missing packet
capture is not a product-failure fact and does not reopen the proven runtime chain.

**Guard**

Do not promote a stronger diagnostic oracle into a mandatory product gate after the
required semantic product property is already proven by independent durable evidence.

**Existing guard mapping:** KF-010 (oracle failure vs product failure separation).

---

### INC-R2B-07 — displayed SHA-256 omitted the final hexadecimal character

**Phenomenon**

One assistant delivery message displayed the `_03` artifact SHA-256 with the final
hexadecimal character `c` omitted. The user independently ran `shasum -a 256`, detected
the mismatch and stopped before execution.

The correct artifact digest was:

```text
81f4d0ef19f76168a22f5d65439d7c93098004ff31a207f5a64d7f9f6f96521c
```

The truncated displayed value is invalidated. No artifact with the truncated digest
was executed.

**Guard**

- SHA-256 display must be exactly 64 hexadecimal characters.
- The locally calculated artifact hash is execution authority; a copied chat value
  that fails length/equality validation must STOP execution.
- Hash comparison must be exact, not prefix-based.

---

## KF-085 — Broker single-file bind-mount live authority / writeability oracle

```text
ID=KF-085
DOMAIN=PHYSICAL_HARNESS
STATUS=RESOLVED
```

**Phenomenon**

Temporary Broker debug-observability executors successively targeted a Docker inspect
host source pathname and the exact container pathname, but candidate configuration
could not be established in the running Broker: the host-path object was not the same
inode as the live mount object, and the live mount itself was read-only.

**Root cause**

The executor treated pathname identity and `test -w` as mutation authority for a
running single-file Docker bind mount. Those are insufficient: a running bind mount
can continue referencing a different inode after host-side pathname replacement, and
pathname permission tests do not override an RO mount.

**Resolution / regression rule**

1. For a running single-file bind mount, classify live authority with Docker inspect,
   running process mount namespace (`/proc/<pid>/root` / mountinfo), and
   container-visible dev/inode/hash.
2. Never use host-path rename/atomic replacement to mutate a config already bound into
   a running container.
3. Before any mounted-file mutation, require Docker mount `RW=true` and live mount
   options consistent with writeability; `test -w` is only auxiliary.
4. If the live mount is RO, mutation is unavailable in the current runtime; use
   read-only evidence or a separately authorized staging/recreate successor.
5. Observability tooling failure remains separate from product failure.

This issue is marked `RESOLVED` because the current route has a complete process and
runtime-authority avoidance rule, but no product source change is required.

## Existing known-failure mappings revalidated

The following existing records remain relevant and already cover other issues seen in
this Board B route:

```text
KF-010=GUARDED   # log/oracle false-negative must not masquerade as product failure
KF-072=OPEN      # UNKNOWN / execution-state serialization discipline
KF-075=GUARDED   # existing-identity credential-recovery product path
KF-078=GUARDED   # executor stdin/TTY/materialization contract
KF-082=GUARDED   # R2B recovery normalization + serial quiescence oracle
```

No new product-domain failure was discovered by the final runtime-liveness or
Broker-observability work.

## Final incident audit

```text
MATERIAL_TEST_INCIDENT_COUNT=7
NEW_PRODUCT_FAILURE_COUNT=0
NEW_SECURITY_FAILURE_COUNT=0
NEW_KF_COUNT=1
NEW_KF_ID=KF-085
KF_085_DOMAIN=PHYSICAL_HARNESS
KF_085_STATUS=RESOLVED
BROKER_CONFIG_EXACT_CURRENT_STATE_PROVEN=true
DYNSEC_EXACT_CURRENT_STATE_PROVEN=true
BROKER_RUNTIME_CONTINUITY_PROVEN=true
MANAGER_RUNTIME_CONTINUITY_PROVEN=true
BOARD_B_R2_CLOSEOUT_REVIEW=PASS
PRODUCT_REGRESSION_PROVEN=false
```

The detailed Board B closure is archived in
`docs/development/N3W_R2B_BOARD_B_R2_CLOSEOUT_REVIEW_PUBLIC_SAFE_20260904.md`.
