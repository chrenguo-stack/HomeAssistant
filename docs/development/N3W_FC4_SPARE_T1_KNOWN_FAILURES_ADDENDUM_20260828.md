# N3-W / FC4 Spare T1 Known-Failures Addendum

Date: 2026-08-28  
Status: public-safe addendum pending central KF-ID reconciliation

## Why this addendum exists

At the time of this archive, two already-open documentation PRs independently allocate `KF-068` to different issues. To avoid silently creating a third numbering conflict, this document records the Spare T1 convergence failures under provisional identifiers `ST1-RG-*`.

These identifiers are **not** permanent `KF-*` allocations. Before merging these records into `KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`, the open PR numbering conflict must be reconciled and final unique KF IDs assigned.

## Provisional regression records

| ID | DOMAIN | Phenomenon | Root cause | Fix / regression guard | Status |
|---|---|---|---|---|---|
| ST1-RG-01 | SECURITY / INFRASTRUCTURE | A successful Mosquitto DynSec password reconciliation changed the target credential field and also advanced top-level `changeIndex`; an earlier semantic comparator treated the extra top-level change as unexpected | The comparator modeled only the business-object mutation and omitted Mosquitto's state-version transition | For state-changing DynSec control operations, validate both the target semantic mutation and the expected `changeIndex` increment while asserting all unrelated state is unchanged | GUARDED |
| ST1-RG-02 | INFRASTRUCTURE | A successor passed static Manager identity/product-runtime gates but failed live MQTT authorization | The gate did not compare **effective** Manager MQTT endpoint/CA values with a known-successful product-equivalent authority; Manager `GH_MQTT_*` semantics were conflated with node-facing `GH_N3W_NODE_BROKER_*` semantics | Static runtime gates must resolve effective values, compare them to a successful authority, preserve the two Broker-configuration domains, and prove the corrected gate rejects the known-bad predecessor | GUARDED |
| ST1-RG-03 | PHYSICAL_HARNESS / INFRASTRUCTURE | A corrected product deployment was rolled back after a stability validator produced a Python `SyntaxError` during a read-only probe | Nested remote shell/Python quoting corrupted the validator command; the failure was validator infrastructure, not a product predicate failure | Preflight an exact validator artifact/argv contract; avoid nested remote quoting; classify validator infrastructure failures separately from product predicate failures; elapsed wall time alone never proves stability | GUARDED |
| ST1-RG-04 | PHYSICAL_HARNESS | A failed-deployment closure exposed terminal post-rollback state in fields that appeared to describe the pre-rollback candidate | The closure schema lacked explicit lifecycle namespaces and therefore allowed evidence from different phases to be conflated | Separate `CANDIDATE_*`, `PRE_ROLLBACK_*`, `FINAL_*`, and `POST_ROLLBACK_*`; never infer candidate health from rollback-terminal fields or vice versa | GUARDED |
| ST1-RG-05 | PHYSICAL_HARNESS / SECURITY | A candidate completed a valid 60-second stability window but the transaction rolled back because the final provisioning probe used a non-authorized Client ID | The final probe reconstructed identity parameters after claim instead of reusing the already-proven preflight probe contract | Freeze and self-test the exact probe identity/argv before claim; final validation must reuse the same contract without changing Client ID or endpoint semantics | GUARDED |

## Cross-cutting rules

- A consumed live authorization is terminal even when rollback succeeds; later attempts require a new unique authorization.
- Credential/DynSec reconciliation that has already become the production authority is not rolled back merely because a later Manager deployment fails.
- A validator/harness failure can require transaction rollback without proving a product defect.
- Known-bad predecessor artifacts remain evidence and must not be silently reused.
- Public archive material must exclude passwords, password-derived verifiers, Setup Secrets, private network addresses, private host paths, raw DynSec content, raw board identifiers, and raw private evidence.

## Central-index reconciliation gate

Before integrating these records into `KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`:

```text
OPEN_PR_KF_ID_COLLISION_RECONCILED=true
FINAL_KF_IDS_UNIQUE=true
NO_EXISTING_KF_ID_REUSED=true
```

Until then, `ST1-RG-01` through `ST1-RG-05` are the repository archive authority for this Spare T1 convergence failure set.
