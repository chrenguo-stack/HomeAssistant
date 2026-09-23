# N3-W Production Multi-Relay Gateway Selection V1 — P1B operator-reboot rebaseline

Status: `IN_PROGRESS`

The first P1B observer stopped before the Relay movement because Board C's boot session
no longer matched the P1A session. The operator confirmed that this boot change was
caused by physically moving Board C.

This is classified as an operator-induced test interruption, not a product failure.

```text
P1A_GATEWAY_A_QUALIFICATION=PASS
P1A_EVIDENCE_RETAINED=true

P1B_FIRST_ATTEMPT=STOP_BEFORE_RELAY_MOVEMENT
P1B_PRODUCT_FAILURE=false
BOARD_C_REBOOT_CAUSE=OPERATOR_CONFIRMED_PHYSICAL_MOVEMENT
OLD_P1A_BOOT_NOT_REUSABLE_FOR_P1B=true

P1B_REQUIRED_RECOVERY=
FRESH_DIRECT_BASELINE_AND_FRESH_BOOT_BINDING

P1B_REQUIRE_SAME_BOOT_FROM_P1A=false
P1B_REQUIRE_SAME_BOOT_WITHIN_P1B=true

NEXT_ONE_GATE=
N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_P1_GATEWAY_B_REBASELINE_AND_QUALIFICATION_20260923_02
```

The R2 physical plan says C should return to Direct without power-cycle between
individual Gateway qualifications when practical. Therefore the reboot does not
invalidate the already completed A-only qualification, but P1B must establish a new
fresh Direct baseline and bind the new C boot before movement.
