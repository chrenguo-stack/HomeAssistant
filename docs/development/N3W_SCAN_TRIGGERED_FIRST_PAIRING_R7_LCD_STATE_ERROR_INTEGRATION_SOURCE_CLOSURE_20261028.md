# N3W Scan-Triggered First Pairing R7 — LCD State/Error Integration Source Closure

Date: 2026-10-28

Gate:

`N3W_SCAN_TRIGGERED_FIRST_PAIRING_R7_LCD_STATE_ERROR_INTEGRATION_SOURCE_CLOSURE_20261028_01`

## 1. Scope

This document closes the R7 source implementation/review stage only.

Included:
- exact-source rebind;
- exact-head CI closure;
- independent source review;
- hardware-SPI evidence;
- LCD state/error integration review;
- false-PASS review;
- next-gate recommendation.

Not included:
- merge authorization;
- T1 access or mutation;
- board access or flashing;
- live runtime mutation;
- physical LCD acceptance;
- exact physical artifact nomination.

## 2. Source authority

Repository:

`chrenguo-stack/HomeAssistant`

Frozen R7 design/preflight head:

`e7fd7939215759f0433391d16a28a53d85d50bcf`

R7 implementation PR:

`#702`

Final exact R7 product-source head:

`aee4966b39140a36a9b259a643c138e9f26d0c6d`

PR #702 remained:
- open;
- draft;
- unmerged;
- no review threads;
- no reviews.

Repository `main` remained exactly:

`2fbd0e9c2d3bf8a513ac318034e249511ffb6a2e`

Fresh compare against `main`:
- status: identical;
- ahead: 0;
- behind: 0.

Therefore no main/source drift contaminated the R7 review.

## 3. Exact implementation delta

Compared with the frozen R7 design head, the exact implementation changes only:

```text
.github/workflows/greenhouse-manager-ci.yml

firmware/esphome_rc/components/greenhouse_n3w_core/
  n3w_registration_display.cpp
  n3w_registration_display.h
  n3w_registration_portal.cpp
  n3w_registration_portal.h
  n3w_simple_product_component.cpp
  n3w_simple_product_component.h

firmware/esphome_rc/f1_0_rc2/packages/
  display.yml
  n3w_product_transport.yml

tests/n3w_registration/
  n3w_registration_display_host_test.cpp
  test_scan_triggered_first_pairing_r7_lcd_state_contract.py
```

No Manager/T1 source, NVS schema, pairing crypto, Broker/DynSec or Home Assistant source was changed.

## 4. Exact-head CI result

Final exact head:

`aee4966b39140a36a9b259a643c138e9f26d0c6d`

Workflow summary:

```text
SUCCESS=24
FAILURE=0
PENDING=0
```

Successful workflows include:
- greenhouse-manager CI;
- F1.0-RC2 firmware CI;
- N3W current-main product source convergence R3 CI;
- N3W Board_D R4 production de-harness CI;
- N3W production multi-relay gateway selection V1 CI;
- N3W production relay discovery full-channel fallback V1 CI;
- N1 ESP32-C6 MQTT firmware CI;
- M0/M2/H3/C-07 regression workflows.

The greenhouse-manager cross-language job passed the R4/R5/R6 focused contracts and the new R7 source/host contracts.

The F1.0-RC2 firmware job successfully validated and compiled the formal production target:

`f1_0_rc2_n3w_target.yml`

## 5. Hardware SPI closure

R7 explicitly changed the LCD bus contract to:

```yaml
spi:
  id: bus_spi
  clk_pin: GPIO2
  mosi_pin: GPIO3
  interface: hardware
```

Latest exact-head production configuration output proves:

```text
interface: hardware
interface_index: 0
```

The exact-head build also compiled:
- ESPHome `spi_esp_idf.cpp`;
- ESP-IDF `spi_master.c`.

The formal N3-W product target then linked successfully.

Therefore:

```text
LCD_HARDWARE_SPI_REQUIRED=true
LCD_HARDWARE_SPI_ACCEPTED_BY_ESPHOME=true
LCD_HARDWARE_SPI_ACCEPTED_BY_ESP32C6_BUILD=true
SOFTWARE_SPI_FALLBACK_ALLOWED=false
```

The following remain unchanged:
- ST7920 `data_rate: 1MHz`;
- display `update_interval: 1s`.

This proves the transport implementation is hardware SPI. It does not claim a measured runtime CPU percentage reduction; that would require physical/runtime profiling.

## 6. R7 display model closure

Final states:

```text
IDLE_UNREGISTERED = 0
DISCOVERING       = 1
WAIT_CONFIRM      = 2
REGISTERING       = 3
SUCCESS           = 4
ERROR             = 5
```

Final user error classes:

```text
E01 = 未找到主机
E02 = 主机不可用
E03 = 主机忙
E04 = 网络中断
E05 = 注册超时
E06 = 注册失败
E07 = 二维码失效
```

The product component is the state authority.

The YAML/display layer only mirrors and renders the component state.

No second pairing/registration business state machine was introduced.

## 7. Display-only latch review

The new `RegistrationDisplayController` is isolated from:
- network;
- NVS;
- Setup Secret;
- pairing ID;
- 47110/47112;
- Manager/T1;
- transaction renewal.

Frozen presentation windows:

```text
SUCCESS = 3000 ms
ERROR   = 5000 ms
```

Behavior reviewed:
- same visible error does not continuously extend its own latch;
- a different error may replace a previous error;
- committed SUCCESS dominates a late display error during its active display window;
- expired latch returns to the current base display state.

These timers are presentation-only.

They do not:
- refresh the Manager 1800-second deadline;
- create/renew pairing IDs;
- erase provisional state;
- close 47112;
- change registration authority.

## 8. SUCCESS authority review

R7 does not infer success from:
- browser confirm accepted;
- 47110 accepted;
- credential bundle receipt;
- provisional NVS writes;
- final ACK HTTP 200 alone;
- `pairing_handoff_ready`;
- MQTT connection.

The source calls `show_registration_success_()` only inside branches already guarded by:

`pairing_client_.provisioned() == true`

This preserves the existing R6 success authority:
- exact committed/finalized registration path;
- exact pending-ACK recovery path.

Therefore:

```text
SUCCESS_FALSE_PASS_PATH_FOUND=false
R6_FINAL_ACK_AUTHORITY_PRESERVED=true
```

## 9. Pending-ACK review

R6 pending ACK continues to own recovery priority.

R7 display behavior:
- pending ACK -> REGISTERING;
- WAIT/UNKNOWN recovery -> remains REGISTERING;
- committed recovery -> SUCCESS;
- terminal cleanup/renewal -> E07;
- persistence/local failure -> E06.

No R7 display branch can independently mark a pending transaction committed.

## 10. Error-mapping review

### E01

A completed user-triggered discovery with zero valid candidates shows E01.

Candidate-list expiry during the current valid browser session is exposed as a one-shot event and shows E01.

### E02

47110 bootstrap connection/TLS/pin transport failure maps to E02 when the node still has Wi-Fi.

This is display-only and does not permit fallback to a different T1.

### E03

Exact `registration_busy` confirm response maps to E03.

### E04

Network interruption during an active registration path maps to E04.

The one-shot Wi-Fi-loss display flag prevents a tight loop from continuously re-latching E04.

### E05

Local safe transaction deadline reached maps to E05.

The R6 rule remains unchanged:
- local timeout does not renew pairing identity;
- authoritative terminal classification still belongs to 47110/T1.

### E06

Protocol/crypto/persistence/local correctness failures map to E06.

### E07

Current valid stale candidate/session and durable transaction renewal map to E07.

Arbitrary wrong-token LAN requests do not directly create E07.

## 11. Portal event review

R7 adds two narrow one-shot UI events:

```text
candidate_stale_event_pending
candidate_list_expired_event_pending
```

They are cleared when the portal stops/restarts.

The stale-candidate event is raised only after:
- source is local;
- the portal action schema/token passes validation;
- the candidate cannot be accepted in the current valid session.

Therefore an arbitrary invalid scan token cannot force the product LCD into E07.

No Setup Secret is added to the browser/portal surface.

## 12. LCD rendering closure

The obsolete idle LCD behavior:

`正在查找主机`

is no longer present in the registration LCD page.

Final product-facing registration copy includes:
- 联机注册;
- 扫码注册;
- 正在搜索;
- 等待确认;
- 请看手机;
- 联机注册中;
- 请稍候;
- 注册成功;
- E01-E07 error text.

The browser may still use a searching phrase during an actual user-triggered discovery; R7 did not incorrectly remove that browser behavior.

## 13. Glyph and layout review

R7 expanded the configured BDF glyph allowlists for the new registration vocabulary.

The source contract verifies:
- every configured R7 line has glyph coverage in the exact selected font;
- configured monospaced text width is bounded by the logical 64-pixel page width;
- E01-E07 fit the selected font/width;
- page-5 display copy contains no private registration/credential fields.

Physical aesthetics such as perceived centering, font visual weight, QR visual spacing and enclosure viewing angle remain R10 physical/UI acceptance concerns.

## 14. Page-5 visibility false-PASS and repair

During independent closure review, the first full-green implementation exposed a display-scheduling false-PASS risk.

Initial approach:
- normal `control.yml` increments `display_page` every 4 seconds;
- the N3-W presentation bridge forced `display_page=4` every 1 second.

Those were independent timers, so a transient non-registration frame could not be excluded.

This was repaired before closure.

Final exact source does **not** mutate `display_page` from the 1-second bridge.

Instead, at render time:

```text
force_registration_page =
  pairing display enabled
  AND (
    unprovisioned
    OR display state == SUCCESS
    OR display state == ERROR
  )

page = force_registration_page ? 4 : display_page
```

Consequences:
- unregistered product UI remains physically on page 5;
- SUCCESS/ERROR remain physically on page 5 for their bounded latches;
- no timer race writes the page counter;
- after success expires on a provisioned node, ordinary five-page rendering resumes at the then-current page counter.

The original 4-second page cadence remains unchanged.

## 15. Display priority review

Final effective display priority remains:

```text
1. low-battery protection overlay
2. R7 SUCCESS / ERROR registration result
3. Wi-Fi provisioning/reconnect screen
4. unprovisioned R7 registration state
5. provisioned normal page-5 connected state
```

The low-battery branch still returns before ordinary page rendering.

R7 does not mutate registration state when low-battery UI is displayed.

## 16. Existing product behavior preserved

R7 does not change:
- R5 user-triggered discovery;
- multi-T1 explicit selection;
- R6 selected-T1 TLS pinning;
- Setup Secret transport ordering;
- 47110 confirm/status contract;
- 47112 pairing crypto;
- strict final ACK parsing;
- pending-ACK durable recovery;
- terminal cleanup ordering;
- T1 relocation identity binding;
- Direct/Relay runtime architecture;
- MQTT/Broker lifecycle.

## 17. Secret-surface review

R7 LCD copy does not contain:
- Setup Secret;
- pairing ID;
- raw hardware ID;
- manager ID;
- system ID;
- TLS fingerprint;
- MQTT password.

No sensitive registration material was added to GitHub evidence or UI copy.

## 18. Final source review result

```text
GATE=N3W_SCAN_TRIGGERED_FIRST_PAIRING_R7_LCD_STATE_ERROR_INTEGRATION_SOURCE_CLOSURE_20261028_01

R7_EXACT_HEAD=aee4966b39140a36a9b259a643c138e9f26d0c6d
EXACT_HEAD_CI=PASS
CI_SUCCESS_COUNT=24
CI_FAILURE_COUNT=0
CI_PENDING_COUNT=0

MAIN_DRIFT=false
UNRESOLVED_REVIEW_THREAD_COUNT=0

R7_STATE_MODEL=PASS
R7_ERROR_MAPPING=PASS
R7_SUCCESS_AUTHORITY=PASS
R7_PENDING_ACK_DISPLAY=PASS
R7_PORTAL_EVENT_BOUNDARY=PASS
R7_GLYPH_LAYOUT_SOURCE_CONTRACT=PASS
R7_PAGE5_VISIBILITY=PASS

LCD_HARDWARE_SPI=PASS
LCD_SPI_INTERFACE_INDEX=0
LCD_DATA_RATE=1MHz
LCD_UPDATE_INTERVAL=1s

NEW_FALSE_PASS_BLOCKER_COUNT=0
SOURCE_REPAIR_REQUIRED=false
R7_SOURCE_IMPLEMENTATION=PASS
PR702_SOURCE_MERGE_READY=true

T1_ACCESS=false
BOARD_ACCESS=false
LIVE_MUTATION=false
PHYSICAL_ACCEPTANCE=false
MERGE=false
```

`PR702_SOURCE_MERGE_READY=true` means source review/CI readiness only. It is not merge authorization.

## 19. Remaining physical boundary

R7 closure does not prove:
- LCD visual quality on the actual SMR12864/ST7920 module;
- final perceived text alignment;
- QR readability through the product enclosure;
- hardware SPI electrical margin at 1 MHz;
- real-user UX timing.

Those belong to later exact-artifact/physical acceptance stages.

## 20. Next executable gate

The frozen implementation order remains:

```text
R7  LCD state/error integration                CLOSED PASS
R8  full simulated end-to-end + regression/safety
R9  exact artifact build + independent artifact/source review
R10 separately authorized physical acceptance
```

Recommended next gate:

`N3W_SCAN_TRIGGERED_FIRST_PAIRING_R8_FULL_SIMULATED_E2E_SAFETY_SOURCE_DESIGN_AND_PREFLIGHT_20261028_01`

R8 must remain host/simulated unless a separately authorized physical gate is later opened.
