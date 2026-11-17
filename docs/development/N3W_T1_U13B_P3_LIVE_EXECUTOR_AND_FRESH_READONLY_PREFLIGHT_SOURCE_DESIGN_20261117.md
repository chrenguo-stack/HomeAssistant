# N3-W T1 U13B P3 live executor + fresh real-T1 read-only preflight source design — 2026-11-17

## Entry authority

```text
P3_CLOSED_PASS_HEAD=dbf8cd1b70365f5d6e1614fdf51a452c04b4e31a
P3_NONLIVE_SOURCE_HEAD=c476770f652d06ab581ad7022a2935e59a597268
P3_NONLIVE_SOURCE_CI=20_OF_20_SUCCESS
P3_EXACT_ARTIFACT_RUN=44089585822
P3_TARGET_BINDING_RUN=44091564730
```

This source stage implements, but does not authorize, the two live-facing
packages needed before P3 physical acceptance.

## Package A — fresh real-T1 read-only preflight

Path:

`tools/execution_packages/n3w/r7a/u13b_p3_fresh_readonly_preflight/`

The package reuses the already proven P1 U13A status-only probe and adds a
second read-only admission probe for P3.

It verifies:

- current Host transaction is the exact terminal U13A authority;
- transaction ID, transaction SHA-256 and historical USB filesystem UUID are exact;
- current Home Assistant image/runtime identity is still 2026.10.4;
- generic/legacy transactions do not contain a non-terminal blocker;
- transaction history metadata, when present, is private and structurally valid;
- the old U13A USB public fingerprint remains historical evidence;
- exactly one different eligible fresh USB candidate is present for the new transaction.

It never calls `prepare_new()`, never writes transaction metadata, never
formats/mounts media, and never changes services/images/HA data.

Current source authority:

```text
REAL_T1_READONLY_EXECUTION_AUTHORIZED=false
NEW_CLEAN_OTA_MUTATION_AUTHORIZED=false
```

Therefore the current package can only run `source-check`.

## Why a second fresh USB is mandatory

The successful U13A USB contains recovery evidence for the prior committed
transaction. Reformatting that medium merely to create the rollback fixture
would destroy historical recovery evidence and violate the clean-independent-
transaction rule.

P3 therefore requires a different fresh USB. The read-only preflight records
the old public fingerprint and requires exactly one distinct candidate.

The future live executor repeats that same-candidate check **before** consuming
its one-shot live authorization. If the candidate changed or disappeared, the
live gate stops before claim.

## Package B — P3 live executor to U11

Path:

`tools/execution_packages/n3w/r7a/u13b_p3_live_to_u11/`

Current source authority:

```text
LIVE_EXECUTION_AUTHORIZED=false
NEW_CLEAN_OTA_MUTATION_AUTHORIZED=false
AUTHORIZATION_GRANTED=false
U13B_LIVE_EXECUTION_AUTHORIZED=false
CONTROLLED_ROLLBACK_MUTATION_AUTHORIZED=false
```

The live path is present for source review/CI only.

When a later separately authorized manifest is created, the sequence is:

```text
fresh real-T1 read-only preflight
-> local exact 2026.10.3 artifact verification
-> revalidate same fresh USB before claim
-> one-shot P3 outer authorization claim
-> stage exact source bundle + exact target archive
-> HaUsbIpcExecutor.submit(PREPARE)
-> archive old terminal transaction
-> fresh U1 transaction
-> fresh USB format + exact target copy/verification -> U4
-> install request -> U5
-> HaUsbU6PredecessorController -> U6
-> HaUsbU7BackupController + ProtectedHaDataBackupProvider -> U7
-> record_recovery_admission -> U8
-> separate product U9 one-shot authorization
-> predecessor capacity release -> U10
-> HaUsbU11TargetInstallController -> U11
-> STOP
```

`record_target_accepted()` and `record_commit()` are intentionally absent.

## Artifact delivery without fake OTA publication

The exact 2026.10.3 artifact currently has GitHub Actions authority, not a
proven public `ota.hahub.top` release.

The source therefore does **not** claim that 2026.10.3 is published as a
normal OTA release and does not change Manager's higher-version rule.

After the future one-shot live claim, the operator-side executor stages the
already hash-bound exact artifact to the T1 private transaction directory.
A narrow `StagedArtifactBackend` overrides only product
`prepare_target()`: it copies the staged archive onto the newly bound USB,
rechecks SHA-256, byte size, tag, Linux/ARM64 portable identity and fsyncs the
destination.

The in-memory HostReleasePolicy URL exists only to satisfy the frozen structural
policy contract. This acceptance backend does not perform an HTTP fetch.

## Exact source delivery

The future live package creates a ZIP containing the exact repository-bound
product modules and stages it only after the outer authorization claim.

Remote execution:

- checks the ZIP SHA-256;
- checks the exact member set;
- verifies every module SHA-256;
- extracts only into the private P3 state root;
- prepends that private exact-source directory to Python import path;
- never rewrites `/opt/HomeAssistant`.

This prevents drift in installed source from silently changing the physical
acceptance implementation.

## One-shot failure behavior

The outer authorization is written before artifact/source staging. Therefore a
post-claim SCP or execution failure consumes the transaction-scoped
authorization and is non-replayable. This is deliberately fail-closed.

A future retry after such a failure requires reconciliation and a new reviewed
authorization; it must not replay the consumed grant.

## Hard stop and authority separation

The successful P3 transaction ends at:

`U11_TARGET_INSTALLED_STARTED`

No U12 acceptance or U13A commit is part of P3.

P3 authorization does not authorize P5 controlled rollback. After a real U11
is obtained, the next stage is a fresh P4 read-only U13B preexecution package
expected to return `ROLLBACK_ELIGIBLE`; only a later separately authorized P5
may enter U13B rollback mechanics.

## Current safety truth

```text
REAL_T1_READONLY_PREFLIGHT_EXECUTED=false
REAL_T1_ACCESS=false
T1_MUTATION=false
USB_MUTATION=false
SERVICE_MUTATION=false
IMAGE_MUTATION=false
HA_DATA_MUTATION=false
NEW_CLEAN_OTA_MUTATION_AUTHORIZED=false
U13B_LIVE_EXECUTION_AUTHORIZED=false
CONTROLLED_ROLLBACK_MUTATION_AUTHORIZED=false
BOARD_ACCESS=false
MERGE=false
```
