# N3W OTA Guard v0.2 review artifact

Status: **REVIEW ONLY / NOT AUTHORIZED FOR PHYSICAL USE**

This record preserves the high-level-model implementation and host-side review material generated during KF-089 OTA toolchain repair. GitHub is the team collaboration workspace; the tool must not exist only in chat/session storage.

## Current team collaboration surface

The active review source is now materialized directly at normal repository paths on the review branch:

```text
tools/n3w_ota_guard.py
tests/tools/test_n3w_ota_guard.py
```

The deterministic archive described below remains a recovery snapshot of the earlier pre-materialization state. It is no longer the primary review surface.

Current review branch state after materialization/focused-test safety repair:

```text
BRANCH=review/n3w-ota-guard-v0.2-20260911
CURRENT_REVIEW_COMMIT=a6b257acdc24049a362f1cebd37af76124746770
TOOL_GIT_BLOB=264a74ae6144a5dae1ca660dcb2b27c283a8a0f4
FOCUSED_TEST_GIT_BLOB=56b75a136b613999074f1f8a219dbcdb4e07ae10
STATUS=REVIEW_ONLY
PHYSICAL_USE_READY=false
BOARD_ACCESS=false
```

The focused normal-path test file is an R2 review harness for the highest-risk invariants. The archive retains the earlier broader host-side suite snapshot and its original provenance.

## Authority / provenance

```text
TOOL_NAME=N3W OTA Guard
TOOL_VERSION=0.2.0-review
IMPLEMENTATION_ORIGIN=HIGH_LEVEL_MODEL
CODEX_IMPLEMENTATION_REUSED=false
PHYSICAL_USE_READY=false
BOARD_ACCESS=false
```

## Archived pre-materialization snapshot

The adjacent base64 file contains a deterministic `tar.gz` with the earlier source/test snapshot:

```text
tools/n3w_ota_guard.py
tests/tools/test_n3w_ota_guard.py
```

Hashes frozen at archive creation time:

```text
tools/n3w_ota_guard.py
SHA256=1a44848a110ab4d72eb1179e113c22a6310f725a7f32f84148fd8b3651782572
SIZE=38564

tests/tools/test_n3w_ota_guard.py
SHA256=bc6a3b082ded1c2198975d95880f7d94bcc9aeee687fc72d9f932fe8db0394b5
SIZE=21374
```

Bundle:

```text
FILE=N3W_OTA_GUARD_V0_2_REVIEW_20260911.tar.gz
SHA256=43d152b5c8a6b370740ec1fdb8bfaa9241d5cf225a592d9a55e8047efdf1724c
SIZE=14635
BASE64_FILE=N3W_OTA_GUARD_V0_2_REVIEW_20260911.tar.gz.b64
```

These hashes describe the archive snapshot only. The normal-path focused test was subsequently replaced with a public-repository-safe R2 review harness; use the branch commit/blob bindings above for current review.

## Reconstruction of archived snapshot

From this directory:

```bash
base64 --decode N3W_OTA_GUARD_V0_2_REVIEW_20260911.tar.gz.b64 \
  > N3W_OTA_GUARD_V0_2_REVIEW_20260911.tar.gz

sha256sum N3W_OTA_GUARD_V0_2_REVIEW_20260911.tar.gz

tar -xzf N3W_OTA_GUARD_V0_2_REVIEW_20260911.tar.gz
```

On macOS, use `base64 -D` instead of `base64 --decode` if required.

## Host validation history

Archive-time validation:

```text
PY_COMPILE=PASS
HOST_TEST_COUNT=40
HOST_TEST_RESULT=PASS
```

Current GitHub review commit additionally passed repository CI including Public repository safety after synthetic-only MAC fixtures replaced board-like literals.

Frozen implementation properties under review:

```text
ROM_IDENTITY_BINDING=true
APP0_SHA_BINDING_BEFORE_SWITCH=true
OTA_STATE_PRESERVED=true
SEQ_LABEL_PRESERVED=true
OTADATA_WRITE_SIZE=32
NON_TARGET_SECTOR_BYTE_IDENTICAL=true

R2_CODE_REVIEW_REQUIRED=true
PHYSICAL_USE_READY=false
```

The materialized normal source path is now the primary implementation review surface. This does **not** make the tool production or physical-use authority. R2 semantic/code review must pass before any separate physical successor authorization is designed.
