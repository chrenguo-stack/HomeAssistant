# N3-W T1 U13B P3 U10 read-only Attempt 04 exact root-cause closure

Date: 2026-11-18

## Physical result

```text
ATTEMPT04_EXACT_CANDIDATE=3a3cceb57167882c1f0cbaf32c77ee21779bc213
STATUS=STOP
REASON=private_file_metadata_invalid
STAGE=verify_u9_authority_ledgers
U9_SUBSTAGE=durable_u9_verified
EXIT_CODE=2
RECEIPT_SHA256=4783adc3ca22752914353fbbb933004894fb93e820231825db72a9047b11ae76
READ_ONLY=true
DESTRUCTIVE_CUTOVER=false
DESTRUCTIVE_CUTOVER_ELIGIBLE=false
PREDECESSOR_RUNTIME_DELETE=false
PREDECESSOR_IMAGE_DELETE=false
TARGET_IMAGE_LOAD=false
SERVICE_MUTATION=false
U10_TRANSITION=false
U11_PLUS=false
```

Raw evidence remains operator-local/private.

## Exact source reasoning

Attempt 04's new `u9_substage=durable_u9_verified` proves the delegated `u9.inspect()` completed all of its checks, including:
- U9 claim via the U9-specific compatibility reader;
- base historical ledger + exact-tools binding;
- host U9 transaction;
- U7 ledger;
- runtime/USB/mirror checks;
- quiesced application owner and image/source checks;
- U9 success ledger.

After U9 returns, U10 independently rereads the U9 transaction; because the receipt reached `verify_u9_authority_ledgers`, that strict transaction read also passed.

The next U10 source sequence is:

```python
original = preflight.bind_ledger(plan)
broker = u8.bind_u7_ledger(plan)
u9_claim = preflight.read_object(u9.ledger_root() / "claim.json")
```

The first two operations had already passed moments earlier inside the same `u9.inspect()` execution and there is no mutation path in this probe. The third operation is different: it bypasses the U9-specific legacy compatibility reader and applies the strict generic private-file reader to the exact U9 claim record already known from Attempt 01 to have legacy mode metadata.

Therefore the remaining false STOP is the duplicated strict U9-claim reread in U10.

## Repair contract

- Replace only the U10 U9-claim read with `u9.read_ledger_object(...)`.
- Keep `preflight.read_private()` and all unrelated generic private-file checks unchanged.
- Add regression requiring U10 to use the U9 ledger-specific reader for the U9 claim and forbidding the strict generic reader at that call site.
- Keep U10 read-only, with no execute/grant/destructive path.
- Source/CI closure is required before any further physical retry.

## Safety boundary

```text
CURRENT_LIVE_STAGE=U9_LIVE_AUTHORIZATION_CLAIMED
U9_AUTHORIZATION=CONSUMED_NO_REPLAY
ATTEMPT04=CONSUMED_AS_READONLY_ATTEMPT
ATTEMPT05_AUTHORIZED=false
U10_DESTRUCTIVE_AUTHORIZATION=false
U11_PLUS=false
PR807_MERGE=false
```
