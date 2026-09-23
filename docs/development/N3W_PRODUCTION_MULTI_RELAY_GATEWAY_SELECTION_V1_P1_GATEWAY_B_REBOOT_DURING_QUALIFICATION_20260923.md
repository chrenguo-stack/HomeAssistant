# N3-W Production Multi-Relay Gateway Selection V1 — P1B reboot during qualification

Status: `STOP_INCONCLUSIVE`

The second P1B attempt established a fresh B/C Direct baseline successfully, then stopped
during the B-only Relay qualification because Board C changed boot session after the
fresh baseline.

```text
P1A_GATEWAY_A_QUALIFICATION=PASS
P1A_EVIDENCE_RETAINED=true

P1B_FRESH_DIRECT_REBASELINE=PASS

BOARD_A_INACTIVE=true

BOARD_B_SOURCE_REBASELINE_BEFORE=direct
BOARD_B_SOURCE_REBASELINE_AFTER=direct
BOARD_B_SEQ_REBASELINE_BEFORE=3
BOARD_B_SEQ_REBASELINE_AFTER=5
BOARD_B_SAME_BOOT=true
BOARD_B_CANONICAL_ADVANCED=true

BOARD_C_SOURCE_REBASELINE_BEFORE=direct
BOARD_C_SOURCE_REBASELINE_AFTER=direct
BOARD_C_SEQ_REBASELINE_BEFORE=1
BOARD_C_SEQ_REBASELINE_AFTER=3
BOARD_C_SAME_BOOT=true
P1B_FRESH_C_BOOT_SESSION_SHA256=80f588aeb6303551bc7b7565477a1991877e1b557c4e15098ec0987f130d3076

P1B_OBSERVATION_LAST_PROGRESS_SECONDS=255
STOP_REASON=BOARD_C_BOOT_SESSION_CHANGED_DURING_P1B

C_CAN_RELAY_THROUGH_B=NOT_PROVEN
P1_GATEWAY_B_QUALIFICATION=INCONCLUSIVE
PRODUCT_RELAY_FAILURE=NOT_PROVEN

BOARD_FLASH_WRITE=false
BOARD_NVS_WRITE=false
T1_RUNTIME_MUTATION=false

NEXT_ONE_GATE=
N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_P1_GATEWAY_B_REBOOT_CAUSE_REVIEW_20260923_01
```

Because the boot changed after the fresh P1B baseline, this attempt cannot be used as a
same-boot Direct -> Relay qualification. The evidence does not by itself distinguish
an operator/power interruption from a device/runtime reset. Do not classify this as a
Gateway-B relay-path product failure without separate reset-cause evidence.
