# N3W OTA Guard ROM Identity Contract Repair R1 — 2026-09-11

## Status

```text
REPAIR=N3W_OTA_GUARD_ROM_IDENTITY_CONTRACT_REPAIR_R1
REPAIR_RESULT=PASS_HOST_REVIEW_AND_CI
PHYSICAL_USE_AUTHORIZED=false
BOARD_ACCESS=false
OLD_PHYSICAL_AUTHORIZATION_CONSUMED=true
OLD_PHYSICAL_AUTHORIZATION_REPLAY_PERMITTED=false
NEXT_ONE_GATE=HOST_ONLY_REPAIR_REPLAY_AGAINST_CONSUMED_PRIVATE_EVIDENCE
```

This document freezes the host-side repair produced after the first consumed Board B
physical successor attempt stopped at `ROM_IDENTITY_BINDING` before any flash read or
mutation.

## Observed failure and root cause

The consumed physical attempt produced a successful esptool 5.2.0 `read-mac` command,
but the reviewed v0.2.2 Guard rejected its stdout because the generic six-octet regex
found two distinct candidates.

Host-only forensic recovered:

```text
PROCESS_RETURN_CODE_ZERO=true
STDOUT_DISTINCT_SIX_OCTET_CANDIDATE_COUNT=2
STDERR_DISTINCT_SIX_OCTET_CANDIDATE_COUNT=0
AUTHORITATIVE_READ_MAC_LINE_COUNT=2
AUTHORITATIVE_READ_MAC_LINE_SHAPE=BASE MAC: <MAC>
FAILURE_CLASS=STDOUT_MULTIPLE_DISTINCT_CANDIDATES
ROOT_CAUSE_CONFIDENCE=HIGH
```

The exact esptool 5.2.0 ESP32-C6 behavior explains the false candidate: `read-mac`
prints an eight-octet EUI64 `MAC:` value in addition to the six-octet `BASE MAC:`
value, while the old Guard regex was not bounded to a complete line or to the `BASE
MAC` label. It could therefore match the first six octets embedded in EUI64. The
connection-info path and explicit `read-mac` path can also repeat the same valid BASE
MAC line; duplicate identical authoritative lines must not be treated as multiple
identities.

This was a host-side parser contract defect. It was not evidence of Board identity
mismatch, firmware corruption, flash mutation, or toolchain failure.

## Repair architecture

The already R2-reviewed mutation core is intentionally unchanged.

Frozen base authority:

```text
BASE_REVIEWED_IMPLEMENTATION_HEAD=b8eb0aec6d26d3905e8bc861625c1e20f1c40ba3
BASE_TOOL_GIT_BLOB=e7b0019cdb9673fbf4e23653dec561ea40ff757c
BASE_TOOL_MODE=BOARD_B_RECOVERY_ONLY
```

Repair implementation authority:

```text
REPAIR_IMPLEMENTATION_HEAD=af2ed8d5a62e84a83d4ba4593cf2442be3dff97d
REPAIR_ADAPTER_PATH=tools/n3w_ota_guard_identity_contract_repair.py
REPAIR_ADAPTER_GIT_BLOB=c5cf94b4a2de482049e5ea8ceb420a395115e037
REPAIR_TEST_PATH=tests/tools/test_n3w_ota_guard_identity_contract_repair.py
REPAIR_TEST_GIT_BLOB=532ae73e364a137607e7864561947311e03fb353
REPAIR_WORKFLOW_GIT_BLOB=0ab1ba352c335332d5178ec4b860a8fe74f137b8
REPAIR_REVISION=identity-contract-r1
```

The adapter binds the base source by its exact Git blob before execution. It delegates
all actual subprocess I/O and all app0/otadata/mutation logic to the reviewed base.
Only `rom_identity_read` stdout presented to the reviewed identity comparison is
canonicalized.

The repaired identity contract is:

1. retain the raw stdout/stderr files written by the reviewed base runner;
2. consider only complete lines with shape `BASE MAC: <six-octet>`;
3. ignore generic `MAC:`, EUI64, `MAC_EXT`, and embedded six-octet substrings;
4. allow repeated identical BASE MAC lines;
5. require exactly one distinct BASE MAC value across those authoritative lines;
6. pass one canonical BASE MAC line into the reviewed expected-vs-observed comparison;
7. if there are zero or multiple distinct exact BASE MAC values, fail closed.

No app0-write surface, retry, rollback, or new mutation primitive is added.

## Host regression

GitHub Actions run:

```text
WORKFLOW=N3W OTA Guard CI
RUN_ID=34601597808
CONCLUSION=success
BASE_TESTS=45/45 PASS
IDENTITY_REPAIR_TESTS=10/10 PASS
TOTAL_TARGETED_TESTS=55/55 PASS
COMPILE_WARNINGS_AS_ERRORS=PASS
PUBLIC_REPOSITORY_SAFETY=PASS
ALL_OBSERVED_HEAD_WORKFLOWS=12/12 PASS
```

Regression coverage specifically proves:

- the old parser reproduces the EUI64-prefix false positive;
- the repaired parser accepts duplicate identical `BASE MAC` lines;
- an EUI64 prefix is ignored;
- two distinct exact BASE MAC values still fail closed;
- a generic six-octet `MAC:` line without `BASE MAC` fails closed;
- raw evidence remains preserved while only the value returned to the reviewed parser
  is canonicalized;
- non-identity read results are not modified;
- host-only replay of the consumed-evidence shape succeeds when the exact BASE MAC
  matches expected identity and fails when it does not.

## Mandatory host-only replay before any new physical authorization

The source repair and CI are not sufficient by themselves to authorize another board
open. The already captured private evidence from the consumed attempt must now be
replayed with the repaired exact-label semantics.

This gate must not access USB, serial, Board B, flash, RF, or T1.

Use the exact repair adapter from the frozen repair implementation and the existing
private files only. The key command is logically:

```text
python tools/n3w_ota_guard_identity_contract_repair.py \
  replay-identity-evidence \
  --stdout-file <PRIVATE_CONSUMED_ATTEMPT>/rom_identity_read.stdout.txt \
  --expected-base-mac <PRIVATE_EXPECTED_BOARD_B_BASE_MAC>
```

The expected identity must come from existing private trusted evidence and must not be
written to public GitHub.

PASS requires exactly:

```text
REPAIR_BINDING=PASS
IDENTITY_REPAIR_REPLAY=PASS
AUTHORITATIVE_BASE_MAC_LINE_COUNT=2
AUTHORITATIVE_DISTINCT_BASE_MAC_COUNT=1
EXPECTED_IDENTITY_MATCH=PASS
BOARD_ACCESS=false
```

If the exact BASE MAC does not match the expected private identity, stop and classify
that as a real identity mismatch. Do not reopen the board. If replay passes, the next
step is a fresh one-time physical authorization; the consumed authorization must never
be reused.

## Safety disposition

```text
APP0_WRITE_ALLOWED=false
SECOND_APP0_FLASH_ALLOWED=false
OTADATA_MUTATION_COUNT_MAX=1
MUTATION_RETRY=false
AUTO_SECOND_ATTEMPT=false
AUTO_ROLLBACK=false
OLD_AUTHORIZATION_REPLAY=false
NEW_PHYSICAL_AUTHORIZATION_REQUIRED=true
```

The repair changes only the identity-output interpretation boundary. The reviewed
mutation core remains bound to the exact v0.2.2 base blob above.
