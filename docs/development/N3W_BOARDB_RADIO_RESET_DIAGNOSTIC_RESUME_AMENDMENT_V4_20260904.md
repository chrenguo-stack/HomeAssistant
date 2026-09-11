# N3-W Board B Radio / Reset Diagnostic — Resume Amendment V4

Date: 2026-09-04

This amendment supersedes only the post-compile changed-path handling in the prior Board B diagnostic execution contract and V1/V2/V3 amendments. It does not expand product-source scope and does not authorize Board/T1 execution.

## Triggering stop

```text
HEAD_BEFORE_IMPLEMENTATION_COMMIT=725cd011c73d2ab3a14505ddfc5ecbe22a979378
RESUME_LOCAL_SCOPE=PASS
DIAGNOSTIC_CHANGED_PATH_ORACLE=PASS
EXISTING_SPLIT_TOOLCHAIN_BINDING=PASS
DIAGNOSTIC_SOURCE_CONTRACT=PASS
CURRENT_PHASE4_SOURCE_CONTRACT=PASS
ESPHOME_CONFIG=PASS
ESPHOME_COMPILE=PASS
IMPLEMENTATION_CHANGED_PATH_COUNT=3
IMPLEMENTATION_SCOPE_EXACT=false
BOARD_FLASH_EXECUTED=false
T1_MUTATION=false
TERMINAL=STOP_FOR_CHANGED_PATH_SCOPE_FAILURE_BEFORE_COMMIT
```

The third local path was:

```text
firmware/esphome_rc/board_lab/n3w_phase4_physical/.gitignore
```

Remote repository read-back at `725cd011c73d2ab3a14505ddfc5ecbe22a979378` proves that path is not tracked in the diagnostic branch. It appeared only after the successful ESPHome config/compile step.

## Adjudication

```text
ESPHOME_CONFIG=PASS
ESPHOME_COMPILE=PASS
DIAGNOSTIC_SOURCE_REGRESSION_PROVEN=false
PRODUCT_REGRESSION_PROVEN=false
POST_COMPILE_WORKTREE_SIDE_EFFECT=true
IMPLEMENTATION_SCOPE_EXPANSION=false
```

The generated `.gitignore` must never be added to the diagnostic implementation commit merely to satisfy the changed-path oracle.

## Exact bounded cleanup authority

The executor may remove exactly one local file only if every oracle below passes:

```text
CLEANUP_PATH=firmware/esphome_rc/board_lab/n3w_phase4_physical/.gitignore
TRACKED=false
STATUS=UNTRACKED_ONLY
REGULAR_FILE=true
SYMLINK=false
ESPHOME_GITIGNORE_TEMPLATE_MATCH=true
```

No directory cleanup, wildcard cleanup, `git clean`, stash, reset, restore, or cache deletion is authorized.

Use:

```bash
set -euo pipefail
repo="${HOME}/HomeAssistant-local-test"
cd "$repo"

artifact="firmware/esphome_rc/board_lab/n3w_phase4_physical/.gitignore"

test -e "$artifact" || { echo 'ESPHOME_GITIGNORE_SIDE_EFFECT_PRESENT=false'; exit 1; }
test -f "$artifact" || { echo 'ESPHOME_GITIGNORE_REGULAR_FILE=false'; exit 1; }
test ! -L "$artifact" || { echo 'ESPHOME_GITIGNORE_SYMLINK_SAFE=false'; exit 1; }

if git ls-files --error-unmatch -- "$artifact" >/dev/null 2>&1; then
  echo 'ESPHOME_GITIGNORE_TRACKED_UNEXPECTEDLY=true'
  exit 1
fi

status_line="$(git status --porcelain=v1 --untracked-files=all -- "$artifact")"
test "$status_line" = "?? $artifact" || {
  printf 'ESPHOME_GITIGNORE_STATUS_UNEXPECTED=%s\n' "$status_line"
  exit 1
}

python3 - "$artifact" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
expected = """# Gitignore settings for ESPHome

# This is an example and may include too much for your use-case.
# You can modify this file to suit your needs.

/.esphome/

/secrets.yaml

"""
if text != expected:
    print("ESPHOME_GITIGNORE_TEMPLATE_MATCH=false")
    raise SystemExit(1)
print("ESPHOME_GITIGNORE_TEMPLATE_MATCH=true")
PY

rm -- "$artifact"
test ! -e "$artifact"
echo 'ESPHOME_GITIGNORE_BOUNDED_CLEANUP=PASS'
```

The `python3` call above is standard-library-only content validation. It does not install or mutate the toolchain.

## Post-cleanup exact scope oracle

Immediately after the bounded deletion, rerun the V1 union changed-path oracle. It must return exactly these two paths and no others:

```text
firmware/esphome_rc/components/greenhouse_n3w_core/greenhouse_n3w_core.h
tests/n3w_phase4/test_boardb_radio_reset_diag_source_contract.py
```

Required:

```text
IMPLEMENTATION_CHANGED_PATH_COUNT=2
IMPLEMENTATION_SCOPE_EXACT=true
```

Then run:

```bash
git diff --check
```

Do not rerun ESPHome config or compile after cleanup because those commands are already PASS and would recreate the same non-source side effect. Do not rerun broader historical pytest discovery. The previously frozen PASS evidence remains valid as long as the two implementation files are unchanged.

## Commit and push gate

Only after the post-cleanup scope oracle and `git diff --check` PASS:

```bash
git add \
  firmware/esphome_rc/components/greenhouse_n3w_core/greenhouse_n3w_core.h \
  tests/n3w_phase4/test_boardb_radio_reset_diag_source_contract.py

# Verify staged paths are exactly the two implementation paths.
git diff --cached --name-only

git commit -m "diag: instrument Board B radio and reset observability"
git push origin diag/n3w-boardb-radio-reset-observability-20260904
```

No other file may be staged or committed in the implementation commit.

## Terminal boundary

After successful push:

```text
BOARD_B_FLASH=false
BOARD_B_PHYSICAL_TEST=false
BOARD_A_ACCESS=false
BOARD_C_ACCESS=false
T1_MUTATION=false
TERMINAL=STOP_FOR_CURRENT_GITHUB_CI_REVIEW
```

The next gate is current GitHub CI/read-back. Board B flashing remains prohibited until that gate passes.

## Unchanged prohibitions

```text
GIT_CLEAN=false
STASH=false
RESET=false
RESTORE=false
CACHE_DELETE=false
PIP_INSTALL=false
PIP_UPGRADE=false
BREW_INSTALL=false
TOOLCHAIN_MUTATION=false
BOARD_A_ACCESS=false
BOARD_C_ACCESS=false
T1_MUTATION=false
NVS_ERASE=false
FACTORY_RESET=false
CREDENTIAL_ROTATION=false
RADIO_ARBITRATION_REPAIR=false
WIFI_RECONNECT_REPAIR=false
SAME_CHANNEL_FIRST_REPAIR=false
ASYNC_SEND_SEMANTIC_REPAIR=false
AUTO_REPAIR=false
```

Any mismatch in the cleanup oracle, post-cleanup scope oracle, staged-path oracle, commit, or push is an immediate STOP with evidence and no repair.