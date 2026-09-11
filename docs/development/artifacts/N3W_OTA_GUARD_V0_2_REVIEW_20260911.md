# N3W OTA Guard v0.2 review artifact

Status: **REVIEW ONLY / NOT AUTHORIZED FOR PHYSICAL USE**

This record preserves the exact high-level-model implementation and host-side tests generated during KF-089 OTA toolchain repair. It is intentionally archived before R2 review so the artifact does not exist only in chat/session storage.

## Authority / provenance

```text
TOOL_NAME=N3W OTA Guard
TOOL_VERSION=0.2.0-review
IMPLEMENTATION_ORIGIN=HIGH_LEVEL_MODEL
CODEX_IMPLEMENTATION_REUSED=false
PHYSICAL_USE_READY=false
BOARD_ACCESS=false
```

## Archived contents

The adjacent base64 file contains a deterministic `tar.gz` with:

```text
tools/n3w_ota_guard.py
tests/tools/test_n3w_ota_guard.py
```

Exact source hashes before bundling:

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

## Reconstruction

From this directory:

```bash
base64 --decode N3W_OTA_GUARD_V0_2_REVIEW_20260911.tar.gz.b64 \
  > N3W_OTA_GUARD_V0_2_REVIEW_20260911.tar.gz

sha256sum N3W_OTA_GUARD_V0_2_REVIEW_20260911.tar.gz

tar -xzf N3W_OTA_GUARD_V0_2_REVIEW_20260911.tar.gz
```

On macOS, use `base64 -D` instead of `base64 --decode` if required.

After extraction, verify both source-file hashes above before review or reuse.

## Review status frozen at archive time

```text
PY_COMPILE=PASS
HOST_TEST_COUNT=40
HOST_TEST_RESULT=PASS

ROM_IDENTITY_BINDING=true
APP0_SHA_BINDING_BEFORE_SWITCH=true
OTA_STATE_PRESERVED=true
SEQ_LABEL_PRESERVED=true
OTADATA_WRITE_SIZE=32
NON_TARGET_SECTOR_BYTE_IDENTICAL=true

R2_CODE_REVIEW_REQUIRED=true
PHYSICAL_USE_READY=false
```

This archive is a recovery/share artifact, not yet the canonical production tool path. After R2 review passes, the reviewed source should be materialized at normal repository paths and supersede this archive as implementation authority.
