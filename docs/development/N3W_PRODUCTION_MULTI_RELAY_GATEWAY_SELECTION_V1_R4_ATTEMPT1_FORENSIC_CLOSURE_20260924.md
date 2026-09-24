# N3-W Production Multi-Relay Gateway Selection V1 — R4 Attempt 1 Forensic Closure

Date: 2026-09-24

## Fresh readonly forensic result

```text
BOARD_A_SOURCE_CURRENT=relay
BOARD_A_ACTIVE_GATEWAY=BOARD_B
BOARD_A_R4_R7_BOOT_MATCH=true

BOARD_B_SOURCE_CURRENT=direct
BOARD_B_R4_R7_BOOT_MATCH=true

BOARD_C_SOURCE_CURRENT=direct
BOARD_C_R4_R7_BOOT_MATCH=true

STABLE_HASH_TIE_WINNER=BOARD_B

CANDIDATE_RSSI_POST_EVENT_AVAILABLE=false
CANDIDATE_SET_POST_EVENT_AVAILABLE=false
CANONICAL_CURSOR_PROVES_SELECTED_GATEWAY_ONLY=true

MANAGER_RESTART_COUNT=0
T1_MUTATION=false
DATABASE_MUTATION=false
SERVICE_RESTART=false
BOARD_MUTATION=false

RESULT=PASS_R4_FAILURE_READONLY_FORENSIC
```

## Interpretation

The frozen Gateway Selection V1 policy uses RSSI first, but any candidate within 3 dB of the strongest candidate enters the equivalent-quality band. The stable child+Relay SHA-256 rule resolves that band.

For this exact A/B/C identity set:

```text
STABLE_HASH_TIE_WINNER=BOARD_B
```

Therefore the observed selection of Board B is fully consistent with intended policy if Board A actually measured B and C within 3 dB during the 6500 ms candidate window.

The physical operator confirmation that C was "clearly stronger" was not backed by the candidate RSSI values actually collected inside Board A. Those RAM-only candidate values are cleared after selection and are not recoverable from the canonical cursor.

The same observed result is also consistent with Board C not entering the candidate set during that particular window.

## Acceptance disposition

```text
R4_ATTEMPT_1=INCONCLUSIVE_PHYSICAL_PRECONDITION
R4_PRODUCT_SOURCE_DEFECT=NOT_PROVEN
R4_ACCEPTANCE=OPEN
R5_EXECUTION=BLOCKED_UNTIL_R4_PASS
```

Do not count Attempt 1 as an R4 PASS. Do not count it as a proven production defect.

## Recovery route

Restore Board A to Direct on the same R4-R7 boot authority, then repeat R4 with a substantially larger physical RF separation: Board C stays fixed; Board B remains Direct and still viable as Relay, but is placed much farther from / more obstructed from A's Relay test location so the intended C advantage is well beyond the 3 dB equivalent band.

```text
NEXT_ONE_GATE=
N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_R4_ATTEMPT2_A_SAME_BOOT_DIRECT_RESTORE_20260924_01
NEXT_GATE_AUTHORIZED=true
```
