# N3W T1 Core Stack Clean Reference R3 pairing-readiness repaired readonly preflight — listener parse false-PASS repair progress

Date: 2026-11-02

~~~text
TASK=N3W_T1_CORE_STACK_CLEAN_REFERENCE_R3_PAIRING_READINESS_BRIDGE_REPAIRED_READONLY_PREFLIGHT_20261102_01
STATE=STOP_SOURCE_REPAIR_CI_PENDING

LOCAL_PACKAGE_AUTHORITY=PASS

T1_BOOT_ID=dc0f29fd-59f9-4f4c-ae79-206db2b22002
T1_SYSTEM_STATE=running
FAILED_UNIT_COUNT=0
RUNTIME_CONTAINER_COUNT=3
MANAGER_RESTART_COUNT=0

BRIDGE_STATE_PRESENT=false
PROVISIONING_ROOT_PRESENT=false
FACTORY_ACCEPTED_PRESENT=false
FIRST_PAIRING_TRANSACTION_PRESENT=false
SUCCESSOR_RECOVERY_PRESENT=false
TEMP_TRANSPORT_RESIDUAL_COUNT=0

PAIRING_UDP_LISTENER_COUNT=1
PAIRING_TCP_LISTENER_COUNT=0

NEW_SOURCE_DEFECT=PAIRING_LISTENER_LOCAL_ADDRESS_COLUMN_FALSE_PASS
ROOT_CAUSE=bridge _listener_count used line.split()[4] peer-address column instead of line.split()[3] local-address column
FALSE_PASS_RISK=true

REPAIR_HEAD=dab3ccc3826fe0c1c691b3a9122674862734b4fd
REPAIR_BRIDGE_BLOB=e138d0e19134707079e2eb5344aa66ff3ecae71b
REPAIR_TEST_BLOB=e6070410b413c4fb10ff583839190b1c0a8e678b

CI_RUN=41374354232
CI_STATE=QUEUED_AFTER_3_POLLS
CI_CONCLUSION=NOT_AVAILABLE

AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
FACTORY_ACCEPTED_CREATED=false
PAIRING_WINDOW_OPENED=false
T1_MUTATION=false
BOARD_ACCESS=false
MERGE=false

NEXT_ACTION=READ_CI_RUN_41374354232_WHEN_COMPLETE_THEN_IDENTIFY_REAL_UDP_47111_OWNER_WITH_CORRECT_LOCAL_ADDRESS_COLUMN
~~~

## Result

The repaired read-only preflight stopped before bridge inspect because the live T1 baseline
showed one UDP listener on port 47111 while the expected pairing-closed state requires zero.

A follow-up diagnostic command incorrectly filtered the peer-address column and therefore
printed no listener rows. Independent source review then found the same column-selection bug
inside the bridge itself: `_listener_count()` parsed `line.split()[4]`, which is the peer
address in `ss -H -lun/-ltn` output, rather than `line.split()[3]`, the local address.

This creates a real false-PASS route: a live pairing listener can exist while the bridge reports
zero listeners.

## Bounded repair

Repair commit `dab3ccc3826fe0c1c691b3a9122674862734b4fd` changes only the listener parser and
focused tests.

The parser now evaluates the local-address column. Tests cover:

- a UDP 47111 local listener is counted;
- a TCP 47112 local listener is counted;
- a peer-address occurrence alone does not count as a local listener.

No T1 mutation, service restart, marker creation, pairing-window action, Board access, or merge
occurred.

## CI stop point

Focused CI run `41374354232` was still queued after three polls, so polling stopped.

After CI success, the next read-only action is to identify the actual UDP 47111 owner using the
correct local-address column. Do not run bridge inspect until that listener is understood.
