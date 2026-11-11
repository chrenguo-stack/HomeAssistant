# N3-W T1 KF-147 Writable Mount Restoration Read-only Preflight Attempt02 — Remote Syntax Repair
# 2026-11-11

## Attempt02 evidence

```text
SOURCE_HEAD=8d6024ae889951eab1ff2427ad60e4a5598c8065
STATUS=STOP
REASON=remote_result_json_invalid
REMOTE_RETURN_CODE=1
REMOTE_STDOUT_LENGTH=0
REMOTE_STDERR_LENGTH=258
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
HOST_STATE_MUTATION=false
USB_MUTATION=false
U5_TRANSITION=false
```

The improved observability worked: this attempt proved the failure occurred before the remote script
could emit its JSON result.

## Root cause

Independent exact-source inspection found six literal backslash-n sequences in the
`verify_bound_media()` function signature inside `REMOTE_SCRIPT`. Because the script is passed
to `python3 -c`, those tokens cause a parser-level failure before `main()` can run.

A second CI defect allowed this through: the restoration test file was present in workflow path
filters, but the target-binding source job neither py_compiled the restoration executor nor executed
the restoration test. The test itself already contains a direct compile of `REMOTE_SCRIPT`.

## Repair

```text
REPAIR_HEAD=f9002512b20f95af0bfa3541cea7e175bf9eebdf
EXECUTOR_BLOB=122203aaa534b15e45ea16dbbf0ef46ba236cecd
MANIFEST_BLOB=42fabe839b8dda7a27015e82c0dc86ed156f7f9e
TARGET_BINDING_WORKFLOW_BLOB=94067a09c91d46491e1400b8d32f0a982948f89a
```

The six invalid literal backslash-n tokens were replaced with real line breaks. The target-binding
source job now explicitly py_compiles the restoration executor and runs
`tests/tools/test_n3w_t1_kf147_u5_writable_mount_restoration.py`.

## CI at polling stop

```text
TARGET_BINDING_RUN=43041346219
TARGET_BINDING_SOURCE=SUCCESS
TARGET_BINDING_EXACT=IN_PROGRESS
MANAGER_A_TO_B_RUN=43041345855
MANAGER_SOURCE=SUCCESS
MANAGER_EXACT_MANAGER_SLICE=QUEUED
FAST_CONTRACT_RUN=43041345992
FAST_CONTRACT=SUCCESS
PUBLIC_SAFETY_RUN=43041346291
PUBLIC_SAFETY=SUCCESS
CI_POLL_LIMIT_REACHED=true
FULL_APPLICABLE_CI_PASS=false
```

Links:
- https://github.com/chrenguo-stack/HomeAssistant/actions/runs/43041346219
- https://github.com/chrenguo-stack/HomeAssistant/actions/runs/43041345855
- https://github.com/chrenguo-stack/HomeAssistant/actions/runs/43041345992
- https://github.com/chrenguo-stack/HomeAssistant/actions/runs/43041346291

Next safe entry: after all applicable CI for exact head f9002512 is terminal SUCCESS, rerun the same
read-only preflight once. Live unmount, writable mount and U5 remain unauthorized.
