# N3-W T1 U9+ Phase-A restart-convergence live revalidation preflight

```text
NEXT_ONE_GATE=N3W_T1_U9_PLUS_PHASE_A_RESTART_CONVERGENCE_REPAIR_LIVE_REVALIDATION_PREFLIGHT
PREFLIGHT=PASS
SCOPE=READ_ONLY
OBSERVED_AT_UTC=2026-11-20T09:22:55.385966Z
EVIDENCE_ORIGIN=USER_EXECUTED_PINNED_SSH_PROBE
ARCHIVE_STATUS=EVIDENCE_ONLY
PRODUCTION_AUTHORITY=false
```

## Fresh repository binding

- main: `3e7faf258d670c9eaf3be6ede9bbb02df2ac009d`.
- PR #807: open draft, unmerged. PR and branch head at rebind: `7811b6bc2fc3cdc5b1cecb45549cb81b6d80784c`.
- CI authority: `3d74881e3bfadbecd23721f8c9d500f95ef69696`, 22 of 22 workflow runs successful.
- Source, test and manifests were identical at both heads. Local package check: `U9PLUS_PHASE_A_SOURCE_CHECK_PASS`.

| Member | Git blob |
| --- | --- |
| Repaired U13B host | `437f3e6c4cae53f7d94e244cd312ac454768f8e1` |
| Regression test | `9ca455c79204632e396530c0e40f654957da2caf` |
| P3 manifest | `fcb8ecd4dd4f68a7fef5c64abe627cedc32dbca7` |
| Phase-A manifest | `2ba6e96aec0f41f7916c852cef37c3fce9ecb966` |

## Live observations

```text
HOST_PHASE=U13B_ROLLED_BACK
HOST_STATUS=ROLLED_BACK
HOST_TRANSACTION_SHA256=4548f591d972576ea4d3f1f078cb55b483d1f63f2244b03c3413da1891e09d3f
U11_OVERLAY_SUPERVISION=PASS
MANAGER_COUNT=1
HOMEASSISTANT_COUNT=1
BROKER_COUNT=1
LISTENERS_EXACT=true
MANAGER_MQTT_AUTHENTICATED=true
HOMEASSISTANT_MQTT_AUTHENTICATED=true
HOMEASSISTANT_HTTP_STATUS=401
HOMEASSISTANT_BINDING=local/n3w-homeassistant:2026.10.4-5881590f
CANDIDATE_OVERRIDE_ACTIVE=true
LIVE_CANDIDATE_DAEMON_BLOB=941baffc8423a10cfa1436323d109caae17be473
LIVE_CANDIDATE_U13B_HOST_BLOB=a103a2633aaea5a34efbfed35449b2eb5bace61b
IPC_UID_GID=999:999
IPC_PHASE=ERROR
IPC_ERROR_CODE=u13b_predecessor_runtime_not_running
```

The probe reached its end snapshot. The durable Host transaction bytes, OTA main PID and candidate host blob matched their initial observations. The IPC error matches the documented old-candidate baseline. The probe observed the durable Host record and did not independently reread USB metadata. This archive records the operator-provided probe output, with private SSH routing and authentication details excluded.

## Stop boundary

```text
PHASE_A_OVERALL=NOT_YET_PASS
LIVE_437F_RETRY_AUTHORIZATION=NOT_GRANTED
CANDIDATE_REPLACEMENT=false
OTA_RESTART=false
U9_REPLAY=false
DESTRUCTIVE_U10_REPLAY=false
HOST_USB_TRANSACTION_MUTATION=false
U11_PLUS=false
PRODUCTION_SOURCE_OVERWRITE=false
MERGE=false
NEXT_SAFE_ENTRY_POINT=NEW_EXPLICIT_EXACT_437F_SINGLE_FILE_REPLACEMENT_AND_ONE_OTA_RESTART_AUTHORIZATION_BOUNDARY
```

Existing source and regression evidence remain bound to the original CI authority. This document closes the read-only gate only.
