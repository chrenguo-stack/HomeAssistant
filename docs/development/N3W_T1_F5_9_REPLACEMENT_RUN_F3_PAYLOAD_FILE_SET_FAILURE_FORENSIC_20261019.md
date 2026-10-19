# N3-W T1 F5-9 replacement run — F3 payload file-set failure forensic

Date: 2026-10-19

## Live result

~~~text
TASK=N3W_T1_F5_9_T1B_EXPLICIT_LIVE_AUTHORIZATION_REPLACEMENT_RUN_20261019_01
RESULT=FAIL

AUTHORIZATION_GRANTED=true
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
AUTHORIZATION_REPLAY_ALLOWED=false

RUN_ID=3e37993537f9317dfb8070fd53fa20384de86cbd7c2a234857b55602c1280799
RUN_ID_SHA256=9fd9cf8ea51f48f0cb44d0d20bf3eda89f805a54d57d117f31f5f5f3530399aa
PLAN_DIGEST=eaebb731adf6a7ce12af876fb72420f8967a7985689551afa7c8f93a5cf9b0ce
PREFLIGHT_SHA256=583fc5ded12d998c1e30bdc75074cdd183cbd28a2d067c04798043207d2e6622
APPROVAL_RECORD_SHA256=ddfaad073a9d556d99f63aba1d2010b43b488c7cf9f22a4a61fba11c330fb9ee

PRODUCT_SOURCE_HEAD=9048dd7c6b48c0620471919c0cf96c96bdab71f1
PRODUCT_SOURCE_TREE=7b567c7140fd403049a6f7c2fa51887be08e8c8d
RELEASE_ID=31c8a8cd2d8424f93aaa7b4d0b78cfe2b73f1b035f4bdbce08a181ac56619420
RELEASE_SHA256=1bbcb81bd84ec899e4c1d37fffef99defbbcc40509c49ce41048f6a6d92039ad

HOST_BASELINE_REPORT=PASS
HOST_BASELINE_INSTALLED=true
DOCKER_ACTIVE=true
PRODUCT_SERVICE_START=false

REMOTE_BOOTSTRAP_STATUS=STOP
REMOTE_BOOTSTRAP_REASON=payload_file_set_invalid
REMOTE_BOOTSTRAP_AUTHORIZATION_CLAIMED=false
REMOTE_BOOTSTRAP_AUTHORIZATION_CONSUMED=false

MAC_FINAL_OUTCOME=FAIL
MAC_TERMINAL_PHASE=HOST_BASELINE
MAC_FAILURE_CODE=phase_execution_failed:F3_DEPLOY:production_f3_claimed_or_unknown:production_f3_execution_not_proven
CONNECTION_EPOCH_COUNT=1
DEVICE_ACCEPTANCE=false
EVIDENCE_COMPLETE=false
OPERATOR_SESSION_CLOSED=true
LIVE_REBOOT=false
BOARD_ACCESS=false
MERGE=false
~~~

## Exact source root cause

The source defect is deterministic in the exact production source.

`tools/n3w_t1_fresh_product_staging_host.py::execute_production()` extracts the immutable F3 payload into
`remote_dir`, then copies the mutable production phase context to:

~~~text
<remote_dir>/production-phase-context.json
~~~

The same `remote_dir` is passed to the target bootstrap as `--payload-root`.

`tools/n3w_t1_fresh_product_bootstrap.py::execute_production_apply()` begins by calling
`_load_manifest(payload_root)`. That file-set verifier accepts only manifest-declared payload files and excludes
only `payload-manifest.json` plus the historical exact claim marker. It does not exclude
`production-phase-context.json`.

Therefore the Mac production adapter itself inserts a control-plane file into the immutable payload namespace and
the target correctly rejects that extra file as:

~~~text
payload_file_set_invalid
~~~

The failure is before `_load_production_phase_context()`, before `_claim_production_execution()`, before any
image request/load and before public product staging.

This is a new F5 integration defect, distinct from KF-114. KF-114 concerned the historical
`.authorization-claimed` marker. The correct repair is not to weaken the payload inventory for arbitrary control
files; production phase context should be staged outside the immutable payload root and cleaned/preserved with the
same success/failure semantics as the payload staging directory.

## Conservative target classification pending fresh read-only proof

Source and live output directly prove:

~~~text
HOST_BASELINE_BUSINESS_EXECUTION=PASS
DOCKER_BASELINE_INSTALLED=true
F3_PUBLIC_PRODUCT_STAGING_STARTED=false:SOURCE_ORDER_AND_BOOTSTRAP_STOP
F3_PRODUCTION_EXECUTION_CLAIM_CREATED=false:SOURCE_ORDER_AND_BOOTSTRAP_AUTHORIZATION_CLAIMED_FALSE
PRODUCT_SERVICE_START=false
REBOOT_EXECUTED=false
BOARD_ACCESS=false
~~~

The runtime source attempts to mark the outer `F3_DEPLOY` phase `UNKNOWN` after any dispatch exception. The exact
durable run/phase state, F3 production-execution ledger absence, product-path absence and remote staging cleanup must
be freshly read from T1 before they are promoted to PASS.

Do not replay this run and do not reuse its F5-9 authorization.

## Next route

~~~text
NEXT_ONE_GATE=N3W_T1_F5_9_F3_PAYLOAD_FILE_SET_FAILURE_READONLY_FORENSIC_20261019_01
T1_MUTATION=false
SOURCE_MUTATION=false
NEW_PRODUCTION_AUTHORIZATION=false
~~~
