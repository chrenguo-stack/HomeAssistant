# H3/N2 Stage 2D-9R G3R D2-10 forensic terminal closure and executor repair

## Approved scope

This source-only successor implements:

`D1-H3N2-STAGE2D9R-G3R-D2-10-FORENSIC-TERMINAL-CLOSURE-AND-EXECUTOR-REPAIR-20260729-01`

It is stacked directly on Draft PR #205 at exact HEAD
`0ca39a8a284fca70fc69474aadb13ca85492b10d`. It does not modify the
PR #205 branch or its Artifact.

## Frozen D2-10 disposition

D2-10 is permanently:

- `CONSUMED_FAILED`;
- primary failure `PREPARE_RESULT_TIMEOUT`;
- secondary terminalization failure `KeyError('main_sha')`;
- Flash completed;
- PREPARE count `1`;
- VERIFY count `0`;
- locked recovery attempted once;
- locked recovery outcome `UNKNOWN`;
- on-disk marker `CLAIMED_STALE`;
- replay and automatic retry prohibited.

The stale marker has SHA-256
`af478d31abc45d99fc3beebf9ca1ba5ed42f530a5f34efd2d133db2196bf7af6`.
The public forensic transcript has SHA-256
`53eeb04fd5f128068bd947f1b60a896d2f0cb38ed68f7cadbda54f149f1d7e64`.
The contract binds every redacted evidence file independently.

Artifact `8718562956` remains load-bearing forensic evidence for what D2-10
executed, but it is permanently prohibited as the source of another physical
authorization.

## Root cause

The inherited core result generator reads `authorization["main_sha"]`. D2-10
correctly moved the audit-only repository binding to
`authorization["repository_head_sha"]`. The result generator therefore raised
`KeyError` after the primary PREPARE failure and after the locked-recovery call
returned or raised.

Because recovery outcome existed only in the call stack and temporary work
directory, the secondary failure also destroyed the evidence needed to
distinguish recovery success from recovery failure.

## Executor repair

The reusable terminalization safety controller is installed only by a future,
separately bound physical wrapper. This PR creates no executable physical
request.

The controller:

- accepts `repository_head_sha` and retains `main_sha` only as a compatible
  result alias;
- wraps every result generator with a non-throwing terminal fallback;
- records recovery `STARTED`, `COMPLETED`, or `FAILED` outside the temporary
  execution directory;
- preserves the primary execution failure separately from secondary result or
  marker failures;
- provides an outer post-claim guard that converts a stale `CLAIMED` marker to
  `CONSUMED_FAILED` if result or marker terminalization raises;
- never expands one-shot, replay, retry, ACTIVATE, CLEANUP, or production
  permissions.

## Forensic closure tool

The host-only tool has two separate operations:

- `plan`: validates the exact stale marker, contract check, terminal output,
  and redacted evidence inventory, then writes only a proposed result, proposed
  marker, plan, and checksum manifest to a new output directory.
- `close`: repeats all validation and additionally requires a new exact,
  one-shot, maximum-two-hour forensic closure authorization before writing the
  terminal result and atomically replacing the stale marker.

No closure authorization is generated or packaged by this PR. The `close`
operation is not executed in this decision gate.

The tool contains no USB enumeration, serial, esptool, Flash, Broker, PREPARE,
VERIFY, or network implementation. It does not determine the unknown recovery
outcome; it records that uncertainty explicitly.

## Test layers

Fast tests cover:

- exact D2-10 evidence and stale-marker binding;
- read-only closure planning;
- changed marker/evidence rejection;
- separate closure authorization and expiry;
- D2-10-style `repository_head_sha` compatibility;
- complete simulated PREPARE timeout with recovery success;
- complete simulated PREPARE timeout with recovery failure;
- result and marker persistence with VERIFY count zero;
- terminal marker writer failure;
- arbitrary result-generator failure;
- deterministic two-lane review packaging.

GitHub CI must also verify PR #205 remains an exact open Draft, Artifact
`8718562956` remains unexpired with digest
`218b2138640dc3d5a21d3a0a6f455b9708de11eac7ca4b6908c167776a36c479`,
and no authorization record or physical request is present.

## Explicitly out of scope

This decision does not:

- alter the existing Mac marker or result directory;
- create or apply a forensic closure authorization;
- create a new physical request or physical authorization;
- connect or enumerate a board;
- open USB or serial;
- invoke esptool or modify Flash/NVS;
- start a Broker;
- execute PREPARE, VERIFY, ACTIVATE, or CLEANUP;
- mark a PR Ready, merge, release, tag, or deploy.
