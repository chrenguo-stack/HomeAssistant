# N3-W Board B Radio / Reset Diagnostic — Resume Amendment V3

Date: 2026-09-04

This amendment supersedes only the open-ended focused-test discovery clause of the parent diagnostic execution contract. V1 changed-path rules, V2 split-toolchain binding, diagnostic source scope, no-repair rules, Board/T1 boundaries, and all STOP conditions remain in force.

## Triggering stop

```text
RESUME_LOCAL_SCOPE=PASS
DIAGNOSTIC_CHANGED_PATH_ORACLE=PASS
HEAD=520e7c7da47ace686a1f07b74ed1285102797052
EXISTING_SPLIT_TOOLCHAIN_BINDING=PASS
Python=3.11.9
pytest=8.4.2
ESPHome=2026.4.3
SOURCE_CONTRACT_TESTS=PASS
FOCUSED_DISCOVERY_RESULT=24 passed, 6 failed
```

No ESPHome config/compile, commit/push, Board access, T1 operation, or physical test was executed after the focused-test failure. The two allowed local implementation files remain preserved.

## Adjudication

The six failures are not accepted as evidence of a regression in the diagnostic implementation.

Read-only repository review shows:

1. `tests/n3w_p4b/test_n3w_p4b_contract.py` is a historical P4B contract bound to the 2026-08-07 stage entry (`base_sha=4f9242efc8c1b4776e4cc46c66ebc85b6e4ffe57`) and asserts pre-activation conditions such as empty `GreenhouseN3wCore::setup()/loop()`.
2. The accepted N3-W telemetry simplification architecture explicitly removes Relay reassembly, `ChildRelayCache`, DATA_FRAGMENT/RECEIPT_ACK/retry/RESEND/REORDER ownership from ordinary periodic telemetry.
3. Current `greenhouse-manager CI` scopes changes to `greenhouse_n3w_core` against `tests/n3w_phase3/**` and `tests/n3w_phase4/**`; it does not use `tests/n3w_p4b/**`, `tests/n3w_p5/**`, or old S5 contracts as the current simplified-core regression surface.
4. Current Phase 4 source contracts explicitly assert that the simplified product runtime excludes `ChildRelayCache`, DATA_FRAGMENT, RECEIPT_ACK, RESEND and REORDER.
5. Historical S5 files may still reference `greenhouse_n3w_product_runtime`, while that component directory is no longer present in the current tree. Those references are not a valid current-core test selector.

Therefore:

```text
FOCUSED_TEST_SELECTION_DEFECT=true
STALE_HISTORICAL_CONTRACT_FAILURES=true
DIAGNOSTIC_SOURCE_REGRESSION_PROVEN=false
PRODUCT_REGRESSION_PROVEN=false
```

## Root cause

The parent contract used an open-ended instruction:

```text
run any existing focused host/source tests that cover the N3-W simple product runtime and ESP-NOW driver if discoverable
```

That rule is too broad for a repository containing archived or quarantined historical contracts. Test discovery must be exact and current-authority bound.

## Exact current local test allowlist

For this diagnostic gate, local pytest execution is limited to exactly:

```text
tests/n3w_phase4/test_boardb_radio_reset_diag_source_contract.py
tests/n3w_phase4/test_phase4_source_contract.py
```

Invoke with the V2 Python authority:

```bash
"$PY" -m pytest -q \
  tests/n3w_phase4/test_boardb_radio_reset_diag_source_contract.py

"$PY" -m pytest -q \
  tests/n3w_phase4/test_phase4_source_contract.py
```

No additional pytest discovery is authorized for the local pre-compile gate.

Explicitly excluded from this gate's local regression decision:

```text
tests/n3w_p4b/**
tests/n3w_p5/**
old S5 / greenhouse_n3w_product_runtime contracts
historical exact-base / stage-entry contracts outside tests/n3w_phase4/**
```

This exclusion does not delete or repair those tests. Their independent maintenance is outside this diagnostic gate.

## Build gate

Because both exact Phase 4 source contracts already passed with the current two local implementation files and V2 toolchain binding, the executor may re-run them once after reading this amendment, then proceed directly to the parent ESPHome Phase 4 physical harness config/compile steps.

Use only:

```bash
ESPHOME="${HOME}/.local/bin/esphome"
```

and retain the exact target/arguments from the parent contract.

Required local build closure before commit:

```text
RESUME_LOCAL_SCOPE=PASS
DIAGNOSTIC_CHANGED_PATH_ORACLE=PASS
EXISTING_SPLIT_TOOLCHAIN_BINDING=PASS
DIAGNOSTIC_SOURCE_CONTRACT=PASS
CURRENT_PHASE4_SOURCE_CONTRACT=PASS
ESPHOME_CONFIG=PASS
ESPHOME_COMPILE=PASS
```

## Remote CI boundary

After local config/compile PASS and exact diff review:

1. commit only the two implementation paths allowed by the parent contract;
2. push the diagnostic branch;
3. STOP before any Board B flash.

Board B flash is intentionally moved behind a current GitHub CI review gate. The high-level model will open or inspect the PR and require the current `greenhouse-manager CI` Phase 4/current-core checks before authorizing physical flashing.

This prevents stale local historical suites from blocking the diagnostic build while still preserving a clean current-environment regression check before Board mutation.

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

Any failure in the exact Phase 4 source tests, ESPHome config/compile, changed-path review, or source-scope review remains an immediate `STOP` with evidence and no repair.
