# N3W OTA Guard v0.2 R2 review note

This file intentionally marks the currently materialized source and focused tests as review-only.

```text
PRIMARY_COLLABORATION_SURFACE=GITHUB_NORMAL_SOURCE_PATHS
TOOL_PATH=tools/n3w_ota_guard.py
FOCUSED_TEST_PATH=tests/tools/test_n3w_ota_guard.py
ARCHIVE_RECOVERY_SNAPSHOT=docs/development/artifacts/N3W_OTA_GUARD_V0_2_REVIEW_20260911.md
R2_CODE_REVIEW_REQUIRED=true
PHYSICAL_USE_READY=false
```

The focused test harness does not erase the earlier archived host-suite evidence. R2 review must judge the implementation itself against ESP-IDF 5.5.4 / esptool 5.2.0 semantics before any new physical authorization is designed.
