# N3-W Board B Radio / Reset Diagnostic — Resume Amendment V2

Date: 2026-09-04

This amendment supersedes only the local toolchain binding section of `N3W_BOARDB_RADIO_RESET_DIAGNOSTIC_RESUME_AMENDMENT_20260904.md`. All source-scope, changed-path, no-install, no-repair, Board/T1, and STOP rules remain unchanged.

## Triggering stop

```text
RESUME_LOCAL_SCOPE=PASS
DIAGNOSTIC_CHANGED_PATH_ORACLE=PASS
HEAD=6c51adb1eb772119ec1a18944b0e88400411ca04
EXISTING_VENV_ESPHOME=FAIL
```

No pytest, ESPHome config/compile, commit/push, Board access, T1 operation, or physical test was executed after that failure. The two allowed local implementation files remain preserved.

## Root cause

The previous amendment incorrectly assumed that the verified Python virtual environment and the verified ESPHome executable share one installation prefix.

Repository authority `docs/development/local-ai-task-splitting-rules.md` records the verified local baseline as:

```text
PYTHON=3.11.9
PYTHON_VENV=$HOME/.venvs/greenhouse-homeassistant-dev
ESPHOME=2026.4.3
ESPHOME_PATH=$HOME/.local/bin/esphome
```

Therefore `${HOME}/.venvs/greenhouse-homeassistant-dev/bin/esphome` is not the authoritative ESPHome path for this workstation.

## Corrected split toolchain authority

Use the existing Python virtual environment only for Python/pytest:

```bash
VENV="${HOME}/.venvs/greenhouse-homeassistant-dev"
PY="${VENV}/bin/python"
```

Use the independently installed, already-verified ESPHome executable for ESPHome operations:

```bash
ESPHOME="${HOME}/.local/bin/esphome"
```

No package installation, upgrade, relinking, or virtual-environment mutation is authorized.

## Read-only environment binding oracle

```bash
set -euo pipefail

VENV="${HOME}/.venvs/greenhouse-homeassistant-dev"
PY="${VENV}/bin/python"
ESPHOME="${HOME}/.local/bin/esphome"

test -x "$PY" || { echo 'EXISTING_VENV_PYTHON=FAIL'; exit 1; }
test -x "$ESPHOME" || { echo 'EXISTING_STANDALONE_ESPHOME=FAIL'; exit 1; }

"$PY" --version
"$PY" - <<'PY'
import importlib.metadata as m
import sys

assert sys.version_info[:2] == (3, 11), sys.version
pytest_v = m.version("pytest")
assert int(pytest_v.split(".", 1)[0]) == 8, pytest_v
print(f"EXISTING_VENV_PYTEST={pytest_v}")
print("EXISTING_PYTEST_BINDING=PASS")
PY

esphome_v="$($ESPHOME version 2>&1 | tr -d '\r')"
printf 'EXISTING_STANDALONE_ESPHOME_VERSION=%s\n' "$esphome_v"
printf '%s\n' "$esphome_v" | grep -F '2026.4.3' >/dev/null || {
  echo 'EXISTING_STANDALONE_ESPHOME_VERSION=FAIL'
  exit 1
}

echo 'EXISTING_SPLIT_TOOLCHAIN_BINDING=PASS'
```

If the executable uses a different version-reporting spelling but clearly reports exact version `2026.4.3`, that exact-version proof is acceptable. Do not modify the executable or environment merely to satisfy formatting.

## Command substitution

Every pytest command in the parent contract must be invoked as:

```bash
"$PY" -m pytest <unchanged original arguments>
```

Every ESPHome config/compile/run command in the parent contract must be invoked as:

```bash
"$ESPHOME" <unchanged original arguments>
```

Do not use shell-default `python`, `pytest`, or `esphome` as authority.

## Optional read-only corroboration

If `gh-local` already exists and is executable, `gh-local status` may be run as additional read-only evidence. Absence of `gh-local` alone is not a failure of this gate because the exact Python/pytest and ESPHome paths above are the controlling oracles.

## Resume sequence

1. Preserve the existing two local implementation paths; no stash/reset/restore/regeneration.
2. `git fetch origin --prune`.
3. Read this V2 amendment from the remote branch.
4. Fast-forward the diagnostic branch only if doing so does not touch the two local implementation paths.
5. Re-run the union changed-path oracle from V1.
6. Run the split toolchain oracle above.
7. Run `git diff --check`.
8. Run the original source-contract pytest and focused existing N3-W pytest through `$PY -m pytest`.
9. Only after those PASS, run original ESPHome config and compile through `$HOME/.local/bin/esphome`.
10. Continue the parent contract only if all source/build gates PASS.

## Unchanged prohibitions

```text
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

Any environment, test, source-contract, config, compile, identity, or baseline failure remains an immediate `STOP` with evidence and no repair.
