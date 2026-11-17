# N3-W T1 U13B P3 acceptance-only clean OTA source package CLOSED_PASS — 2026-11-17

## Closure

```text
PR=807
PR_STATE=OPEN_DRAFT_UNMERGED
DEFAULT_MAIN_HEAD=3e7faf258d670c9eaf3be6ede9bbb02df2ac009d

P3_TARGET_AUTHORITY_CLOSED=true
P3_EXACT_ARTIFACT_RUN=44089585822
P3_EXACT_ARTIFACT_RESULT=SUCCESS
P3_TARGET_BINDING_RUN=44091564730
P3_TARGET_BINDING_RESULT=SUCCESS

P3_NONLIVE_SOURCE_PACKAGE_HEAD=c476770f652d06ab581ad7022a2935e59a597268
P3_NONLIVE_SOURCE_CI_RUN=44093176411
P3_NONLIVE_SOURCE_CI_RESULT=SUCCESS
P3_HEAD_WORKFLOWS=20_OF_20_SUCCESS

TARGET_IMAGE=local/n3w-homeassistant:2026.10.3-c2bb99de
PREDECESSOR_IMAGE=local/n3w-homeassistant:2026.10.4-5881590f
TARGET_ARCHIVE_SHA256=d26ac92ceed7baf689e1db9f11550c1e51d36f6dc81cac995a3eaf7a3d13912d
TARGET_ARCHIVE_SIZE_BYTES=835151232
TARGET_ARTIFACT_ID=14330409226
TARGET_ARTIFACT_DIGEST_SHA256=a84ddb194ed72ddba6797a0141c1835ecdadfc369c84427303f02d3628d76200
```

The P3 acceptance-only source package closes the repository-side proof that the
frozen 2026.10.3 target can be converted into the existing product
`HostOtaAdmission` without modifying Manager's normal higher-version rule.

The package intentionally bypasses only the version-discovery layer. The
lower product path remains:

```text
HaUsbIpcExecutor.submit("PREPARE")
-> HaUsbStateStore.prepare_new()
-> archive existing terminal transaction
-> new_transaction()
-> request_prepare()
-> store.write()
-> normal USB / recovery / backup / U9 / U10 / U11 product path
```

The focused CI also re-runs
`test_terminal_ha_usb_transaction_is_archived_before_next`, proving the
existing terminal U13A transaction may be archived before a new transaction is
created.

## Safety boundary

```text
REAL_T1_READONLY_PREFLIGHT_EXECUTED=false
REAL_T1_ACCESS_AUTHORIZED=false
LIVE_EXECUTION_AUTHORIZED=false
NEW_CLEAN_OTA_MUTATION_AUTHORIZED=false
U13B_LIVE_EXECUTION_AUTHORIZED=false
CONTROLLED_ROLLBACK_MUTATION_AUTHORIZED=false
T1_MUTATION=false
USB_MUTATION=false
SERVICE_MUTATION=false
IMAGE_MUTATION=false
HA_DATA_MUTATION=false
BOARD_ACCESS=false
MERGE=false
```

P3 source closure does not authorize or execute a real T1 preflight or any new
clean OTA transaction.

## Next source gate

The next repository-side gate is to build and test two exact packages:

1. a fresh real-T1 read-only preflight that revalidates the current terminal
   U13A runtime, transaction, USB/media authority, exact 2026.10.3 artifact
   availability, state-root/history admissibility and capacity prerequisites;
2. a P3 live executor source package that is fail-closed, one-shot, separately
   authorized and explicitly stops at U11 before U12.

Both packages must remain non-executable against real T1 until their individual
authorization flags are explicitly granted after source/CI closure.
