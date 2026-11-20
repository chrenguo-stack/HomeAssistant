# N3-W T1 U13B P3 U10 read-only preflight Attempt 02 ModuleNotFoundError safe STOP

Date: 2026-11-18

## Result

```text
EXECUTION_CANDIDATE=c288303a638947fedb7ee504874f7a14a147bf87
STATUS=STOP
REASON=ModuleNotFoundError
STAGE=bind_durable_u9
EXIT_CODE=2
READ_ONLY=true
DESTRUCTIVE_CUTOVER=false
DESTRUCTIVE_CUTOVER_ELIGIBLE=false
U10_TRANSITION=false
U11_PLUS=false
PREDECESSOR_RUNTIME_DELETE=false
PREDECESSOR_IMAGE_DELETE=false
TARGET_IMAGE_LOAD=false
SERVICE_MUTATION=false
LOCAL_RECEIPT_SHA256=8f2275e25a1b5be8dfa6fa104ad2d2c529162a0c581585006c00c172d073b9ca
```

The operator-local raw evidence remains private. The public repository records only the safe receipt fields and SHA-256 binding.

## Classification

This is a safe read-only tooling failure. It does not indicate U9 transaction corruption and does not permit U9 replay. The durable live authority remains `U9_LIVE_AUTHORIZATION_CLAIMED`.

No predecessor runtime/image deletion, target image load, service mutation, U10 transition, U11+ transition or destructive cutover occurred.

## Root cause

The exact Attempt 02 source executes remotely under an isolated Python bootstrap.

`u10_preflight.inspect()` first calls `u9.inspect()`. Inside the durable-U9 status path, after the U9 ledger record is accepted, the first product-module import is reached before `preflight.bind_ledger(plan)`.

`preflight.bind_ledger(plan)` is what validates the historical authority and invokes `recovery.load_frozen_tools(...)`, which adds the exact frozen product-tool directory to the isolated process import path.

The ordering is therefore invalid for an isolated bootstrap: the product module is requested before its exact frozen path has been loaded. Attempt 01 stopped earlier at the legacy-ledger metadata check, so it could not expose this second latent defect.

## Repair boundary

Allowed continuation is source/test/CI/archive only:
- move exact-tools binding ahead of the first product import in U9 durable status inspection;
- add focused ordering regression;
- make the P3 live/read-only workflow run the U9/U10 source checks and focused tests;
- archive CI and freeze a new exact read-only candidate.

Not authorized:
- U9 replay;
- destructive U10 predecessor-capacity release;
- predecessor deletion;
- target image load/start;
- service restart;
- U11+;
- spare-T1 mutation;
- PR #807 merge.

A later read-only physical attempt is required for physical closure. Even a PASS does not grant destructive U10 authorization.
