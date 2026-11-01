# N3W Scan-Triggered First Pairing R7 — LCD State/Error Integration Source Design and Preflight

Date: 2026-10-27

Gate:

`N3W_SCAN_TRIGGERED_FIRST_PAIRING_R7_LCD_STATE_ERROR_INTEGRATION_SOURCE_DESIGN_AND_PREFLIGHT_20261027_01`

## 1. Gate scope

This gate is source design / preflight only.

Allowed:
- fresh repository and PR rebind;
- exact-source read-only review;
- R7 display-state architecture;
- exact event/error mapping;
- test and CI planning;
- GitHub documentation.

Not allowed:
- product source mutation;
- T1 access or mutation;
- board access or flashing;
- live runtime mutation;
- sensitive Setup Secret transport;
- merge.

## 2. Fresh authority rebind

Repository:

`chrenguo-stack/HomeAssistant`

Current repository main remains exactly:

`2fbd0e9c2d3bf8a513ac318034e249511ffb6a2e`

Fresh compare:
- status: identical
- ahead: 0
- behind: 0

R6 source implementation PR #698:
- open
- draft
- unmerged
- exact source head:
  `6283cff57bcd0576968df9fd2440f3aae27331a5`

R6 source closure PR #699:
- docs-only
- head:
  `f6bfbb31916ea0a1bdcebe439a22ec349642f1aa`

R6 -> physical preflight PR #700:
- docs-only
- head:
  `73ca5895cb77a5ad9082b0968ae40a1323e7ef8e`

R7 product-source authority remains the exact R6 source head
`6283cff57bcd0576968df9fd2440f3aae27331a5`.

Documentation-only commits do not redefine the product-source authority.

## 3. Upstream frozen requirements

Primary authorities:
- `docs/adr/0011-n3w-scan-triggered-first-registration.md`
- `docs/development/N3W_SCAN_TRIGGERED_FIRST_PAIRING_SOURCE_DESIGN_20261026.md`
- R6 exact implementation / closure
- R6 -> physical validation preflight

ADR-0011 freezes LCD as the primary normal-product progress/failure surface.

The registration LCD state model is:

```text
IDLE_UNREGISTERED
DISCOVERING
WAIT_CONFIRM
REGISTERING
SUCCESS
ERROR
```

Initial user-facing error classes are:

```text
E01 = 未找到主机
E02 = 主机不可用
E03 = 主机忙
E04 = 网络中断
E05 = 注册超时
E06 = 注册失败
E07 = 二维码失效
```

Frozen display wording allows:

### Idle unregistered

```text
联机注册
<QR>
扫码注册
```

### Discovery

```text
联机注册
正在搜索
```

### Wait for phone choice/confirmation

```text
等待确认
请看手机
```

### Registering

```text
联机注册中
请稍候
```

### Success

```text
注册成功
```

### Errors

```text
E01 未找到主机
E02 主机不可用
E03 主机忙
E04 网络中断
E05 注册超时
E06 注册失败
E07 二维码失效
```

Exact 128×64 line placement may be tuned by render/glyph tests, but these semantics are frozen.

The old idle LCD behavior:

`正在查找主机`

is explicitly superseded.

The browser may still use a searching phrase while an actual user-triggered discovery is in progress. R7 only removes the obsolete **LCD idle** semantic; it does not rewrite browser copy merely because the same phrase appears there.

## 4. Exact R6 current-state review

R6 already provides the product facts R7 needs.

### 4.1 Registration portal stages

Current `RegistrationPortalStage`:

```text
IDLE
DISCOVERING
WAIT_CONFIRM
ERROR_NO_CANDIDATE
SELECTED_PENDING_BOOTSTRAP
```

Important current transitions:
- valid `/start` moves portal stage to `DISCOVERING` before the product loop consumes the trigger;
- successful discovery moves to `WAIT_CONFIRM`;
- no candidates moves to `ERROR_NO_CANDIDATE`;
- successful valid candidate confirmation moves to `SELECTED_PENDING_BOOTSTRAP`;
- retry re-arms `DISCOVERING`;
- portal reset returns to `IDLE`.

This is enough to derive IDLE / DISCOVERING / WAIT_CONFIRM / early REGISTERING without creating a second product transaction state machine.

### 4.2 R6 registration product facts

Current `SimpleProductComponent` already owns:
- `registration_candidate_selected_`;
- `registration_bootstrap_accepted_`;
- exact bootstrap result/deadline;
- `pairing_ack_pending_`;
- `pairing_client_.provisioned()`;
- portal lifecycle;
- discovery lifecycle;
- Wi-Fi state;
- bootstrap transport error;
- parsed confirm action/reason;
- simplified pairing result.

These facts remain the business authority.

R7 must not create another pairing/registration correctness state machine.

### 4.3 Current LCD gap

Current `display.yml` only has coarse booleans:
- `n3w_pairing_display_enabled`;
- `n3w_product_provisioned`;
- `n3w_pairing_display_ready`.

When Wi-Fi is connected and the node is unprovisioned:
- QR ready -> “扫码添加节点 / 等待添加”;
- QR not ready -> “正在查找主机”.

Therefore current R6 source does not implement the frozen six-state LCD contract or E01-E07 mapping.

## 5. R7 architecture decision

R7 uses a **display-only reducer/latch**, not a second registration state machine.

Recommended new narrow module:

```text
firmware/esphome_rc/components/greenhouse_n3w_core/
  n3w_registration_display.h
  n3w_registration_display.cpp
```

It contains:
- display state enum;
- display error enum;
- transient SUCCESS/ERROR latch;
- pure bounded timing behavior;
- no network;
- no NVS;
- no Setup Secret;
- no pairing protocol;
- no Manager/T1 logic.

### 5.1 Display state enum

```cpp
enum class RegistrationDisplayState : uint8_t {
  IDLE_UNREGISTERED = 0,
  DISCOVERING,
  WAIT_CONFIRM,
  REGISTERING,
  SUCCESS,
  ERROR,
};
```

### 5.2 Error enum

```cpp
enum class RegistrationDisplayError : uint8_t {
  NONE = 0,
  E01_NO_HOST = 1,
  E02_HOST_UNAVAILABLE = 2,
  E03_HOST_BUSY = 3,
  E04_NETWORK_INTERRUPTED = 4,
  E05_REGISTRATION_TIMEOUT = 5,
  E06_REGISTRATION_FAILED = 6,
  E07_QR_INVALID = 7,
};
```

Numeric 1..7 values intentionally match the user-visible E01..E07 identifiers.

No engineering root-cause string is exposed to LCD.

### 5.3 Display controller

The pure controller owns only transient display overrides.

Required operations:

```text
show_error(error, now_ms)
show_success(now_ms)
resolve(base_state, now_ms)
current_error(now_ms)
```

Frozen timings:

```text
REGISTRATION_ERROR_DISPLAY_MS = 5000
REGISTRATION_SUCCESS_DISPLAY_MS = 3000
```

Reason:
- errors may require two lines and must remain readable;
- success is a brief confirmation;
- neither timer is a transaction timer;
- neither timer pauses/restarts pairing;
- neither timer alters the canonical 1800-second Manager deadline.

Repeated reporting of the **same already-visible error** must not continuously extend the same latch. This prevents a retry loop from making one recoverable error permanent on LCD.

A new different error may replace the prior error and begin a new bounded display interval.

SUCCESS overrides any prior error only after durable local `provisioned()==true`.

## 6. One canonical display authority

`SimpleProductComponent` is the public display authority.

It should expose:

```cpp
RegistrationDisplayState registration_display_state() const;
RegistrationDisplayError registration_display_error() const;
```

The component derives a base state from existing facts and applies only the R7 transient controller.

It must not expose:
- Setup Secret;
- pairing ID;
- raw hardware ID;
- manager/system ID;
- bootstrap host;
- TLS fingerprint;
- 47112 session ID;
- delivery digest.

`pairing_handoff_ready` is explicitly forbidden as LCD success/state authority.

## 7. Base-state derivation

Outside an active SUCCESS/ERROR latch, derive the display state as follows.

### 7.1 REGISTERING has first business priority

Return `REGISTERING` when any of these is true:
- `pairing_ack_pending_`;
- `registration_candidate_selected_`;
- `registration_bootstrap_accepted_`;
- portal stage is `SELECTED_PENDING_BOOTSTRAP`.

This covers:
- post-confirm bootstrap;
- active 47112 transaction;
- pending final ACK;
- 47110 durable status recovery.

WAIT/UNKNOWN status recovery remains REGISTERING.

It must not be shown as success or failure.

### 7.2 Portal stage mapping

Otherwise:

```text
RegistrationPortalStage::DISCOVERING
  -> DISCOVERING

RegistrationPortalStage::WAIT_CONFIRM
  -> WAIT_CONFIRM

RegistrationPortalStage::IDLE
  -> IDLE_UNREGISTERED

RegistrationPortalStage::ERROR_NO_CANDIDATE
  -> IDLE_UNREGISTERED after the bounded E01 latch expires
```

`ERROR_NO_CANDIDATE` is a browser/discovery fact, not a permanent LCD ERROR state.

### 7.3 Provisioned outside brief success

A node that was already provisioned at boot does not show `SUCCESS`.

SUCCESS is only an event latch for a registration commit observed in the current boot/session.

After the 3000 ms success display expires, the existing page-5 “已联网” product display resumes.

## 8. Portal event boundary

R7 must not let arbitrary invalid LAN requests force an LCD error.

Specifically:
- an unauthenticated/wrong scan token that receives HTTP 403 must **not** directly trigger E07;
- otherwise any LAN client could create a visible error by sending bad tokens.

A narrow current-session event is sufficient.

Recommended addition to `RegistrationPortal`:

```text
candidate_stale_event_pending
take_candidate_stale_event()
```

It is raised only when:
- the request first passes current local/source/token checks;
- candidate confirmation then fails because the selected candidate/session is stale.

That event maps to E07.

Candidate expiration observed by current valid status polling may move the portal to `ERROR_NO_CANDIDATE`; it maps to the normal bounded E01 no-candidate behavior.

This preserves the source-design meaning of `LOCAL_QR_SESSION_STALE -> E07` without creating an LCD denial-of-service surface from invalid tokens.

## 9. Exact R7 error mapping

R7 maps current concrete R6 source signals to the frozen user error classes.

The user error is intentionally coarser than engineering diagnostics.

### 9.1 E01 — 未找到主机

Use E01 for a completed user-triggered discovery with no valid candidate.

```text
registration_discovery_.discover(...) == true
AND discovered.empty()
  -> E01
```

A real internal discovery construction/randomness failure where `discover()==false` is not “no host”; map that to E06.

Candidate expiry while the current browser is listing candidates may also enter the bounded E01 path unless a valid confirm action explicitly proves candidate/session stale, which is E07.

### 9.2 E02 — 主机不可用

Bootstrap transport:

```text
CONNECT_FAILED
TLS_FAILED
PIN_MISMATCH
  -> E02
```

`IO_FAILED`:
- if node Wi-Fi has been lost -> E04;
- if Wi-Fi remains connected -> E02.

Retryable/unavailable T1 confirm reasons map to E02, including current source reasons such as:

```text
bootstrap_unavailable
trusted_product_lan_unavailable
first_registration_transaction_not_implemented
registration_rate_limited
source_not_trusted_product_lan
```

These remain engineering-distinct in logs; LCD only says the host is unavailable.

A TLS pin mismatch must remain fail-closed exactly as R6 defines. Showing E02 does not weaken trust or trigger fallback to another T1.

### 9.3 E03 — 主机忙

Exact confirm result:

```text
action = RETRY
reason = registration_busy
  -> E03
```

A discovery candidate carrying `busy=true` does not automatically become an LCD error merely by being listed.

The user may still explicitly select it; the authoritative confirm result decides E03.

### 9.4 E04 — 网络中断

Use E04 for network interruption after the user has entered the registration transaction path.

At minimum:

```text
Wi-Fi lost while:
  registration_candidate_selected_
  OR registration_bootstrap_accepted_
  OR pairing_ack_pending_
  -> E04
```

And:

```text
SimplePairingClientError::HTTP_FAILED
during the existing accepted transaction
  -> bounded E04
```

E04 is display-only. Automatic retry inside the same transaction may continue.

E04 must not:
- renew pairing ID;
- create a new 1800-second transaction;
- close 47112;
- reset the Manager deadline.

Wi-Fi loss while merely idle/waiting for scan is not E04. Existing Wi-Fi provisioning/reconnect UI remains responsible there.

### 9.5 E05 — 注册超时

When the local safe monotonic deadline derived from the Manager response is reached:

```text
now >= registration_bootstrap_result_.transaction_deadline_ms
  -> E05
```

R7 does not change R6's authority rule:
- local timeout cannot mint a new pairing ID;
- node must later obtain authoritative 47110 terminal classification;
- old transaction identity is preserved until T1 proves terminal state.

Therefore E05 is user feedback, not transaction renewal authority.

### 9.6 E06 — 注册失败

Use E06 for non-retryable/local/protocol correctness failures, including:

Bootstrap:
```text
INVALID_ARGUMENT
RESPONSE_TOO_LARGE
PROTOCOL_FAILED
```

Confirm response:
```text
manager_mismatch
system_mismatch
identity_invalid
request_invalid
path_not_found
other syntactically valid but non-terminal/non-busy rejection
```

Pairing client:
```text
IO_FAILED
RESPONSE_REJECTED
CRYPTO_FAILED
PERSISTENCE_FAILED
```

Local registration portal creation failure may also show E06 while the component continues its existing bounded portal retry.

R7 must not convert E06 into whole-NVS reset or silent provisioning success.

### 9.7 E07 — 二维码失效

E07 covers a user-facing registration identity/session that is no longer valid.

Use E07 for:

```text
valid current scan session + candidate stale on confirm
terminal confirm reason = expired
terminal confirm reason = replay_detected
SimplePairingClientError::TRANSACTION_RENEWED
terminal ACK recovery cleanup successfully completed
```

For terminal confirm:
- first call the existing durable pairing-ID renewal primitive;
- only if renewal succeeds may E07 represent that the previous QR/session is obsolete;
- if durable renewal itself fails, show E06 and remain fail-closed.

R7 does not invent a new renewal mechanism.

## 10. Pending-ACK / restart display semantics

R6 already gives ACK_PENDING priority over ordinary registration.

R7 preserves it.

At boot with a valid pending ACK:
- do not show idle registration QR as normal state;
- show REGISTERING;
- run the existing bounded direct-ACK / 47110 status recovery.

Status result:
- COMMITTED -> local provisioned -> SUCCESS for 3000 ms;
- WAIT -> REGISTERING;
- UNKNOWN/wait -> REGISTERING;
- transport unavailable -> remain REGISTERING, optionally bounded E04 if a concrete network-unreachable event is known;
- terminal -> durable TERMINAL_CLEANUP -> fresh pairing ID -> E07;
- cleanup/persistence failure -> E06.

WAIT/UNKNOWN must never map to SUCCESS or E07.

## 11. SUCCESS authority

R7 must have one exact success trigger:

```text
pairing_client_.provisioned() == true
after current registration commit/recovery path
```

SUCCESS may be latched only in the two existing commit closures:
- direct R6 selected-candidate pairing path;
- pending-ACK recovery path.

R7 must not trigger SUCCESS from:
- browser confirm accepted;
- 47110 accepted;
- credential bundle decrypted;
- peer/Broker bundle persisted;
- final ACK HTTP 200 without exact committed payload;
- `pairing_handoff_ready`;
- MQTT connection alone.

This preserves the R6 false-PASS closure.

The 3000 ms success display must not delay:
- local runtime-state loading;
- MQTT configuration;
- normal runtime startup.

It is presentation-only.

## 12. LCD page priority

Keep low-battery behavior highest priority.

Recommended page-5 priority:

```text
1. LOW_BATTERY overlay
2. bounded registration SUCCESS / ERROR latch
3. Wi-Fi not connected -> existing Wi-Fi provisioning/reconnect QR
4. Wi-Fi connected + unprovisioned -> R7 registration state rendering
5. provisioned -> existing “已联网” screen
```

Why SUCCESS/ERROR precedes ordinary Wi-Fi rendering:
- E04 must remain visible briefly when an active registration loses Wi-Fi;
- a just-proven Manager COMMIT may still show “注册成功” briefly even if transport state changes immediately afterward.

After the bounded latch expires, ordinary Wi-Fi/provisioned rendering resumes.

Low-battery overlay does not mutate or reset registration display state. When it clears, the then-current state is rendered.

## 13. YAML integration

`n3w_product_transport.yml` remains a presentation bridge, not a business authority.

It should mirror from `n3w_product_core`:
- provisioned boolean;
- registration display state code;
- registration display error code;
- current registration QR payload/readiness.

Recommended globals:

```text
n3w_registration_display_state
n3w_registration_display_error
n3w_registration_qr_ready
n3w_product_provisioned
```

Existing ambiguous `n3w_pairing_display_ready` may be retired or retained only as an internal compatibility alias during the same source change, but the final R7 display branch must consume the explicit registration state/error authority.

No YAML logic may infer SUCCESS from provisioned transition timing on its own.

## 14. LCD rendering

Page 5 must render the frozen semantics.

Suggested layout:

### IDLE_UNREGISTERED
- current registration QR;
- “联机注册”;
- “扫码注册”.

### DISCOVERING
- “联机注册”;
- “正在搜索”.

### WAIT_CONFIRM
- “等待确认”;
- “请看手机”.

This is used for both one-candidate confirmation and multi-candidate user selection.

### REGISTERING
- “联机注册中”;
- “请稍候”.

### SUCCESS
- “注册成功”.

### ERROR
- first line: `E01` .. `E07`;
- second line: corresponding Chinese description.

The final layout must fit the current rotated logical 64×128 canvas and preserve the existing top status bar / bottom page/time area unless a render test proves a small registration-page-only adjustment is necessary.

## 15. Font/glyph contract

Current BDF glyph allowlists were written before the complete R7 vocabulary.

R7 implementation must explicitly add every Chinese glyph actually rendered by the new strings to the exact font used for that string.

A test must fail if any rendered R7 character is absent.

Do not rely on:
- “the font file probably contains the glyph”;
- fallback behavior;
- another font's glyph list.

The source contract must bind exact rendered string -> exact configured font -> required glyph set.

## 15.1 LCD SPI hardware-interface requirement

R7 must make the LCD SPI bus selection explicit.

Current R6 source declares:

```yaml
spi:
  id: bus_spi
  clk_pin: GPIO2
  mosi_pin: GPIO3
```

With no `interface` key, ESPHome uses its default `any` policy. That policy normally selects an available hardware SPI controller first, but it also permits software fallback when hardware allocation is unavailable.

For the LCD12864/ST7920 product path, silent software-SPI fallback is not acceptable.

R7 implementation must change the bus to:

```yaml
spi:
  id: bus_spi
  clk_pin: GPIO2
  mosi_pin: GPIO3
  interface: hardware
```

Rationale:
- LCD transfer is a display workload, not a low-rate sensor workload;
- hardware SPI reduces CPU bit-banging work when compared with software SPI;
- explicit `hardware` makes the resource contract fail closed instead of silently degrading to software SPI;
- current ST7920 `data_rate: 1MHz` remains unchanged unless later physical signal-integrity testing justifies a separate change.

Important qualification:
- this setting does not prove that the previous `interface: any` build was using software SPI;
- with an available hardware controller, `any` may already resolve to hardware;
- therefore the source claim is `HARDWARE_SPI_REQUIRED_AND_NO_SOFTWARE_FALLBACK`, not an unproven claim that R7 necessarily reduces CPU use relative to the exact R6 binary.

R7 CI must prove from ESPHome validation/build output or generated configuration that the product LCD bus is accepted as a hardware SPI bus on ESP32-C6. A configuration that falls back to software SPI is a failure.

This SPI selection affects only the transport implementation used to push the framebuffer to ST7920. It does not change:
- `update_interval`;
- LCD state semantics;
- the R7 display latch;
- the registration transaction;
- the 1800-second deadline.

## 16. Display timing is not protocol timing

R7 introduces no transaction deadline.

Frozen separation:

```text
ERROR LCD hold     = 5 seconds
SUCCESS LCD hold   = 3 seconds
discovery budget   = existing R5 bounded discovery
candidate TTL      = existing 30 seconds
pairing transaction= Manager-owned 1800 seconds
```

The 3/5-second UI timers must never:
- refresh the 1800-second deadline;
- create a pairing ID;
- close pairing;
- delete pending state;
- control Manager/T1 services.

## 17. No forced display dwell before network work

R7 does **not** add an artificial one-second delay before discovery/bootstrap merely to guarantee a transient frame is physically visible.

Reason:
- that would change transaction latency for presentation reasons;
- portal stages are already set from the HTTP request path before product-loop consumption;
- state correctness is more important than forcing a minimum visible dwell.

R8/R10 may observe that a very fast transition is not human-visible. If physical UX shows that a minimum dwell is needed, that is a later measured UI tuning decision, not part of R7 correctness authority.

## 18. Browser boundary

R7 is LCD-focused.

Do not expand this gate into browser/T1 protocol redesign.

Browser may continue to:
- show candidates;
- send current scan-session actions;
- display its existing searching/accepted text.

R7 may add only the narrow stale-current-session event needed for E07.

Full browser end-to-end result behavior belongs to R8 simulated E2E closure.

## 19. Expected source mutation set for implementation

Allowed primary R7 source files:

```text
firmware/esphome_rc/components/greenhouse_n3w_core/
  n3w_registration_display.h               NEW
  n3w_registration_display.cpp             NEW
  n3w_registration_portal.h
  n3w_registration_portal.cpp
  n3w_simple_product_component.h
  n3w_simple_product_component.cpp

firmware/esphome_rc/f1_0_rc2/packages/
  n3w_product_transport.yml
  display.yml

tests/n3w_registration/
  test_scan_triggered_first_pairing_r7_lcd_state_contract.py    NEW
  n3w_registration_display_host_test.cpp                        NEW or equivalent

.github/workflows/
  greenhouse-manager-ci.yml
```

Changes outside this list require explicit source-review justification.

Not expected:
- Manager/T1 runtime source;
- registration ledger;
- dynamic pairing window;
- pairing crypto;
- NVS schema;
- Broker/DynSec;
- Home Assistant;
- deployment/firstboot.

## 20. Implementation invariants

R7 implementation must preserve all of the following:

```text
IDLE_UNREGISTERED_AUTO_DISCOVERY=false
SETUP_SECRET_PHONE_EXPOSURE=false
SETUP_SECRET_LCD_EXPOSURE=false
PAIRING_ID_LCD_EXPOSURE=false
TLS_FINGERPRINT_LCD_EXPOSURE=false

R6_TLS_PINNING_UNCHANGED=true
R6_CONFIRM_CONTRACT_UNCHANGED=true
R6_47112_PAIRING_CRYPTO_UNCHANGED=true
R6_FINAL_ACK_SUCCESS_AUTHORITY_UNCHANGED=true
R6_PENDING_ACK_RECOVERY_UNCHANGED=true
R6_TERMINAL_CLEANUP_UNCHANGED=true

DISPLAY_ERROR_DOES_NOT_MUTATE_PAIRING_STATE=true
DISPLAY_TIMER_DOES_NOT_MUTATE_TRANSACTION_DEADLINE=true
SUCCESS_REQUIRES_PROVISIONED=true
PAIRING_HANDOFF_READY_IS_NOT_DISPLAY_AUTHORITY=true
```

## 21. R7 tests

### 21.1 Pure host display-controller test

Compile and run a small C++ host test that proves:
- base state is returned with no active latch;
- E01..E07 encode exactly 1..7;
- ERROR remains active for exactly the bounded error interval;
- SUCCESS remains active for exactly the bounded success interval;
- same-error repeated notification does not extend the existing latch indefinitely;
- new different error may replace the previous error;
- SUCCESS overrides an error only when explicitly invoked by commit integration;
- no networking/ESP-IDF dependency exists in the display controller.

### 21.2 Source integration test

New:

`tests/n3w_registration/test_scan_triggered_first_pairing_r7_lcd_state_contract.py`

It must directly inspect source and prove:
- six states exist;
- seven error classes exist;
- public component getters exist;
- no `pairing_handoff_ready` use in display authority;
- portal `DISCOVERING` -> LCD DISCOVERING;
- portal `WAIT_CONFIRM` -> LCD WAIT_CONFIRM;
- selected/bootstrap/pending ACK -> REGISTERING;
- discovery empty -> E01;
- transport unavailable/pin mismatch mapping -> E02;
- `registration_busy` -> E03;
- active-transaction Wi-Fi/HTTP failure -> E04;
- transaction deadline -> E05;
- protocol/crypto/persistence failure -> E06;
- terminal renewal/current-session stale candidate -> E07;
- WAIT/UNKNOWN pending ACK does not become SUCCESS;
- success latch call is dominated by `pairing_client_.provisioned()`;
- error display helpers never call renewal/erase/NVS reset.

### 21.3 LCD/YAML golden contract

Prove `display.yml` contains all required product strings:

```text
联机注册
扫码注册
正在搜索
等待确认
请看手机
联机注册中
请稍候
注册成功
未找到主机
主机不可用
主机忙
网络中断
注册超时
注册失败
二维码失效
```

Prove the idle LCD branch no longer contains:

`正在查找主机`

Do not reject that phrase if it remains in the **browser** source for actual discovery progress.

### 21.4 Glyph coverage

Parse the configured BDF/glyph allowlist and prove every character rendered by each R7 line is available from the exact selected font.

### 21.5 Layout bounds

Use exact configured font metrics or a deterministic equivalent to prove:
- no R7 line exceeds the logical 64-pixel registration-page width;
- registration content stays clear of the existing top status bar and bottom page/time area;
- QR render remains bounded to the current registration-page region.

### 21.6 Regression contracts

Re-run R4/R5/R6 source contracts unchanged.

Prove:
- no idle discovery regression;
- browser remains secret-free;
- R5 explicit multi-T1 selection unchanged;
- R6 TLS pin before Setup Secret transmission unchanged;
- R6 final ACK strict proof unchanged;
- R6 pending-ACK/terminal cleanup unchanged.

### 21.7 Production compile

Compile the production ESP32-C6 F1.0-RC2 N3-W target.

The R7 CI step must be added after R6 focused source contracts in `greenhouse-manager-ci.yml`.

Existing firmware workflows must remain green.

## 22. Source-review focus after implementation

Independent review must not accept CI alone.

Re-read exact implementation and verify:
1. one display authority, no duplicate business state machine;
2. success cannot be reached before R6 committed/provisioned proof;
3. display error timers cannot mutate transaction state;
4. pending ACK WAIT/UNKNOWN cannot become success/error cleanup;
5. E07 cannot be triggered by arbitrary wrong-token LAN requests;
6. terminal renewal remains durable-before-RAM exactly as R6;
7. old idle “正在查找主机” is gone only from LCD idle behavior;
8. QR remains secret-free;
9. all R7 strings have exact glyph coverage;
10. no new false-PASS path.

## 23. Preflight result

```text
GATE=N3W_SCAN_TRIGGERED_FIRST_PAIRING_R7_LCD_STATE_ERROR_INTEGRATION_SOURCE_DESIGN_AND_PREFLIGHT_20261027_01

BASE_PRODUCT_SOURCE=6283cff57bcd0576968df9fd2440f3aae27331a5
MAIN_DRIFT=false

R7_ARCHITECTURE=DISPLAY_ONLY_REDUCER_PLUS_BOUNDED_LATCH
SECOND_PAIRING_STATE_MACHINE=false

LCD_STATE_MODEL_FROZEN=true
LCD_ERROR_MAPPING_FROZEN=true
SUCCESS_AUTHORITY=PAIRING_CLIENT_PROVISIONED_AFTER_MANAGER_COMMIT
SUCCESS_DISPLAY_MS=3000
ERROR_DISPLAY_MS=5000

T1_SOURCE_CHANGE_REQUIRED=false
MANAGER_SOURCE_CHANGE_REQUIRED=false
NVS_SCHEMA_CHANGE_REQUIRED=false
PAIRING_PROTOCOL_CHANGE_REQUIRED=false

PRODUCT_SOURCE_MUTATION=false
T1_ACCESS=false
BOARD_ACCESS=false
LIVE_MUTATION=false
MERGE=false

R7_SOURCE_IMPLEMENTATION_ELIGIBLE=true
PREFLIGHT_RESULT=PASS_READY_FOR_SOURCE_IMPLEMENTATION
```

## 24. Next executable gate

`N3W_SCAN_TRIGGERED_FIRST_PAIRING_R7_LCD_STATE_ERROR_INTEGRATION_SOURCE_IMPLEMENTATION_20261027_01`

Implementation must stay within the allowed mutation set above unless a newly proven source blocker requires a separately documented design delta.

No physical work is authorized by this R7 preflight.
