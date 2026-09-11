# N3-W Board B Radio / Reset Diagnostic — Resume Amendment

Date: 2026-09-04

This amendment is subordinate to:

- `N3W_BOARDB_RADIO_RESET_DIAGNOSTIC_INSTRUMENTATION_GATE_20260904.md`
- `N3W_BOARDB_RADIO_RESET_DIAGNOSTIC_CODEX_EXECUTION_CONTRACT_20260904.md`

It exists only to correct two executor-contract defects encountered after the first source-only attempt. It does not expand the diagnostic scope and does not authorize product repair.

## Frozen facts from first attempt

```text
BRANCH=diag/n3w-boardb-radio-reset-observability-20260904
PREVIOUS_REMOTE_HEAD=cc5a0791d7968249c1a0271374a9cecf0204e2c1
FIRST_PRECLAIM=PASS
BOARD_ACCESS=false
T1_MUTATION=false
FLASH_EXECUTED=false
COMMIT_EXECUTED=false
PUSH_EXECUTED=false
```

Exactly two local implementation paths were produced and must be preserved for resume if their status still matches this allowlist:

```text
firmware/esphome_rc/components/greenhouse_n3w_core/greenhouse_n3w_core.h
tests/n3w_phase4/test_boardb_radio_reset_diag_source_contract.py
```

No other local changed or untracked path is allowed.

## Amendment A — changed-path oracle

The original use of `git diff --name-only` is insufficient because it omits untracked files. Replace every implementation changed-path oracle in this gate with the union of unstaged, staged, and untracked paths:

```bash
actual_paths="$({
  git diff --name-only
  git diff --cached --name-only
  git ls-files --others --exclude-standard
} | LC_ALL=C sort -u)"

expected_paths="$(printf '%s\n' \
  firmware/esphome_rc/components/greenhouse_n3w_core/greenhouse_n3w_core.h \
  tests/n3w_phase4/test_boardb_radio_reset_diag_source_contract.py \
  | LC_ALL=C sort -u)"

printf '%s\n' "$actual_paths"

test "$actual_paths" = "$expected_paths" || {
  printf 'DIAGNOSTIC_CHANGED_PATH_ORACLE=FAIL\n'
  exit 1
}
printf 'DIAGNOSTIC_CHANGED_PATH_ORACLE=PASS\n'
```

This oracle remains valid before and after staging.

## Amendment B — existing Python/ESPHome environment binding

Do not use the invoking shell's default Python as authority and do not install or upgrade any package.

Repository authority `tools/dev/local_environment_policy_20260722_v1.json` defines:

```text
REPOSITORY=~/HomeAssistant-local-test
VIRTUAL_ENVIRONMENT=~/.venvs/greenhouse-homeassistant-dev
PYTHON_RANGE=>=3.11.0,<3.12.0
ESPHOME_EXPECTED=2026.4.3
PYTEST_EXPECTED_MAJOR=8
```

Use only:

```bash
VENV="${HOME}/.venvs/greenhouse-homeassistant-dev"
PY="${VENV}/bin/python"
ESPHOME="${VENV}/bin/esphome"

test -x "$PY" || { echo 'EXISTING_VENV_PYTHON=FAIL'; exit 1; }
test -x "$ESPHOME" || { echo 'EXISTING_VENV_ESPHOME=FAIL'; exit 1; }

"$PY" --version
"$PY" - <<'PY'
import importlib.metadata as m
import sys

assert sys.version_info[:2] == (3, 11), sys.version
pytest_v = m.version("pytest")
esphome_v = m.version("esphome")
assert int(pytest_v.split(".", 1)[0]) == 8, pytest_v
assert esphome_v == "2026.4.3", esphome_v
print(f"EXISTING_VENV_PYTEST={pytest_v}")
print(f"EXISTING_VENV_ESPHOME={esphome_v}")
print("EXISTING_VENV_BINDING=PASS")
PY
```

If this binding fails:

```text
STOP
NO_PIP_INSTALL
NO_PIP_UPGRADE
NO_BREW_INSTALL
NO_TOOLCHAIN_MUTATION
```

For every pytest command in the parent execution contract, invoke the same arguments through:

```bash
"$PY" -m pytest ...
```

For ESPHome config/compile/run operations in the parent execution contract, invoke the same arguments through:

```bash
"$ESPHOME" ...
```

## Resume preclaim

Because the first attempt intentionally left exactly two allowed local implementation changes, the original clean-worktree preclaim is superseded for resume only.

Resume steps:

```bash
set -euo pipefail
repo="${HOME}/HomeAssistant-local-test"
cd "$repo"

test "$(git branch --show-current)" = \
  "diag/n3w-boardb-radio-reset-observability-20260904"

git fetch origin --prune

git merge-base --is-ancestor \
  b683fc62a4126b6f6a0e945db8db68c2584e0e2d \
  HEAD

git merge-base --is-ancestor \
  cc5a0791d7968249c1a0271374a9cecf0204e2c1 \
  origin/diag/n3w-boardb-radio-reset-observability-20260904

actual_paths="$({
  git diff --name-only
  git diff --cached --name-only
  git ls-files --others --exclude-standard
} | LC_ALL=C sort -u)"
expected_paths="$(printf '%s\n' \
  firmware/esphome_rc/components/greenhouse_n3w_core/greenhouse_n3w_core.h \
  tests/n3w_phase4/test_boardb_radio_reset_diag_source_contract.py \
  | LC_ALL=C sort -u)"

test "$actual_paths" = "$expected_paths" || {
  echo 'RESUME_LOCAL_SCOPE=FAIL'
  exit 1
}

echo 'RESUME_LOCAL_SCOPE=PASS'
```

Do not discard, restore, or regenerate the two existing allowed implementation files merely because they are dirty/untracked. Continue with diff review, the corrected changed-path oracle, existing-venv binding, and then the original source-test/build sequence.

The remote amendment commit itself may be read with `git show origin/diag/n3w-boardb-radio-reset-observability-20260904:docs/development/N3W_BOARDB_RADIO_RESET_DIAGNOSTIC_RESUME_AMENDMENT_20260904.md` before local fast-forward. If a fast-forward pull can be performed without touching the two allowed local implementation paths, it is permitted; otherwise remain at the local implementation base and treat the fetched remote amendment as authority.

## Unchanged prohibitions

```text
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

## Resume gate

Only after all of the following are PASS may execution return to the parent contract's ESPHome config/compile stage:

```text
RESUME_LOCAL_SCOPE=PASS
EXISTING_VENV_BINDING=PASS
DIAGNOSTIC_CHANGED_PATH_ORACLE=PASS
SOURCE_CONTRACT_TESTS=PASS
FOCUSED_EXISTING_N3W_TESTS=PASS
```

Any failure means `STOP` with evidence and no repair.
