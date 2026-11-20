# N3-W T1 U13B P3 U9 source closure and read-only preflight entry

Date: 2026-11-18

## Frozen candidate

```text
PR=807
PR_STATE=OPEN_DRAFT_UNMERGED
U9_CANDIDATE_HEAD=816cf5f2f55c895b6112edbd563cf71df8b7be93
U9_EXECUTOR_BLOB=a38f4f2bae49d45c8390435454046bef71d0f71b
U9_GRANT_PRESENT=false
U9_LIVE_AUTHORIZATION_GRANTED=false
```

The P3-specific U9 source binds the exact live U8 checkpoint:

```text
U8_TRANSACTION_SHA256=c9210a75ba4496b42fd080ca4ef261cf669a56452f99531066f921a5fcbe4908
U8_RECEIPT_SHA256=8340d0b4a5be925c954932113b8c593668e83b5f60d1271714f2ce91d521a63a
RECOVERY_CONTENT_MANIFEST_SHA256=d534be84e38817b10eab8a2f8a47c6dae3fd0946da9eba1e1d7f12090e23e9d3
PRODUCT_AUTHORIZATION_ID=N3W_T1_CORE_UPDATER_HOMEASSISTANT_USB_P3_U9_20261118_01
```

## Independent source review

The product primitive `claim_live_authorization()` validates an active U8 transaction, requires product authorization to be previously unclaimed/unconsumed, validates the product authorization-id namespace, and returns a new U9 transaction document. It does not itself persist host or USB state.

The P3 U9 preflight path:
- re-verifies durable U8 through the U8 status/reconciliation path;
- requires the exact U8 transaction digest and recovery-content manifest;
- requires application services still quiesced and Broker continuity;
- requires exact target/predecessor/backup/media/source bindings;
- projects U8 -> U9 only in memory;
- performs no transaction store write, no USB metadata write, no ledger creation and no authorization claim.

The execute path, which remains unauthorized, requires a separate grant commit and is bounded to:
1. exact final preclaim verification;
2. one-shot authorization ledger claim;
3. USB U9 persistence;
4. Host U9 persistence;
5. stop before U10.

It explicitly performs no service restart, predecessor image deletion, target image load or U10+ action.

## CI evidence

```text
HA_TARGET_BINDING_RUN=44318364944
HA_TARGET_BINDING_SOURCE=SUCCESS
HA_TARGET_BINDING_EXACT_BINDING=SUCCESS
HA_TARGET_BINDING_TESTS=963_PASS

P3_LIVE_READONLY_SOURCE_RUN=44318364803
P3_LIVE_READONLY_SOURCE=SUCCESS

CORE_STACK_AUTHORITY_RUN=44318364642
CORE_STACK_AUTHORITY=SUCCESS

PUBLIC_REPOSITORY_SAFETY_RUN=44318364736
PUBLIC_REPOSITORY_SAFETY=SUCCESS
```

The same-version artifact workflow is not a U9 source-gate dependency.

## Next gate

```text
NEXT_ONE_GATE=N3W_T1_U13B_P3_U9_READONLY_PREFLIGHT_20261118_01
T1_ACCESS=READ_ONLY_ONLY
T1_MUTATION=false
USB_MUTATION=false
TRANSACTION_MUTATION=false
AUTHORIZATION_CLAIM=false
U9_TRANSITION=false
U10_PLUS=false
```

A successful read-only preflight does not authorize the U9 live claim. U9 execute requires a later isolated grant commit and explicit operator authorization.
