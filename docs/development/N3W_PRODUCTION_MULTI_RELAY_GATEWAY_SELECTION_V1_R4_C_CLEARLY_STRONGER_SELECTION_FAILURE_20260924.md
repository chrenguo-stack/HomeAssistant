# N3-W Production Multi-Relay Gateway Selection V1 — R4 C-Clearly-Stronger Selection Failure

Date: 2026-09-24

## Observed result

```text
R4_EXPECTED_GATEWAY=BOARD_C
R4_OBSERVED_FIRST_GATEWAY=BOARD_B
RESULT=STOP_R4_SELECTED_B_INSTEAD_OF_CLEARLY_STRONGER_C
```

Preconditions recorded by the physical executor:

```text
B_AND_C_VIABLE_CONFIRMED_BY_OPERATOR=true
C_CLEARLY_STRONGER_THAN_B_CONFIRMED_BY_OPERATOR=true
BOARD_C_MOVEMENT=false

BOARD_A_PREMOVE_SOURCE=direct
BOARD_A_PREMOVE_SEQ=20
BOARD_A_PREMOVE_BOOT_SHA256=
7f9468e1ead5b54d2db26493ca59982e97482cba23f7ba803ed2f3d48e6103d9

BOARD_B_PREMOVE_SOURCE=direct
BOARD_B_PREMOVE_SEQ=20

BOARD_C_PREMOVE_SOURCE=direct
BOARD_C_PREMOVE_SEQ=155

MOVE_START_TIME=2026-09-24T11:57:36.532957Z
FIRST_RELAY_GATEWAY=BOARD_B
```

## Classification

This is a valid R4 acceptance mismatch and R4 is not closed PASS.

It is not yet sufficient to classify the frozen production source as defective because the physical premise "C clearly stronger than B" was operator-confirmed but not instrumented with the RSSI values actually collected by Board A.

```text
R4_ACCEPTANCE=FAIL_OBSERVED_GATEWAY_MISMATCH
R4_PRODUCT_SOURCE_DEFECT=NOT_YET_PROVEN
ROOT_CAUSE=OPEN
R5_EXECUTION=BLOCKED
R6_EXECUTION=BLOCKED
R7_EXECUTION=BLOCKED
```

## Frozen-source forensic facts

Source authority:
`8c445f2bdd60d9ac3a33fe7c20a01965360a3b1c`

The frozen source:
- starts a 6500 ms candidate window on the first admissible Relay discovery;
- aggregates every valid same-channel discovery RSSI sample by arithmetic mean;
- selects the strongest mean RSSI candidate;
- treats every candidate within 3 dB of the strongest mean as equivalent;
- applies the stable child+relay SHA-256 tie-break inside that <=3 dB band;
- keeps candidate RSSI aggregates in RAM-only selection state;
- clears the candidate state after successful Relay activation;
- does not expose the candidate mean RSSI values through the production diagnostic surface.

Therefore the post-event canonical cursor proves the selected Gateway but cannot by itself prove whether:
1. both B and C entered the candidate set;
2. C's measured mean RSSI was actually >3 dB stronger than B;
3. B won the stable-hash tie-break inside an actual <=3 dB band.

## Next gate

```text
NEXT_ONE_GATE=
N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_R4_FAILURE_READONLY_FORENSIC_20260924_01
NEXT_GATE_AUTHORIZED=true

PHYSICAL_MOVEMENT=false
POWER_CHANGE=false
BOARD_RESET=false
FLASH_MUTATION=false
NVS_MUTATION=false
T1_MUTATION=false
DATABASE_MUTATION=false
SERVICE_RESTART=false
```
