# H3/N2 Stage 2D-9R G3R watchdog-repaired payload execution binding

## Decision

This source-only successor implements
`D1-H3N2-STAGE2D9R-G3R-WATCHDOG-REPAIRED-PAYLOAD-EXECUTION-BINDING-20260729-01`.
It layers only above Draft PR #204 at exact HEAD
`8d76634adb171c6492e51a5ebd855bcd52bcf073`.

## Binding model

The new execution package reuses the already reviewed host execution logic and
panic-timeline controller from PR #203, but it does not reuse PR #203's old
firmware payload closure.

The blocking payload inputs are:

- Artifact `8716016864`, ZIP SHA-256
  `71ee1c2bfe951e1e4db833ad4efb96e436ba6c6a0729d52caf641b2294f2d456`;
- PR #204 review binding
  `4da1f873ef0ba0680c56b6782e40dfa48f583e33105b9a5d8f76fce9ae75e74e`;
- immutable build binding
  `4051f5d541898cef742f35aeec757e7fc479f383ae094c43939060b8069f4a55`;
- application SHA-256
  `d60b2e0ccf5013629ee7b7aea017a06387e540380dbf2522415c8876a4cf3032`;
- immutable TAR SHA-256
  `ed8e4c673e89107750743702c7e4f4cb9bfada9c53519edcc4ee31719045b2de`;
- recovery TAR SHA-256
  `9a1b75a39edc4b47d7e54417bdb1e6a07671f37a9100e7f4364e63383e11eeb2`;
- final execution binding SHA-256
  `307fcc23fd606afe9898a7879f2898b012c4bbe5d6c86d8b950a0455ad68789b`.

Every runtime member is included in a new policy-version-2 blocking execution
closure. Any changed, added, missing, or replaced member fails closed.

## Repository drift

`main@64c6b093c3ba6a8476c9392c8d106394b2542fb5` and README blob
`23ccbd3d31c0333924af6d4791f4dde24d1b1b89` are retained as audit bindings.
Repository HEAD remains `AUDIT_ONLY` with `repository_head_enforced=false`.

Consequently, README-only repository drift does not authorize or invalidate
an unchanged execution closure. Runtime, wrapper, launcher, immutable,
recovery, request, toolchain, board, serial, one-shot, and expiry bindings
remain blocking.

## Permanent predecessor disposition

Physical request `...-20260729-09` remains permanently:

- `CONSUMED_FAILED`;
- `PREPARE_RESULT_TIMEOUT`;
- `LOCKED_RECOVERY_COMPLETED`;
- PREPARE count `1`;
- VERIFY count `0`;
- locked recovery succeeded;
- replay and automatic retry prohibited.

The old immutable TAR `3a3e96c...`, old recovery TAR `08cff687...`, old final
binding `38760280...`, and old execution closure `d74b1b19...` are explicit
rejection inputs. They cannot be renamed, rebound, or reused.

## New unauthorized request

The deterministic review package may create only:

`D2-H3N2-STAGE2D9R-G3R-PAYLOAD-HANDOFF-REPAIRED-PHYSICAL-20260729-10`

with `authorized=false`, no authorization record, no issued/expiry window, and
no claim or consumption marker. The request is not executable until a later,
separate exact physical authorization is approved and created.

## Validation layers

- Local/fast: Python compile, focused contract tests, shell launcher test,
  deterministic two-lane packaging, checksum verification, README-only audit
  drift, old-payload rejection, final-binding rejection, and closure tamper.
- GitHub: exact PR #204 base, exact Artifact #8713021622/#8716016864,
  source-only changed-file inventory, repeatable review packaging, and public
  repository safety.
- Live: pending and unauthorized. No board or T1 validation is performed by
  this decision.

## Explicit boundary

This change does not create a physical authorization and does not connect or
enumerate a board, open USB/serial, run esptool, modify Flash/NVS, start a
Broker, execute PREPARE/VERIFY/ACTIVATE/CLEANUP, mark Ready, merge, release,
tag, or deploy.
