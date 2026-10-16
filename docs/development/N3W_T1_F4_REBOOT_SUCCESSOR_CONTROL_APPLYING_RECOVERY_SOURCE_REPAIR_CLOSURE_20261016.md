# N3-W T1 F4 reboot successor CONTROL_APPLYING recovery source-repair closure

Date: 2026-10-16

```text
EXECUTION_ID=N3W_T1_F4_REBOOT_SUCCESSOR_CONTROL_APPLYING_RECOVERY_SOURCE_REPAIR_20261016_01
RESULT=CLOSED_PASS

PR=605
SOURCE_REVIEW_HEAD=da64d1cdfbe7e198abc1d536014769f56471d0cb
SOURCE_REVIEW_TREE=93e9308fa58e680a95b9b4dfb6314023dcd6f911
PR_STATE=OPEN_DRAFT_NOT_MERGED

AUTHORIZATION=NOT_APPLICABLE:SOURCE_ONLY_GATE
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false

FOCUSED_TESTS=PASS:N3W_T1_F4_ACTIVATION_SOURCE_CI_207
PUBLIC_REPOSITORY_SAFETY=PASS
EXACT_CONTROL_PACKAGE_CI=PASS
GITHUB_CI=PASS:13/13
FOCUSED_SOURCE_REVIEW=PASS

RECOVERY_AUTHORIZATION_REPLAY_GUARD=PASS
CONTROL_APPLYING_RECOVERY_CONTRACT=PASS
CONTROL_READY_COMMIT_ORDERING=PASS
RECOVERY_APPLYING_DURABILITY_READBACK=PASS
RECOVERY_REBOOT_AND_BOARD_MARKER_GUARD=PASS

LIVE_RUNTIME_MUTATION=false
T1_ACCESS=false
LIVE_RECOVERY_EXECUTED=false
LIVE_RECOVERY_AUTHORIZATION_CLAIMED=false
REBOOT_AUTHORIZATION_CLAIMED=false
REBOOT_EXECUTED=false
CERTIFICATE_LIFECYCLE_TRIGGERED=false
BOARD_ACCESS=false
MERGE=false

SOURCE_REPAIR_RESULT=CLOSED_PASS
NEXT_ROUTE=N3W_T1_F4_REBOOT_SUCCESSOR_CONTROL_APPLYING_RECOVERY_ARTIFACT_AND_READONLY_PREAUTH
AUTO_EXECUTE_NEXT_ROUTE=false
STOP=true
```

## Closure summary

The dedicated `CONTROL_APPLYING` recovery path is source-complete and fail-closed.

The recovery flow now:

1. accepts only the exact historical `CONTROL_APPLYING` install claim;
2. preserves the original consumed install authorization as permanently non-replayable;
3. requires a fresh independent recovery authorization for any future live recovery;
4. binds the exact historical installed files and manifest before replacement;
5. binds the repaired exact package and package-owned recovery entrypoint;
6. binds the F4 transaction, runtime identity, certificate identity, certificate status and boot identity;
7. durably persists and reads back `RECOVERY_APPLYING` before the first target replacement;
8. verifies repaired installed bytes and the repaired runtime guard before persisting `RECOVERY_VERIFIED`;
9. persists `CONTROL_READY` only after the complete recovery verification record is durable;
10. rejects recovery-state drift indicating reboot or board access;
11. leaves partial failures fail-closed rather than replaying the consumed recovery authorization.

The final exact source head passed all 13 observed workflows. The F4 source CI passed Python compilation, Ruff, focused F4 tests, the static F3-to-F4 boundary check, and the provisioning replay guard.

This is a source-only closure. It does not prove that the real T1 has been recovered. The last proven real T1 install claim remains `CONTROL_APPLYING` from the prior read-only forensic evidence. No T1 connection, file replacement, restart, reboot, certificate lifecycle action, board access, authorization claim, or PR merge occurred in this gate.

## Next boundary

The next route is only:

```text
N3W_T1_F4_REBOOT_SUCCESSOR_CONTROL_APPLYING_RECOVERY_ARTIFACT_AND_READONLY_PREAUTH
```

It must not be auto-executed. Any later live recovery still requires fresh read-only evidence, an exact recovery artifact binding, and a separate explicit one-shot live recovery authorization.
