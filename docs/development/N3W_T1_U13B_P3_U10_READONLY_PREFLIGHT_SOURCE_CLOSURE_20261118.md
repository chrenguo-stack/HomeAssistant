# N3-W T1 U13B P3 U10 read-only preflight source closure

Date: 2026-11-18

## Frozen candidate

```text
PR=807
P3_U10_READONLY_CANDIDATE_HEAD=574e25498b7ef545652ea3d74c6c651fe83ae19a
P3_U10_SOURCE_BLOB=53b8d8fbdafde67bcc976eb0f69a4b97fea8bf39
EXECUTE_MODE_PRESENT=false
U10_GRANT_PRESENT=false
U10_DESTRUCTIVE_AUTHORIZATION=false
```

## Exact live entry binding

```text
CURRENT_LIVE_STAGE=U9_LIVE_AUTHORIZATION_CLAIMED
U9_TRANSACTION_SHA256=2b3812af093c1f73a95744413e238f1ca3763407241f889c0646b9495e35a84b
RECOVERY_CONTENT_MANIFEST_SHA256=d534be84e38817b10eab8a2f8a47c6dae3fd0946da9eba1e1d7f12090e23e9d3
U9_AUTHORIZATION=CONSUMED_NO_REPLAY
```

The historical R37/R38 U10 packages are not valid execution authority for this P3 sequence because they bind a different U9 transaction, media identity, image/container set, and historical authorization ledgers.

## Read-only contract

The P3-specific U10 preflight:
- re-verifies the durable P3 U9 checkpoint;
- requires the product authorization to already be claimed and consumed;
- rebinds the current USB by filesystem UUID;
- verifies the USB transaction mirror using the U9 write-session fingerprint recorded in the U9 claim ledger, not the current session fingerprint;
- rehashes target and predecessor recovery archives;
- reverifies the protected Home Assistant backup;
- recomputes recovery capacity;
- requires the stopped Home Assistant container to be the only remaining user of the predecessor runtime image;
- requires the predecessor image still present and the target internal image absent;
- projects the U9 -> U10 transition in memory only.

The source contains no execute mode, no grant path, no Docker container removal, no Docker image removal, no transaction write, no USB metadata sync, and no service start/stop.

## CI

```text
HA_TARGET_BINDING_RUN=44323658172
SOURCE_JOB=SUCCESS
EXACT_BINDING_JOB=SUCCESS
FULL_TEST_SUITE=971_PASS

P3_LIVE_READONLY_SOURCE_RUN=44323658226
P3_LIVE_READONLY_SOURCE=SUCCESS

CORE_STACK_AUTHORITY_RUN=44323658093
CORE_STACK_AUTHORITY=SUCCESS

PUBLIC_REPOSITORY_SAFETY_RUN=44323658007
PUBLIC_REPOSITORY_SAFETY=SUCCESS
```

## Next gate

```text
NEXT_ONE_GATE=N3W_T1_U13B_P3_U10_READONLY_PREFLIGHT_20261118_01
T1_ACCESS=READ_ONLY_ONLY
TRANSACTION_MUTATION=false
USB_MUTATION=false
PREDECESSOR_RUNTIME_DELETE=false
PREDECESSOR_IMAGE_DELETE=false
TARGET_IMAGE_LOAD=false
SERVICE_MUTATION=false
U10_TRANSITION=false
U11_PLUS=false
```

A PASS only proves U10 destructive capacity release is eligible. It does not authorize or perform U10.
