## 2026-11-03 acceptance correction — terminal replay tombstone is compatible with semantic zero-node

The first post-upgrade acceptance harness stopped only because it required all historical business-table counts to be zero. Aggregate-only diagnosis proved:

```text
credential_assignments=0
first_registration_attempts=1
node_id_leases=0
pairing_sessions=0
registration_events=0
registration_node_history=0
registrations=0
retirement_outbox=0

ONLY_ATTEMPT_STATE=EXPIRED
ONLY_ATTEMPT_PHASE=TERMINAL
ONLY_ATTEMPT_CLEANUP_STATE=COMPLETE

replay_node_count=0
replay_tuple_count=0
relay_active_node_count=0
relay_key_file_count=0
```

This does not represent a current node or unresolved registration. Project ADR/source authority explicitly retains terminal first-registration rows as replay tombstones and defines unresolved state as ACTIVE or terminal rows whose cleanup is not COMPLETE.

Correct acceptance rule:

```text
SEMANTIC_ZERO_NODE=
  registrations=0
  AND node_id_leases=0
  AND credential_assignments=0
  AND pairing_sessions=0
  AND unresolved_first_registration_count=0
  AND replay_node_count=0
  AND replay_tuple_count=0
  AND relay_active_node_count=0
  AND relay_key_file_count=0

TERMINAL_COMPLETE_FIRST_REGISTRATION_TOMBSTONES=ALLOWED_AND_PRESERVED
```

No cleanup or mutation is authorized. The tombstone must not be deleted merely to satisfy an empty-table oracle. The final recheck is read-only.

# N3-W T1 Core Updater repaired Manager A -> B live apply closure and post-upgrade acceptance preparation — 2026-11-03

## Live apply result

```text
GATE=N3W_T1_CORE_UPDATER_MANAGER_A_TO_B_LIVE_APPLY_V2_KF137_REPAIRED_EXECUTION_20261103_01
RESULT=PASS

REPAIRED_PRE_APPLY_GATE=PASS
APPLY_RC=0
TRANSACTION_STATUS=COMMITTED
TRANSACTION_PHASE=COMMITTED
RECOVERY_REQUIRED=false

LIVE_MANAGER=local/greenhouse-manager:fresh-3539c8f871e2
MANAGER_RUNTIME_IMAGE_ID=sha256:9dd128f0700840d46d300f9a434e2d3fbf5abba7abbd03c7dd432e9f497be035
MANAGER_RESTART_COUNT=0

HOMEASSISTANT_IMAGE_UNCHANGED=true
HOMEASSISTANT_RESTART_COUNT=0
BROKER_RUNTIME_UNCHANGED=true
BROKER_RESTART_COUNT=0

LISTENER_CONTRACT=PASS
T1_MUTATION=true
SECOND_APPLY_EXECUTED=false
EXPLICIT_ROLLBACK_EXECUTED=false
BOARD_ACCESS=false
```

## Exact repaired updater authority

```text
MAIN=13afc9d68824a20af2ca6c6efac515c94ed90cdf
UPDATER_REVIEWED_HEAD=06866acc9ff8f1e9acb7c3e23097a53031e9b313
UPDATER_MERGE_COMMIT=2e3f1c72e5ac17a9c8a1ecb378148a0d6d2d8c29
PACKAGE_RUN_ID=41561467986
PACKAGE_ARTIFACT_ID=13196564439
UPDATER_PYZ_SHA256=6222ab4bdcb53e0b612777a585111f5ab2ab114a1c52a4997252937ef27033cc
MANAGER_TAR_SHA256=0038286140758c27c66eeb005d2a7ea4aec4538ad94447a44021bb61de7e51f0
```

## Acceptance boundary

The immediate post-apply inspection passed, but repository live-deployment authority is intentionally not switched yet. A separate read-only post-upgrade acceptance must freshly prove:

- updater transaction remains COMMITTED / COMMITTED;
- recovery_required remains false;
- Manager B remains the live binding and exact T1-local runtime image;
- production services owner remains active/enabled with the frozen ExecStart/ExecStop contract;
- Home Assistant image/network identity remains unchanged;
- Broker container/image/start/restart identity remains unchanged;
- listener contract remains exact;
- no unexpected rollback or second mutation occurred.

```text
CURRENT_REPOSITORY_LIVE_DEPLOYMENT_STATE=NOT_YET_APPLIED
LIVE_RUNTIME_MANAGER_B=true
POST_UPGRADE_ACCEPTANCE=PENDING
NEXT_ONE_GATE=N3W_T1_CORE_STACK_MANAGER_B_POST_UPGRADE_LIVE_ACCEPTANCE_20261103_01
BOARD_ACCESS=false
```

Only after that acceptance closes PASS may the canonical repository live-deployment authority move from NOT_YET_APPLIED to applied/current B.
