# T1 Manager Identity Legacy Review Bridge v1

## Purpose

This bridge records an explicit operator decision for one legacy manager identity
rollback whose historical environment and created-directory baselines were never
captured by the old execution package.

It does not convert that legacy result into an audit pass. The original
`rollback_audit_passed=false` result remains unchanged. The bridge only resolves
the required manual review and permits a completely fresh evidence chain to start.

## Accepted audit state

The bridge reruns the repository-owned read-only postrollback audit and accepts
only this exact legacy state:

- schema `gh.m2.t1-manager-identity-postrollback-audit/1`
- `rollback_audit_passed=false`
- `manual_review_required=true`
- `manual_recovery_required=false`
- both `environment_baseline_unavailable=true` and
  `directory_baseline_unavailable=true`
- every definitive rollback, exact-target, service-stability, MQTT socket, and
  anonymous retained-path check is true
- only the unavailable environment and created-directory comparisons are null
- no live service modification, manager migration, credential delivery, anonymous
  closure, secret value, or source path is reported

Any definite failure, partial baseline, drift, unexpected check, or recovery
requirement is rejected. This is intentionally narrower than a general audit
override.

## Operator decision

The command requires this exact confirmation:

`ACCEPT-M2-LEGACY-ROLLBACK-EVIDENCE-GAP`

The confirmation means only:

- accept that the old package cannot retrospectively prove the two missing
  historical baselines;
- retain `rollback_audit_passed=false`;
- resolve the legacy manual-review gate;
- start a new evidence chain that must capture all current baselines.

It does not authorize a production execution, claim or create an authorization,
permit replay of a retired package, or waive any future baseline.

## Live behavior

The bridge reruns the existing read-only T1 audit. It may inspect the three bound
containers, the manager `/proc` socket table, exact transaction targets, and one
anonymous retained subscription. It does not write Compose state, recreate or
restart a service, publish MQTT data, change Home Assistant, or deliver credentials.

The only writes are private mode-0700/0600 decision records under the
operator-selected output directory.

## Output

The output schema is:

`gh.m2.t1-manager-identity-legacy-review-bridge/1`

Each bridge directory contains:

- `audit-report.json`: the rerun redacted legacy audit;
- `operator-decision.json`: the explicit, narrowly scoped acceptance record;
- `manifest.json`: SHA-256 bindings for the transaction journal, rollback manifest,
  rollback archive, audit, confirmation, retained topic, and generated records.

Required result flags include:

- `operator_decision_recorded=true`
- `legacy_baseline_gap_accepted=true`
- `rollback_audit_passed=false`
- `manual_recovery_required=false`
- `manual_review_resolved=true`
- `future_baseline_waiver_enabled=false`
- `ready_for_fresh_evidence_chain=true`
- `ready_for_production_execution=false`
- `authorization_created=false`
- `authorization_claimed=false`
- `manager_identity_migrated=false`
- `node_credentials_delivered=false`
- `preserve_anonymous=true`
- `anonymous_closure_enabled=false`

## CLI

```bash
python3 \
  host/greenhouse-manager/tools/run_t1_manager_identity_migration_legacy_review_bridge.py \
  TRANSACTION_WORKSPACE \
  EXECUTION_PREPARATION_DIRECTORY \
  --output PRIVATE_OUTPUT_DIRECTORY \
  --expected-retained-topic EXPECTED_RETAINED_TOPIC \
  --operator-confirmation ACCEPT-M2-LEGACY-ROLLBACK-EVIDENCE-GAP
```

The success report is path-redacted. The generated private directory is identified
only by `bridge_name` and `manifest_sha256`.
