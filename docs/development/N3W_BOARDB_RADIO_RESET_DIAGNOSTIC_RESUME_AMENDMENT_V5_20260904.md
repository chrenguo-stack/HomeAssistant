# N3-W Board B Radio / Reset Diagnostic — Resume Amendment V5

Date: 2026-09-04

This amendment supersedes only the V4 generated `.gitignore` content-template oracle. It keeps all prior source scope, split-toolchain, exact test allowlist, no-auto-repair, Board/T1 prohibition, and post-push STOP boundaries unchanged.

## Triggering stop

```text
HEAD_BEFORE_IMPLEMENTATION_COMMIT=0bff70a1e58b552ff4b964891218061e6ea29ce0
IMPLEMENTATION_COMMIT=NONE
REMOTE_HEAD_AFTER_PUSH=0bff70a1e58b552ff4b964891218061e6ea29ce0
ESPHOME_GITIGNORE_TEMPLATE_MATCH=false
ESPHOME_GITIGNORE_BOUNDED_CLEANUP=NOT_EXECUTED
IMPLEMENTATION_CHANGED_PATH_COUNT=3
IMPLEMENTATION_SCOPE_EXACT=false
STAGED_SCOPE_EXACT=false
DIAGNOSTIC_SOURCE_CONTRACT=PASS
CURRENT_PHASE4_SOURCE_CONTRACT=PASS
ESPHOME_CONFIG=PASS
ESPHOME_COMPILE=PASS
BOARD_FLASH_EXECUTED=false
T1_MUTATION=false
TERMINAL=STOP_FOR_GITIGNORE_TEMPLATE_MISMATCH
```

## Adjudication

The V4 exact text-template requirement was an over-constrained build-side-effect oracle. The relevant authority facts are provenance and Git status, not byte-for-byte content of an untracked build-generated helper file.

Freeze:

```text
STOP_SAFETY_BEHAVIOR=CORRECT
V4_TEMPLATE_ORACLE_OVERCONSTRAINED=true
PRODUCT_REGRESSION_PROVEN=false
DIAGNOSTIC_SOURCE_REGRESSION_PROVEN=false
ESPHOME_CONFIG=PASS
ESPHOME_COMPILE=PASS
POST_COMPILE_WORKTREE_SIDE_EFFECT=true
IMPLEMENTATION_SCOPE_EXPANSION=false
```

The path remains outside the implementation allowlist and MUST NOT be staged or committed.

## Provenance-based bounded cleanup authority

The executor may remove exactly this one path:

```text
firmware/esphome_rc/board_lab/n3w_phase4_physical/.gitignore
```

Only if all of the following are true at execution time:

```text
PATH_EXACT=true
TRACKED=false
STATUS=UNTRACKED_ONLY
REGULAR_FILE=true
SYMLINK=false
```

No content-template match is required. File contents MUST NOT be used to expand source authority, and the file MUST NOT be committed.

Use exactly:

```bash
set -euo pipefail
repo="${HOME}/HomeAssistant-local-test"
cd "$repo"

artifact="firmware/esphome_rc/board_lab/n3w_phase4_physical/.gitignore"

test -e "$artifact" || { echo 'BUILD_SIDE_EFFECT_PRESENT=false'; exit 1; }
test -f "$artifact" || { echo 'BUILD_SIDE_EFFECT_REGULAR_FILE=false'; exit 1; }
test ! -L "$artifact" || { echo 'BUILD_SIDE_EFFECT_SYMLINK=false'; exit 1; }

if git ls-files --error-unmatch -- "$artifact" >/dev/null 2>&1; then
  echo 'BUILD_SIDE_EFFECT_TRACKED_UNEXPECTEDLY=true'
  exit 1
fi

status_line="$(git status --porcelain=v1 --untracked-files=all -- "$artifact")"
test "$status_line" = "?? $artifact" || {
  printf 'BUILD_SIDE_EFFECT_STATUS_UNEXPECTED=%s\n' "$status_line"
  exit 1
}

echo 'BUILD_SIDE_EFFECT_PROVENANCE_CLASS=ESPHOME_POST_COMPILE_UNTRACKED'
rm -- "$artifact"
test ! -e "$artifact"
echo 'BUILD_SIDE_EFFECT_BOUNDED_CLEANUP=PASS'
```

Explicitly prohibited:

```text
GIT_CLEAN=false
WILDCARD_DELETE=false
DIRECTORY_DELETE=false
CACHE_DELETE=false
STASH=false
RESET=false
RESTORE=false
```

## Post-cleanup implementation scope

Immediately rerun the V1 union changed-path oracle. It MUST return exactly these two implementation paths and no others:

```text
firmware/esphome_rc/components/greenhouse_n3w_core/greenhouse_n3w_core.h
tests/n3w_phase4/test_boardb_radio_reset_diag_source_contract.py
```

Required:

```text
IMPLEMENTATION_CHANGED_PATH_COUNT=2
IMPLEMENTATION_SCOPE_EXACT=true
```

Then:

```bash
git diff --check
```

Do not rerun pytest, ESPHome config, or ESPHome compile if the two implementation files are byte-identical to the previously validated versions. Their prior PASS evidence remains authoritative for this resume.

## Commit and push

Stage only the two implementation paths:

```bash
git add \
  firmware/esphome_rc/components/greenhouse_n3w_core/greenhouse_n3w_core.h \
  tests/n3w_phase4/test_boardb_radio_reset_diag_source_contract.py
```

Verify staged scope exactly:

```bash
git diff --cached --name-only
```

It MUST contain exactly the two paths above.

Then:

```bash
git commit -m "diag: instrument Board B radio and reset observability"
git push origin diag/n3w-boardb-radio-reset-observability-20260904
```

No other file may be staged or committed.

## Development/test-method refinement frozen by this incident

For future gates, deviations MUST be classified before deciding whether to STOP:

```text
SOURCE_MUTATION_UNEXPECTED           -> STOP
CURRENT_CONTRACT_TEST_FAILURE        -> STOP
BUILD_FAILURE                        -> STOP
TOOLCHAIN_DRIFT                      -> STOP
GENERATED_BUILD_SIDE_EFFECT          -> RECORD / CLEAN BOUNDEDLY / CONTINUE
STALE_HISTORICAL_TEST_SELECTION      -> EXCLUDE / RECORD / CONTINUE
```

This classification does not weaken source or live-mutation boundaries. It prevents known build artifacts and retired historical contracts from masquerading as product regressions.

Future development should prefer a disposable validation worktree for build/config/compile activity while keeping the authoritative source worktree commit-clean. That process change is advisory for later gates; this V5 does not create or mutate an additional worktree.

## Terminal boundary

After successful implementation push, STOP immediately for remote diff/read-back and current GitHub CI review:

```text
BOARD_B_FLASH=false
BOARD_B_PHYSICAL_TEST=false
BOARD_A_ACCESS=false
BOARD_C_ACCESS=false
T1_MUTATION=false
TERMINAL=STOP_FOR_CURRENT_GITHUB_CI_REVIEW
```

Board B flashing remains prohibited until the remote implementation commit is read back and current required CI passes.
