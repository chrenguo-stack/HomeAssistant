# N3-W T1_Core_Stack Clean Reference — R1 T1_B first deployment payload_file_set false-STOP repair progress

Date: 2026-11-01

## 0. Status

```text
TASK=N3W_T1_CORE_STACK_CLEAN_REFERENCE_R1_T1B_FIRST_DEPLOYMENT_20261101_01

FIRST_LIVE_ATTEMPT=STOP
FAILURE_CODE=payload_file_set_invalid

FAILURE_STAGE=EXECUTOR_PAYLOAD_LOAD
RUN_FRESH_STAGING_ENTERED=false
IMAGE_REQUEST_EVENT_OBSERVED=false
IMAGE_LOAD_EVENT_OBSERVED=false
PRODUCT_STATE_COMMIT_OBSERVED=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false

REMOTE_PAYLOAD_PRESERVED=true
BLIND_REPLAY_ALLOWED=false
```

## 1. Root cause

The Clean Reference host wrapper extracted the exact runtime payload into a transaction-owned
remote directory and then copied:

```text
n3w_t1_clean_reference_executor.py
```

inside that same payload root.

The executor starts by calling the strict production payload manifest loader. That loader recursively
enumerates every file below the payload root and requires the set to equal the manifest-declared file
set, excluding only the payload manifest and the production claim marker.

Therefore the host wrapper itself introduced an undeclared extra file before the executor validated
the payload:

```text
<remote_payload_root>/n3w_t1_clean_reference_executor.py
```

The strict validator correctly returned:

```text
payload_file_set_invalid
```

This is a host-wrapper staging-location defect. The payload, S1 image cache and strict file-set
validator are not the root cause.

## 2. Mutation boundary of the failed attempt

The executor failed while loading/validating the payload, before calling `run_fresh_staging()`.

Observed output contained no:

```text
clean_reference_authorized
image_requested
image_loaded
```

events.

Therefore the failed attempt did not enter the fresh installer mutation sequence and did not:

- transfer any image tar requested by the executor;
- load an application image;
- create fresh system identity/state;
- create Broker/DynSec product state;
- commit product runtime;
- start any product service;
- access any board.

The transaction-owned remote runtime payload was intentionally preserved by the host wrapper for
failure evidence.

## 3. Bounded source repair

Repair commits:

```text
SOURCE_COMMIT=22ac64f9c1817a9d27f35638a77fc5a7f259ede3
TEST_HEAD=340f967065460504e52cd364a3bdaa0f24aec59e
```

The repair changes only:

```text
tools/n3w_t1_clean_reference_staging_host.py
tests/tools/test_n3w_t1_clean_reference_r1.py
```

New executor staging:

```text
BEFORE=<remote_payload_root>/n3w_t1_clean_reference_executor.py
AFTER=<remote_payload_root>.executor.py
```

The executor is now outside the manifest-validated payload tree.

Success cleanup removes both:

```text
<remote_payload_root>
<remote_payload_root>.executor.py
```

Failure behavior remains evidence-preserving; no blind cleanup/replay is introduced.

## 4. Regression tests

Added tests prove:

1. the executor remote path is a sibling of the payload tree, not a child;
2. success cleanup removes both the payload tree and sibling executor.

Existing strict payload manifest validation is unchanged.

## 5. CI

```text
WORKFLOW=N3W T1 Clean Reference runtime payload CI
RUN_ID=41293344644
STATUS=queued
CONCLUSION=NOT_AVAILABLE
POLL_LIMIT_REACHED=true
```

Link:

```text
https://github.com/chrenguo-stack/HomeAssistant/actions/runs/41293344644
```

No duplicate workflow dispatch was performed.

## 6. Stop point

```text
CURRENT_RESULT=STOP_SOURCE_REPAIR_CI_PENDING
T1_RETRY=false
REMOTE_EVIDENCE_CLEANUP=false
AUTO_EXECUTE_NEXT_GATE=false
```

Do not retry R1 first deployment until the dedicated source CI succeeds and the repaired deployment
tool authority is freshly rebound.
