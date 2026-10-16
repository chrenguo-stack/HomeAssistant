# N3-W T1 F4 reboot acceptance durable closure — post-reboot binding focused source review closure

Date: 2026-10-16

```text
TASK=N3W_T1_F4_REBOOT_ACCEPTANCE_DURABLE_CLOSURE_POSTREBOOT_BINDING_SOURCE_REVIEW_20261016_01
RESULT=CLOSED_PASS

REPOSITORY=chrenguo-stack/HomeAssistant
MAIN=b12c69be5c1d1d61887e9be4a776f575141d44c6
PR=605
PR_STATE=OPEN_DRAFT
PR_BASE=5368acc1eb50f1fc62bbd7c16ff9e64139131a29

SOURCE_REVIEW_HEAD=19bd98386c4828c0768f2f3936429db8c7a59adf
SOURCE_REVIEW_TREE=f5b66faf690c88d655e01ffc0a5d5ef122b589af
SOURCE_REVIEW_CI=PASS:13/13

CANDIDATE_HEAD_AT_REVIEW_START=78e16f0208047868dba4751fc7c21fecae1d7783
SOURCE_DRIFT_AFTER_REVIEW_HEAD=DOCS_ONLY
DOCS_ONLY_CHANGE=docs/development/N3W_T1_F4_REBOOT_ACCEPTANCE_DURABLE_CLOSURE_POSTREBOOT_BINDING_SOURCE_REVIEW_NEW_CHAT_HANDOFF_V1.0_20261016.md

A1_FINALIZER_EXECUTOR_BINDING=PASS
A2_INSTALLED_CONTROL_MATERIAL_BINDING=PASS
A3_PRE_REBOOT_PROTECTIONS_PRESERVED=PASS
A4_FINALIZER_POSTREBOOT_ORDERING=PASS
A5_TERMINAL_VERIFIER_READONLY_AND_POSTREBOOT_SAFE=PASS
A6_AUTHORIZATION_NO_REPLAY_AND_HASH_CHAIN=PASS
A7_ATOMICITY_AND_INTERRUPTION_SEMANTICS=PASS
A8_CERTIFICATE_STATUS_BINDING=PASS
A9_TEST_COVERAGE=PASS
A10_PACKAGE_BUILDABILITY_FOR_LATER_GATE=PASS

LIVE_RUNTIME_MUTATION=false
T1_ACCESS=false
BOARD_ACCESS=false
MERGE=false
```

## 1. Fresh rebind result

Repository main remains `b12c69be5c1d1d61887e9be4a776f575141d44c6`.

PR #605 remains open, draft and unmerged. Its candidate branch advanced from the exact source-review head
`19bd98386c4828c0768f2f3936429db8c7a59adf` to
`78e16f0208047868dba4751fc7c21fecae1d7783` only by adding the new-chat handoff document. The compare is one commit,
one added documentation file, with no product source, test, workflow or runtime-control change.

The exact source-review head still has 13 pull-request workflow runs and all 13 are completed successfully. The
`N3W T1 F4 exact control package` workflow also completed both package jobs successfully, including
`exact-f4-reboot-successor-control`.

## 2. Focused review findings

### A1 — finalizer executor binding: PASS

The finalizer first validates the staged package manifest and then requires the executing
`n3w_t1_f4_reboot_authority.py` to be the exact file inside that package, with the manifest-bound hash and size.
The accepted terminal record separately preserves finalizer source head, package manifest SHA-256 and executor
SHA-256. This no longer confuses the new staged finalizer with the older installed `CONTROL_READY` control identity.

### A2 — installed-control material binding: PASS

`_verify_installed_control_material_binding()` keeps the frozen F4 transaction SHA-256 exact, checks the install
claim and recovery linkage, verifies the installed control manifest, and verifies every installed target's root
ownership, link count, mode, size and SHA-256. It does not depend on pre-reboot timer state or pre-reboot container
`StartedAt` values.

### A3 — pre-reboot protections: PASS

The stronger `_verify_installed_control()` remains in the pre-reboot install/reboot-claim paths and still layers
`_base_pre_reboot()`, runtime/certificate snapshots, drop-in presence and runtime-guard checks on top of immutable
material binding. The post-reboot split therefore does not weaken pre-reboot callers.

### A4 — finalizer ordering: PASS

Before changing the reboot ledger, the finalizer proves the exact staged executor, exact pending-claim SHA-256,
exact installed control, pending-claim contract and a fresh post-reboot acceptance report. Only after all checks pass
does it construct `REBOOT_ACCEPTED` and atomically replace the reboot claim, followed by exact readback.

### A5 — terminal verifier: PASS

`verify_reboot_accepted()` performs no target write. It verifies the exact staged verifier package, exact accepted
claim hash, installed-control material, embedded report hash, current post-reboot boot identity and finalizer
source/manifest/executor bindings. It uses the post-reboot-safe material helper and no longer calls the pre-reboot
runtime helper.

### A6 — no replay and hash chain: PASS

The original reboot authorization remains claimed, consumed and non-replayable. Finalization requires the exact
current `REBOOT_PENDING` file hash and records that value as `pre_acceptance_claim_sha256` in the terminal record.
The terminal record keeps the original authorization fields unchanged. No second reboot claim or authorization
replay path is introduced.

### A7 — atomicity / interruption / ambiguous success: PASS

The only finalization mutation is the reboot-claim replacement under the existing exclusive lock.
`_atomic_write_record()` writes and fsyncs a temporary file, atomically replaces the target and fsyncs the parent
directory.

An interruption before replacement leaves the exact pending record and can be safely retried against the same pending
hash. An interruption after replacement leaves an accepted record; a blind finalizer replay then fails closed because
the pending hash no longer matches. The separate read-only terminal verifier is the recovery path for an ambiguous
success. No partially written JSON state is accepted.

### A8 — certificate-status evidence binding: PASS

The fresh post-reboot verifier runs the exact installed runtime guard. That guard validates the current certificate
status document and binds its certificate fingerprints to the actual certificate files before returning
`runtime_status_sha256`. The acceptance report carries that status hash, and the finalizer stores the complete report
plus its canonical SHA-256 in the terminal record. Terminal verification rechecks the report hash without incorrectly
requiring the mutable certificate-status file to remain frozen forever.

### A9 — regression tests: PASS

The focused tests cover pending-claim hash mismatch, terminal-verifier read-only behavior, explicit rejection of
pre-reboot-helper reuse, and post-reboot-safe immutable material verification. Separate tests cover reboot-verifier
read-only behavior, boot/transaction guards and package file-set agreement. The exact-package workflow gives an
additional integration check.

Non-blocking test improvement for a later maintenance change: add explicit crash-injection tests around the
finalizer's atomic replace boundary and an explicit acceptance-report certificate-status tamper case. These are useful
hardening tests, but the reviewed source does not depend on them for correctness and no source blocker is proven.

### A10 — later package buildability: PASS

The exact-head `N3W T1 F4 exact control package` workflow passed. Its reboot-successor job checked out the exact PR
head, built the four-file successor package, verified the manifest/source-head binding, sealed the transport tar and
uploaded the artifact. This review does not stage or deploy that artifact.

## 3. Review conclusion

No open source blocker was found at the exact source head. The post-reboot binding defect is closed at source-review
level: the finalizer can execute from an exact staged artifact while continuing to bind the already installed
`CONTROL_READY` material, and the terminal verifier is read-only and post-reboot safe.

This does **not** mean the real T1 durable reboot ledger has been finalized. The last proven real-T1 ledger state
remains `REBOOT_PENDING`; the already consumed reboot authorization must not be replayed.

```text
SOURCE_REVIEW_RESULT=CLOSED_PASS
REAL_T1_DURABLE_REBOOT_CLAIM=REBOOT_PENDING
FINALIZER_EXECUTED_ON_REAL_T1=false
NEXT_ROUTE=DEFINE_EXACT_ARTIFACT_AND_READONLY_PREAUTH_GATE_FOR_LEDGER_FINALIZATION
AUTO_EXECUTE_NEXT_GATE=false
STOP=true
```

No T1 access, live runtime mutation, board access or merge occurred in this gate.
