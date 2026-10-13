# N3-W T1 Golden Master R2C E5-E9 source continuation progress — 2026-10-13

## 1. Current result

```text
TASK=N3W_T1_GOLDEN_MASTER_R2C_READONLY_PROBE_E5_E9_SOURCE_CONTINUATION_20261013_01
R2C_SOURCE_AUTHORITY=a626eb8827a584b7a84f3838beaf08f86766cd73
R2C_SOURCE_CANDIDATE_HEAD=ef81e1e8040ac6bebf3b52ce808deb38ff3f4c0b
E1_E4_INITIAL_SOURCE=IMPLEMENTED
E5_E9_SOURCE=IMPLEMENTED_CI_PENDING
FOCUSED_SOURCE_REVIEW=NO_BLOCKER_FOUND_CLOSURE_DEFERRED_FOR_EXACT_HEAD_CI
R2C_REMOTE_EXECUTOR=NOT_IMPLEMENTED
EXECUTION_READY=false
OS_IDENTITY_SEMANTICS_PROVEN=false
CONTROLLED_CLONE_BOOT_EVIDENCE_REQUIRED=true
T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
MERGE=false
```

The current gate remains repository-only. No T1/SSH access, real Seal mutation, disk capture,
clone acceptance, remote executor execution or PR merge occurred.

## 2. Fresh rebind and drift check

Fresh rebind confirmed:

- repository main: `d423211b6196c2f2f0f01dff072c4f877fbe58ee`;
- PR #541: OPEN / DRAFT / not merged;
- candidate branch: `plan/n3w-t1-full-fresh-install-from-zero-20261010`;
- handoff-time source authority: `a626eb8827a584b7a84f3838beaf08f86766cd73`;
- handoff docs-only advance did not change source, tests or workflows.

The source continuation from `a626...` to `ef81...` adds only the E5-E9 collector/test
package in addition to the already recorded documentation-only handoff advance. No workflow
file changed.

## 3. a626 exact-head CI adjudication

The R2C-focused workflow on exact source `a626...` passed:

- `N3W T1 golden master source CI`: PASS.

A separate full deployable-payload workflow failed after the artifact upload had already
succeeded, at the immediate download-by-artifact-ID step. The log showed the uploaded
artifact ID existed, while the following download action returned zero artifacts. No R2C
source/test failure was present in that run, so it was classified as an Actions artifact
visibility/transport failure rather than an E1-E4 source blocker.

## 4. Focused E1-E4 review

Review of the existing source found no blocker to continuing E5-E9:

- E1 keeps exact target drift fail-closed;
- E2/E3 use bounded static analysis, reject dynamic source/eval/download and do not expose
  raw configuration values;
- E4 classifies and compares machine-id only in memory, does not expose the raw ID and
  remains intentionally incomplete until exact boot/fallback semantics are captured;
- read-only file/command primitives remain bounded and no-follow;
- the evidence schema still forces
  `os_identity_semantics_proven=false`,
  `controlled_clone_boot_required=true`, and
  `disk_capture_ready=false`.

## 5. E5-E9 implementation

Added:

- `tools/n3w_t1_r2c_collectors_e5_e9.py`;
- `tests/tools/test_n3w_t1_r2c_collectors_e5_e9.py`.

Implemented bounded read-only collection for:

- E5: SSH host-key metadata, sshd configuration path classes, key-generation conditions,
  relevant units and listener class; private-key contents are never read.
- E6: NetworkManager/netplan/systemd-network inventory and identity-field classification;
  raw SSID/IP/MAC/UUID/profile values are not emitted, and symlinked/unknown configuration
  fails closed.
- E7: journald storage roots, directory-to-current-machine-id classification, effective
  explicit policy evidence and unit ordering; journal bodies are never read.
- E8: random-seed metadata, owner unit and ordering; seed contents are neither read nor
  hashed, and clone entropy independence remains explicitly unproven.
- E9: bounded unit dependency/condition/timestamp capture. Only Before/After edges count as
  ordering evidence; Wants/Requires/Triggers are recorded separately and never promoted to
  ordering proof. Missing edges/conditions remain UNKNOWN.

The tests cover the privacy boundary, fail-closed custom paths/symlinks, no journal/seed/key
body reads, and the distinction between real ordering and dependency-only relationships.

## 6. Same-gate repairs already made

The first E5-E9 source candidate failed Ruff on three style-only findings. The job log was
read and the exact findings were repaired without changing the evidence contract.

The next candidate passed `N3W T1 golden master source CI`, but
`Public repository safety CI` rejected one test-only MAC-shaped fixture at two locations.
The safety log was read; the fixture was replaced with a non-real placeholder. The current
candidate is therefore `ef81e1e8040ac6bebf3b52ce808deb38ff3f4c0b`.

These were same-gate source/test hygiene repairs, not product/runtime failures.

## 7. Current exact-head CI STOP

For exact candidate `ef81...`, the allowed three observation attempts are exhausted.
The relevant workflows are still queued:

- Golden Master source CI:
  https://github.com/chrenguo-stack/HomeAssistant/actions/runs/38418667594
- Public repository safety CI:
  https://github.com/chrenguo-stack/HomeAssistant/actions/runs/38418668272

Do not poll this exact head again in the same session merely to wait. Source closure remains
pending these exact-head results.

## 8. Boundaries and next step

```text
R2A_SOURCE_REPAIR=CLOSED_SOURCE
R2B_HOST_INDEPENDENT_SOURCE_REPAIR=CLOSED_SOURCE
A1_A10=CLOSED_SOURCE
R2C_E5_E9_SOURCE_CLOSURE=PENDING_EXACT_HEAD_CI
R2C_REMOTE_EXECUTOR=NOT_IMPLEMENTED
EXECUTION_READY=false
ACTUAL_R2C_EVIDENCE_EXECUTION=false
OLD_P2B_AUTHORIZATION_REPLAY=false
REAL_SEAL_MUTATION=false
DISK_CAPTURE=false
CLONE_ACCEPTANCE=false
T1_ACCESS=false
BOARD_ACCESS=false
MERGE=false
STOP=CI_PENDING
```

When the exact-head gate CI is green, the same gate should immediately finish the focused
closure review and archive the final E5-E9 source closure. It must still stop before the
remote-executor or actual target-evidence execution gate.
