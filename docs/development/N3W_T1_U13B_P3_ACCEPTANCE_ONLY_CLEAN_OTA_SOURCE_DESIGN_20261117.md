# N3-W T1 U13B P3 acceptance-only clean OTA source design — 2026-11-17

## Goal

Prepare the source/package boundary needed to create a fresh physical-acceptance transaction from the current terminal U13A state without weakening the normal product update policy.

The current real T1 is intentionally treated as:

```text
CURRENT_IMAGE=local/n3w-homeassistant:2026.10.4-5881590f
CURRENT_TRANSACTION=U13A_COMMITTED / COMMITTED
TARGET_IMAGE=local/n3w-homeassistant:2026.10.3-c2bb99de
TARGET_PURPOSE=U13B_PHYSICAL_ACCEPTANCE_ONLY
```

## Why Manager is not modified

The normal Manager control plane correctly exposes an update only when the approved version is greater than the installed version. 2026.10.3 is lower than 2026.10.4, so publishing it as a normal approved update would either be rejected or require weakening a production safety rule.

P3 therefore bypasses only the version-discovery layer.

It does **not** bypass the lower product path.

## Reused product path

The acceptance package constructs the already-existing `HostOtaAdmission` from the exact P3 target authority and feeds that authority to the already-existing `HaUsbIpcExecutor`.

The existing product implementation then owns:

```text
HaUsbStateStore.prepare_new()
-> archive current terminal transaction to history/
-> new_transaction()
-> request_prepare()
-> HaUsbStateStore.write()
-> normal USB prepare / target verification
-> predecessor recovery preparation
-> authenticated HA backup
-> recovery admission
-> U9 one-shot authorization
-> U10 predecessor capacity release
-> U11 target install/start
STOP BEFORE U12
```

No old U13A transaction is rewritten. `prepare_new()` permits only terminal HA-USB status values and archives the existing transaction before a fresh transaction is persisted.

The repository regression `test_terminal_ha_usb_transaction_is_archived_before_next` is part of the focused P3 source CI.

## Current source package boundary

Package:

`tools/execution_packages/n3w/r7a/u13b_p3_acceptance_clean_ota_source/`

It can only perform a local `source-check`. It has no SSH transport, no T1 target argument, no service/image/USB mutation code and no live mode.

```text
REAL_T1_ACCESS_AUTHORIZED=false
LIVE_EXECUTION_AUTHORIZED=false
NEW_CLEAN_OTA_MUTATION_AUTHORIZED=false
CONTROLLED_ROLLBACK_MUTATION_AUTHORIZED=false
```

A later live package must be separately reviewed and separately authorized.

## Exact target authority

```text
P3_EXACT_ARTIFACT_RUN=44089585822
P3_TARGET_BINDING_RUN=44091564730
TARGET_IMAGE=local/n3w-homeassistant:2026.10.3-c2bb99de
ARCHIVE_SHA256=d26ac92ceed7baf689e1db9f11550c1e51d36f6dc81cac995a3eaf7a3d13912d
ARCHIVE_SIZE_BYTES=835151232
ARTIFACT_ID=14330409226
ARTIFACT_DIGEST_SHA256=a84ddb194ed72ddba6797a0141c1835ecdadfc369c84427303f02d3628d76200
```

## STOP boundary

Source/package CI success does not grant T1 access.

Next live-facing work must first build a reviewed live executor that performs fresh read-only revalidation, exact artifact retrieval/binding, one-shot authorization separation and an explicit stop at U11 before U12.
