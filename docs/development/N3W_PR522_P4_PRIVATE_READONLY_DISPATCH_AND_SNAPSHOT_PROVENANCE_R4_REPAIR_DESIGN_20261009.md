# N3-W P4 Private Read-Only Dispatcher and Snapshot Provenance — R4 Repair Design (2026-10-09)

```text
TASK=N3W_PR522_P4_PRIVATE_READONLY_DISPATCH_AND_SNAPSHOT_PROVENANCE_R4_REPAIR_DESIGN_20261009_01
DOCUMENT_CLASS=DESIGN_ONLY
DESIGN_STATUS=PREPARED_FOR_SOURCE_REPAIR
R3_INDEPENDENT_REVIEW=FAIL_SOURCE_BOUNDARY
R3_REVIEW_RECORD=https://github.com/chrenguo-stack/HomeAssistant/pull/522#issuecomment-6072182681
PR522_EXACT_HEAD=58107b36fc20ccbef014d13cbfb708186395441c
PR474_EXACT_HEAD=ac6f4eaf7f57c84c8c12c89aef12f7e8c9007f1d
PR527_CI_HEAD=30cb3c53d0ac3e82faf5fbfcc0ced7c47915c613
MAIN_AT_DESIGN=d423211b6196c2f2f0f01dff072c4f877fbe58ee
INTEGRATION_CI=26_OF_26_PASS_SOURCE_AND_BUILD_ONLY
R3_SYNTHETIC_CI=60_OF_60_PASS_NOT_LIVE
SOURCE_MUTATION=false
LIVE_T1_ACCESS=false
BOARD_ACCESS=false
REAL_SETUP_SECRET_IMPORT=false
MERGE=false
STOP=true
```

## 1. Problem and accepted boundary

The independent R3 source review found a *source-level execution-boundary defect*, not a proven incident on T1. In `host_readonly.py`, `build_remote_program` checks immutable Git blobs, reads the frozen owner-only preboot snapshot, extracts allowlisted read-only Python AST nodes, and screens the remote source. But the separately callable `remote_snapshot_once(target, expected_target_sha, program, *, runner=...)` accepts any caller-supplied `program` surviving a limited token denylist and sends those bytes to `ssh ... python3 -`. The caller also supplies the target SHA, so a self-computed target SHA proves no trusted host origin.

This bypasses the invariant that *the only program ever dispatched* is the exact program created from verified R3 source and the one frozen five-identity snapshot. Similarly, the dispatcher validates some response flags but does not itself compare the response's `preboot_hashes` against the securely loaded five hashes.

Exact R3 source inputs at PR #522 HEAD:

| File | Frozen Git blob |
| --- | --- |
| `bridge_handoff.py` | `e277949c3db5675bd460124832a382d6a2765539` |
| `host_readonly.py` | `b5732e2ae716c2bba9b5313aadec6cd8abf7b776` |
| `remote_projection.py` | `7b3ba146583b61271b41390736b67207c8d4c14e` |
| `validator.py` | `3b7dc0d085dcda52fda0334840d75d5f8678bc1b` |

Private snapshot authority: exact SHA256 `81a4601421d0f85a6295a8d901fa91692e61c27306c36bc673796f856bbd1e0c`, schema `n3w.kf050.runtime-identity-snapshot/1`, exactly five sorted unique historical hardware-identity hashes. Its path, original identities and contents remain outside public GitHub. No raw QR, pairing ID, Setup Secret, SSH locator, host address or private filesystem path belongs in public evidence.

The legacy `OneShotImporter.import_once` and `ssh_manager_stdin_transport` in R3 already reject every call. Keep them fail-closed. This repair does **not** create a production secret importer.

## 2. R4 core decision — source-bound dispatch, not a new framework

**D1. One production entry point.** Introduce a single bounded *read-only* host runner responsible for the whole chain: verify exact source -> verify private immutable snapshot -> verify independently frozen target/SSH identity -> construct the read-only remote program -> validate its exact bytes at dispatch -> run once -> validate the response against the same private snapshot and current time. A separately callable helper that accepts a free-form `program` must either be removed from production API or perform all of these checks at its own dispatch boundary. Leading underscores, documentation, and a keyword denylist are not security controls. Do not add a general execution DSL or broad reusable SSH runner.

**D2. Pin executed bytes at the final boundary.** Read local source from exact trusted bytes; check pinned Git blob SHA before combining the script; compile and AST-check the complete assembled script. Just before SSH, independently reconstruct the expected script from these same pinned inputs and compare byte-for-byte or via a locally computed SHA256. A caller-supplied digest of a caller-supplied program is not acceptable. No mutable `program` or prebuilt `BASELINE_HASHES` input may bypass source generation. Reject extra prefix/suffix code, Unicode/encoding drift, changed Python imports, arbitrary subprocess invocation, dynamic execution/evaluation, write SQL and Manager-mutating operations *before any network call*. AST/allowlist guards defend against mistakes; the primary provenance guarantee is the immutable exact-source binding. R4 must not claim resistance to a fully compromised local root/operator Python process.

**D3. Protect host identity without publishing locators.** Use the preexisting privately approved exact T1 locator and an independently frozen expected SHA, not `hash(target)` submitted by the same caller as evidence. Require preexisting pinned SSH host key/trusted `known_hosts`, `BatchMode=yes`, `StrictHostKeyChecking=yes`, bounded connect timeout and no interactive fallback; avoid `shell=True`. Validate the remote command is *exactly* the audited Python stdin invocation and does not interpolate a shell fragment, path, or secret. If source/target/SSH authority is absent or changed, STOP before opening SSH. No auto-updating of host keys.

**D4. Reuse the existing frozen private snapshot loader.** Require an absolute, owner-only regular file of mode 0600; reject symlink components; check owner, exact bytes SHA256, schema, count and sorted unique five-hash set. Neither a caller-supplied `frozenset` nor remote-returned five hashes may establish authority. Reject missing or mismatched snapshot before SSH.

**D5. Bind response to the same local baseline.** The dispatcher must reject nonzero remote exit, timeout, oversized stdout/stderr, malformed JSON, unexpected field names/types, non-boolean attestations, unexpected hash encodings, missing old identity, new identity count != 1, or any `preboot_hashes` deviation from the privately loaded five values. Treat `read_at`, `expires_at` as timezone-aware and compare against a fresh trusted local clock with a bounded freshness policy; stale/near-expiry results are STOP, not authorization. The remote attestation flags and hashes are only accepted from the exact SSH host executing the exact source. The QR-to-hardware and pairing hash comparison remains a **separate** future P4-C optical step.

**D6. No unintended writes or unsafe evidence.** Remote execution may inspect Docker/container metadata, current TLS handshake/CA and SQLite with `mode=ro` and `PRAGMA query_only=ON` only. Explicitly allow only the audited fixed read operations, including a strictly scoped Docker socket-stats probe; forbid arbitrary remote commands and any Manager pairing `hello`, import/repair/reset, NVS/flash, DB writing, restart or high-water/replay manipulation. Local output may contain only safe statuses, count, pinned digests and bounded error codes. Never persist raw terminal QR input, secret or full remote stdout/stderr to GitHub, console logs or public CI artifacts. A failure with unknown SSH outcome STOPs; no automatic retry. This stage has no secret and no board.

**D7. Preserve error-class clarity.** Separate `SOURCE_DRIFT`, `BASELINE_DRIFT`, `TARGET_OR_HOST_KEY_DRIFT`, `REMOTE_SOURCE_UNSAFE`, `SSH_UNCERTAIN`, `REMOTE_RUNTIME_DRIFT`, `REMOTE_RESPONSE_INVALID`, and `PENDING_TOO_SHORT`. A policy STOP is neither a production firmware failure nor a Manager pairing failure. Do not mark missing logs as proof of a product defect.

## 3. Implementation scope for the *successor* source-repair gate

- Preferred: narrow edits to `host_readonly.py` and `test_host_readonly.py`, plus a small dedicated R4 synthetic regression workflow update if necessary. Reuse `validator.read_private_baseline` and the existing R3 pinned remote source instead of duplicating a second snapshot validator.
- `remote_projection.py` and `bridge_handoff.py` are immutable inputs by default. Changing either requires an explicit reason, refreshed pinned blobs and a dedicated independent source review; never silently weaken the R3 fail-closed legacy importer.
- Carry code on a **new successor branch based on exact frozen PR #522 HEAD**. Do not amend, force-push, rebase or overwrite PR #522, PR #474 or PR #527. Do not alter `firmware/` or `host/greenhouse-manager/` product code. No live T1 invocation in CI.
- The R4 design does not set a new artifact binding or invalidate the prior exact P3 four-region readback, which remains closed PASS. Prior P4 preboot read-only closure also remains closed PASS for its own instrument.
- A new code-source head and every changed source/test blob must be recorded before independent R4 review. A green simulated CI check is necessary but not a field authorization.

## 4. Required synthetic regression matrix

| ID | Attempt or condition | Required result |
| --- | --- | --- |
| R4-01 | Original R3 pinned bytes + valid *synthetic* private snapshot + trusted dummy target + stub SSH runner | Exactly one checked read-only dispatch; sanitized projection |
| R4-02 | Call dispatcher directly with unrelated Python that lacks every old denylist token | STOP before runner invocation |
| R4-03 | Add harmless-looking prefix, suffix, import, dynamic execution or different byte encoding to a valid generated script | STOP before runner invocation |
| R4-04 | Supply matching SHA256 for an unapproved caller-selected target | STOP before runner invocation |
| R4-05 | Target host-key pin missing, changed or untrusted | STOP; no bypass or key rewrite |
| R4-06 | Snapshot file missing, symlink/ancestor symlink, wrong owner/mode, wrong bytes SHA, bad schema or 4/6 hashes | STOP before runner invocation |
| R4-07 | Remote echoes five syntactically valid but wrong preboot hashes, or a forged all-true health report | STOP: no accepted binding |
| R4-08 | Remote gives unexpected fields/types, malformed JSON, excessive output or nonzero exit | STOP; no retry |
| R4-09 | Remote time untrusted, `read_at` stale/future, expired or insufficient TTL | STOP, no permission inferred |
| R4-10 | Remote source includes import-capable helpers, DB mutator, dynamic command or unsafe subprocess | STOP before runner invocation |
| R4-11 | Timeout or transport loses response after one attempted SSH call | One attempt, uncertain outcome, STOP |
| R4-12 | Caller forges legacy `Binding.live_attested`, approval booleans or starts new `OneShotImporter` | Zero actual secret-import transport calls |
| R4-13 | Positive combined remote code uses only allowed read operations, fixed command arguments and UTF-8 source | Syntax + allowlist PASS with stubbed transport |
| R4-14 | Previously passing 60 R3 synthetic cases and original source contracts | No regression; preserve old suite as separate historical evidence |

All fixtures must use fake identities, fake hosts and fake secret data; do not use actual T1, real board, optical QR or real Setup Secret. Tests must assert `runner.assert_not_called()` on each before-dispatch rejection and inspect the actual final stdin bytes on the positive case. CI PASS cannot establish real current T1 compatibility, production importer readiness or successful first pair.

## 5. Later field orchestrator and P4 readiness — **separate, not implemented by R4**

R4 read-only safe dispatch solves only the source/provenance blocker. The following remain OPEN:

- **A4:** independently authorized, host-only read-only T1 compatibility check of the newly repaired runner and its exact runtime DB mounts, Docker identity, UDS, TLS CA/leaf/hostname. This is *not* the old already-consumed preboot authorization and not a reason to rerun it.
- **A5:** an authoritative fresh Manager pending and TTL check **at the last possible moment before any real secret import**. Policy must preserve the 120-second hello-created window and the current QR/pairing identity. The Manager's own `RegistrationState.PENDING` check is useful but cannot by itself prove time budget and operator provenance. `accepted=true` from import does not prove Manager COMMIT, canonical advancement or KF-050 interruption recovery.
- **A6:** a separate *durable* per-attempt operator authorization claimed before irreversible import, bound to exact boot/board/product identity/pairing and target, with consumed state even when the outcome is unknown; failure/timeout never silently retries or creates a fresh attempt. Real optical intake must be private no-echo; transfer via stdin through Manager-owned `pairing.sock` only, not argv/log/file/chat/GitHub. Real human permission for import must be staged separately **before** boot/hello; at-use operator continuation is a distinct STOP. No new physical boot until the entire TTL-bounded sequence is practically ready.

The relevant planned P4-A through P4-F stages remain deferred. Never infer runtime `hardware_id` from ROM silicon binding; only bind the real product LCD `GHN3W2` QR to the exactly one newly created Manager pending registration. The old five-identity snapshot is historical immutable input; it must not be reset, fabricated, or replaced.

## 6. Gate decisions and closure criteria

```text
R4_DESIGN=PASS_DESIGN_ONLY
R4_CODE_IMPLEMENTED=false
R4_SYNTHETIC_EXECUTED=false
R4_INDEPENDENT_SOURCE_REVIEW=NOT_EXECUTED
A1_LEGACY_IMPORT_PATH=CLOSED_ONLY_DISABLED
A2_REMOTE_PROGRAM_DISPATCH=BLOCKER_OPEN_PENDING_R4_CODE
A3_SNAPSHOT_END_TO_END=OPEN_PENDING_R4_CODE
A4_REAL_T1_COMPATIBILITY=OPEN_NO_ACCESS
A5_PENDING_TTL_TIME_OF_USE=OPEN
A6_DURABLE_OPERATOR_ONESHOT_IMPORT=OPEN
P3_FOUR_REGION_READBACK=CLOSED_PASS_NO_REPLAY
P4_PREBOOT_READONLY=CLOSED_PASS_NO_REPLAY
P4_FIRST_NORMAL_BOOT_AUTHORIZED=false
P4_REAL_SETUP_SECRET_IMPORT_AUTHORIZED=false
PR522_MERGE=false
PR474_MERGE=false
PR527_MERGE=false
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false

NEXT_ONE_GATE=N3W_PR522_P4_PRIVATE_READONLY_DISPATCH_AND_SNAPSHOT_PROVENANCE_R4_SOURCE_REPAIR_AND_SYNTHETIC_REGRESSION_20261009_01
NEXT_GATE_CLASS=NONLIVE_SOURCE_REPAIR_ONLY
NEXT_GATE_SOURCE_FOCUS=host_readonly.py;test_host_readonly.py
NEXT_GATE_PASS_IF=DISPATCH_CANNOT_BYPASS_EXACT_SOURCE_SNAPSHOT_TARGET_BINDING_AND_ALL_NEGATIVE_TESTS_PASS
NEXT_GATE_FAIL_IF=ANY_UNPINNED_CODE_CAN_REACH_SSH_OR_ANY_FORGED_BASELINE_RESULT_CAN_PASS
NEXT_GATE_STOP=AFTER_EXACT_SOURCE_SYNTHETIC_CI_AND_INDEPENDENT_REVIEW_HANDOFF
AUTO_EXECUTE_NEXT_GATE=false
```

Source mutation, SSH/live T1 preflight, board power/boot, credential import, and merges are not authorized by this *design* document. Its sole permitted repository change is a public-safe documentation commit/PR, independently versioned from the frozen PR #522 source.
