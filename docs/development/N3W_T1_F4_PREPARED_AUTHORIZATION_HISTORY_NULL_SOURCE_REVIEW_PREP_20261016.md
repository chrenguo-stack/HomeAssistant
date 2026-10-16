# N3-W T1 F4 Prepared Authorization History Null — Source Review Preparation

Date: 2026-10-16

~~~text
TASK=N3W_T1_F4_PREPARED_AUTHORIZATION_HISTORY_NULL_SOURCE_REPAIR_20261016_01
SOURCE_REVIEW_STATUS=PASS_PENDING_CI
SOURCE_HEAD=72b796671e25c30f0d154788e2a4374f030eb7d1

REAL_T1_STAGE=PREPARED
REAL_T1_TRANSACTION_SHA256=bd1e69c2bce2291e835e8bd341434ad889fbdae8630d9bf897a7fdb27dade1ad
REAL_T1_RUNTIME_ACCEPTANCE_AUTHORIZATION_HISTORY=null

LIVE_MUTATION=false
SUCCESSOR_ACTIVATION_AUTHORIZATION_GRANTED=false
SUCCESSOR_RUNTIME_ACCEPTANCE_AUTHORIZATION_GRANTED=false
~~~

## Review result

The dedicated repair design remains the correct direction: do not weaken generic malformed-history validation and do
not manually edit the transaction. Repair only the exact known PREPARED/null incident through a distinct one-shot
repair command.

The final reviewed source adds:

- `repair-prepared-authorization-history`;
- exact source/manifest/launcher binding to the current PREPARED recovery source;
- exact package-launcher entrypoint validation;
- exact PREPARED/recovery/failure-evidence prestate validation;
- exact requirement that the new repair authorization fields are pristine;
- a custom prior-authorization collector used only because the known defective runtime-acceptance history is null;
- a one-shot repair authorization consumed before launcher replacement;
- launcher-only successor package delta;
- normalization of only `runtime_acceptance_authorization_history: null -> []`;
- return to PREPARED with runtime stopped;
- inclusion of the new repair authorization in future global prior-authorization checks.

Generic `_all_prior_authorization_ids()` and `_accept_runtime()` still reject malformed authorization history.

## Review correction made before closure

Independent review found that an intermediate implementation incorrectly compared the preserved failed-acceptance
source/manifest to the recovered PREPARED source/manifest.

The real durable evidence is:

~~~text
runtime_acceptance_last_failure_source_head=ffcbb1a890e42ac776c6d90000bf3f25195da01d
runtime_acceptance_last_failure_manifest_sha256=4df1d95b0849aa4ca574f31f8fd55e57fe118fba1c5913d2d8b3f96e286ec669
~~~

The source and focused test were corrected to bind against those preserved failed-acceptance values. The candidate
head was advanced and CI restarted.

A second hardening change requires all dedicated repair-authorization fields to be absent before the repair is
eligible, and the global-prior regression test now includes the new repair authorization ID.

## CI state at bounded poll stop

At the third and final bounded poll for the current source head:

~~~text
COMPLETED_SUCCESS:
- M0 vertical slice CI
- M2 private Mosquitto CI
- M2 Dynamic Security CI
- M2 node auth board lab CI
- M2 node auth isolated lab CI
- greenhouse-manager CI
- H3 N2 Stage2B3 Pairing Runtime CI
- C-07 node retirement CI
- M2 manager runtime secret ownership CI

IN_PROGRESS:
- N3W T1 F4 activation source CI
- N3W T1 F4 exact control package
- Public repository safety CI
- M2 node auth native board lab CI

FAILURES=0
~~~

No further polling is performed merely to wait.

## Artifact authority

The earlier exact artifact built from candidate head
`45e61839b31cc5b6e8d8f3b76d55dfdcf136f385` is no longer eligible for live repair because the source was
subsequently corrected and advanced to `72b796671e25c30f0d154788e2a4374f030eb7d1`.

Only an exact artifact built from the final source head may be bound for the live PREPARED history repair.

## Next automatic source-side route

After all final-head CI is PASS:

~~~text
NEXT_ONE_GATE=N3W_T1_F4_PREPARED_AUTHORIZATION_HISTORY_NULL_SOURCE_CLOSURE_AND_EXACT_ARTIFACT_BINDING_20261016_01
T1_ACCESS=false
LIVE_MUTATION=false
~~~

The following live repair gate still requires a new explicit one-shot authorization and is not covered by source
repair or artifact binding.
