# N3-W R10 phone-centric pairing UI and LCD simplification source repair — 2026-10-29

## Result boundary

```text
TASK=N3W_SCAN_TRIGGERED_FIRST_PAIRING_R10_PHONE_CENTRIC_PAIRING_UI_AND_LCD_SIMPLIFICATION_SOURCE_REPAIR_20261029_01
SOURCE_BASE=e299c937a7b89bb8a7b9a7432186ba46a416cd44
SOURCE_BRANCH=fix/n3w-r10-phone-centric-pairing-ui-lcd-cycle-20261029
CODE_HEAD_BEFORE_DOCS=251d6f752afff5bf6a17b34af8dd74383215b085

REPOSITORY_MUTATION=true
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
BOARD_WRITE=false
NVS_WRITE=false
MERGE=false
```

This repair follows the physical R10 STOP before any phone scan. The T1 post-boot/pre-scan
baseline had remained idle and unchanged; the Board D run was interrupted by the production
3.00 V low-battery policy after the previously proven development-only -1.00 V bypass had
been replaced by the exact R9 production image.

The low-battery bench bypass is deliberately **not** part of this product-source repair.

## Frozen product interaction

### LCD

The LCD is a persistent device-status surface, not the pairing wizard.

- normal five-page rotation continues before, during and after registration;
- page 5 shows the existing Wi-Fi setup QR when Wi-Fi is not connected;
- with Wi-Fi connected and the product unregistered, page 5 shows the registration QR;
- after durable registration success, page 5 shows `已联机注册`;
- discovery, candidate selection, registration progress, success latch and E01-E07 errors do
  not take over the LCD page cycle.

### Phone page

Scanning the QR opens the node-local page but does not start T1 discovery or a registration
transaction.

The explicit user sequence is:

```text
scan QR
-> phone page
-> 寻找主机
-> select candidate when needed
-> 开始注册
-> SUCCESS or terminal failure/timeout
```

Rules:

- `寻找主机` is the only discovery trigger;
- candidate selection alone does not create the first-registration transaction;
- `开始注册` is the irreversible user boundary for that attempt;
- there is no user-facing cancel action and no product `/v1/registration/cancel` API;
- browser close/backgrounding is not cancellation;
- transient automatic-retry states remain `正在注册` rather than being projected as a false
  terminal error;
- terminal errors remain visible on the phone page and include an E-code plus Chinese text;
- success is bound to the existing provisioned/durable-COMMIT authority;
- the portal remains available for a bounded 15 s success-delivery grace so an already-open
  phone page can observe terminal success;
- explicit retry is available only after an attempt has returned to a terminal error/search
  failure state.

## Source changes

### Node-local registration portal

`n3w_registration_portal.{h,cpp}` now separates:

- `IDLE`
- `DISCOVERING`
- `WAIT_CONFIRM`
- `CANDIDATE_SELECTED`
- `SELECTED_PENDING_BOOTSTRAP`
- `SUCCESS`
- `ERROR_NO_CANDIDATE`
- `ERROR`

New node-local `POST /api/v1/register/begin` moves the already-selected, still-valid
candidate from `CANDIDATE_SELECTED` to `SELECTED_PENDING_BOOTSTRAP`. The component can
consume a selected candidate only after that transition.

Page load performs status recovery only. It does not call the discovery start endpoint.

### Product component

Existing transaction, TLS pinning, Setup Secret, pairing and durable commit authorities are
unchanged.

The component now projects terminal registration results into the phone portal. Success keeps
the portal alive for a bounded delivery grace. Transient HTTP/pending-ACK recovery states do
not publish a false terminal error.

### LCD

`display.yml` no longer computes or uses `force_registration_page`. The rendered page is
always `display_page`. Page 5 no longer consumes the short-lived R7 registration state/error
latches.

The internal R7 display model is retained for compatibility and diagnostics, but it is no
longer an LCD workflow authority.

## Regression guards

The historical R4/R5/R7/R8 source contracts are updated only where they encoded behavior now
superseded by this product decision.

A new
`tests/n3w_registration/test_scan_triggered_first_pairing_r10_phone_ui_contract.py`
requires:

1. QR page load is passive until `寻找主机`;
2. candidate selection does not start registration;
3. `开始注册` is a distinct explicit action;
4. no user cancel path exists;
5. terminal feedback belongs to the phone page;
6. LCD never locks to page 5 for registration;
7. the success-delivery grace is bounded;
8. transient retries cannot masquerade as terminal failure;
9. the production UI branch does not contain the development-only -1.00 V battery bypass.

CI runs this contract after the R8 safety contract.

## Low-battery acceptance overlay boundary

The already-proven Board D development bypass remains a separate acceptance concern:

```text
battery_low_threshold: "-1.00"
```

It must be introduced only in a later R10 physical-acceptance overlay/artifact with explicit
non-production markers, for example:

```text
PHYSICAL_ACCEPTANCE_ONLY=true
PRODUCTION_ELIGIBLE=false
LOW_BATTERY_PROTECTION_BYPASSED=true
```

It must not be merged into the product UI source repair.

## Physical boundary

No Board D reboot, write, erase, NVS mutation, phone scan or T1 live mutation is authorized by
this source repair. The interrupted R10 physical attempt remains stopped. A successor exact
artifact and a new one-shot physical authorization are required before physical work resumes.
