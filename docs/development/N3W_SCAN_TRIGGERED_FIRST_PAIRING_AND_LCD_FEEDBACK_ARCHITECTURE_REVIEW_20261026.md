# N3-W Scan-Triggered First Pairing and LCD Feedback Architecture Review — 2026-10-26

## 1. Review identity

```text
TASK=N3W_SCAN_TRIGGERED_FIRST_PAIRING_AND_LCD_FEEDBACK_ARCHITECTURE_REVIEW_20261026_01
BASE_MAIN=507dbd49495c558b1344f7d713938b733b3bad18
MODE=ARCHITECTURE_REVIEW_DOCS_ONLY

PRODUCT_SOURCE_MUTATION=false
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
BOARD_MUTATION=false
PAIRING_EXECUTION=false
MERGE=false
```

## 2. Product north star

The normal user must not need Linux, Docker, MQTT, SSH, CLI, IP addresses, ports, Home Assistant backend configuration, or manual secret/code copying.

The intended normal user surfaces are:

```text
NODE_LCD
+
PHONE_SYSTEM_CAMERA
+
MINIMAL_LOCAL_BROWSER_PAGE
```

No dedicated mobile app is required for the first product flow.

The phone is not a long-lived management console. Its first-pair role is intentionally narrow:

```text
SCAN
-> SEE THE DISCOVERED LOCAL T1 / DEVICE MATCH
-> CONFIRM
```

All cryptographic and lifecycle work remains automatic and hidden from the user.

## 3. User-facing terminology

Use **“联机注册”** as the product-facing term for bringing an unregistered node into one greenhouse system.

Engineering/internal terms remain unchanged where useful:

- pairing / pairing_id / Setup Secret: protocol and security lifecycle;
- registration: Manager durable registration;
- provisioning: credential/material delivery.

This avoids rewriting stable protocol names only to change UI copy.

```text
PRODUCT_UI_TERM=联机注册
ENGINEERING_PAIRING_TERM_RETAINED=true
PROTOCOL_SCHEMA_RENAME_REQUIRED=false
```

Exact final Chinese copy can still receive a later LCD/UI wording pass, but architecture and state names should stop using “添加设备” as the primary product concept.

## 4. Authority conflict found

The long-term V0.7 route still contains an older LCD rule:

```text
Wi-Fi 已连，未发现主机
-> 正在查找主机
```

That rule conflicts with the now-frozen product direction that Wi-Fi provisioning completion should expose a user-operable registration QR independent of T1 presence.

V0.7 also states that:
- the user should only need power, Wi-Fi provisioning and one explicit node confirmation;
- an unpaired node generates one-time pairing material locally;
- pairing material belongs to the node's unpaired lifecycle.

ADR-0008 later simplified pairing further:
- each fresh pairing transaction uses a device-generated random pairing_id;
- pending intent can survive reboot;
- retries terminate/expire the old transaction and generate a fresh random pairing ID;
- terminal pairing IDs remain replay tombstones.

Therefore the V0.7 “正在查找主机” LCD row is now stale and requires a successor architecture decision rather than silent reinterpretation.

```text
V0_7_LCD_SEARCHING_HOST_ROW=STALE
SUCCESSOR_ADR_REQUIRED=true
```

## 5. Current implementation mismatch

Current Board product source prepares pairing material before Manager discovery:

`SimplePairingClient::prepare_bootstrap_()`:
- loads/creates Setup Secret;
- loads or creates durable random pairing_id.

`pairing_qr_payload()` can therefore be formed while the node is unprovisioned and Wi-Fi-connected.

However the display path currently requires:

```text
Wi-Fi connected
AND not provisioned
AND pairing_handoff_ready == true
```

and `pairing_handoff_ready` becomes true only after:
- Manager discovery succeeds;
- `/hello` succeeds;
- Manager returns a proceed disposition.

This creates the wrong dependency:

```text
T1 pairing exposure
-> Manager discovery
-> /hello PROCEED
-> QR becomes visible
```

The product target is the reverse:

```text
Wi-Fi provisioned + unregistered
-> registration QR visible
-> user scan triggers discovery
-> user confirm triggers bounded pairing transaction
```

## 6. Frozen idle behavior

After Wi-Fi provisioning succeeds:

1. the Wi-Fi provisioning QR is removed immediately;
2. the LCD shows the **联机注册 QR**;
3. the node does **not** actively search for T1;
4. no pairing window is open;
5. no pairing transaction TTL is running;
6. no Manager registration is created merely because the QR is visible;
7. local sensor acquisition/LCD pages remain independent.

```text
PAIRING_QR_AFTER_WIFI=VISIBLE_WHILE_UNREGISTERED
IDLE_T1_DISCOVERY=false
IDLE_PAIRING_WINDOW=false
IDLE_PAIRING_TRANSACTION=false
IDLE_TRANSACTION_TIMER=false
```

The idle QR may persist across reboot using the current durable pairing intent semantics. QR visibility is not itself evidence that a pairing attempt started.

## 7. QR format and app-less entry

The production QR must be directly actionable by a normal phone camera.

A raw value such as:

```text
GHN3W2:<hardware_id>:<pairing_id>:<setup_secret>
```

may remain an internal protocol representation, but must not be the final user-facing scan result.

The production QR should resolve to a **node-local registration page**. Exact URL/hostname/port format is a later source-design decision, but the architecture requires:

- standard phone camera can open it;
- no dedicated app;
- no manual code copy;
- raw Setup Secret is not shown to the user;
- raw Setup Secret is not placed in browser-visible query strings, history, logs or public evidence;
- the node is reachable only on the local network in the normal flow;
- the page exists only for an unregistered node.

An opaque high-entropy scan token may be used to bind the browser visit to the physical QR without exposing Setup Secret.

## 8. Scan-triggered discovery

The first successful HTTP request generated by scanning the current registration QR is the user-action trigger.

Only then may the node start an active T1 discovery attempt.

```text
QR_SCAN_REQUEST_REACHES_NODE
-> SCAN_SESSION_ACTIVE
-> ACTIVE_T1_DISCOVERY
```

Discovery remains location-only and does not create trust or registration.

Recommended discovery behavior:

1. mDNS/DNS-SD browse first;
2. bounded local UDP fallback if needed;
3. stop the active discovery attempt after a bounded short search;
4. do not continue indefinite background discovery after the scan session ends.

T1 may remain **passively discoverable** all the time through a low-risk advertisement/responder. That is not the same as the node continuously searching.

The T1 discovery surface must be separated from privileged pairing exposure:

```text
T1_PASSIVE_DISCOVERABILITY=ALLOWED_ALWAYS
T1_PAIRING_EXPOSURE=DEFAULT_CLOSED
NODE_ACTIVE_DISCOVERY=SCAN_TRIGGERED_ONLY
```

This separation is required because otherwise an idle-closed pairing window creates a circular dependency: the node cannot discover T1 until a window is open, but the window must not open until the user confirms a discovered T1.

## 9. Discovery outcomes

### 9.1 No T1 found

If the scan request reached the node but the bounded discovery attempt finds no T1:

```text
PAIRING_TRANSACTION_CREATED=false
PAIRING_WINDOW_OPEN=false
PAIRING_ID_RENEWED=false
```

LCD is the primary product feedback surface.

Initial category:

```text
E01 = 未找到主机
```

After the error indication, the node returns to the same 联机注册 QR so the user can retry later.

### 9.2 T1 discovered but unavailable

If discovery finds a candidate but the required local registration service cannot be reached or is unhealthy:

```text
E02 = 主机不可用
```

No durable first-pair transaction should be created.

### 9.3 Multiple T1 candidates

Multiple T1s are not an error that should be auto-resolved by RSSI, response time or identifier ordering.

The phone page may present the local candidates and let the user select one.

LCD may show a compact “请在手机选择” state; exact wording/code remains a UI detail.

### 9.4 Exactly one healthy T1

The browser shows only simple human-readable confirmation information sufficient to avoid choosing the wrong local system, for example:

```text
节点：<friendly node identifier>
主机：<friendly greenhouse/system identifier>

[确认联机注册]
```

No certificate fingerprint, key comparison, IP address, MQTT field or technical security prompt is shown to the normal user.

## 10. User confirmation boundary

Scanning does **not** start the 30-minute pairing transaction.

Discovery does **not** start the 30-minute pairing transaction.

The transaction begins only after the user presses the final confirmation control for the selected local T1.

```text
SCAN
-> DISCOVER
-> SHOW MATCH
-> USER CONFIRM
-> START REGISTRATION TRANSACTION
```

This prevents:
- idle QR exposure from consuming a transaction;
- a missing T1 from consuming a transaction;
- a slow human scan from exhausting the transaction;
- background network activity from silently creating pairing state.

## 11. Transaction timing

The normal first-registration transaction maximum lifetime is widened to:

```text
FIRST_REGISTRATION_TRANSACTION_TTL_SECONDS=1800
```

Thirty minutes is a maximum safety bound, not a required open duration.

The transaction ends early on:
- successful commit;
- explicit unrecoverable failure;
- user cancellation if supported;
- terminal protocol rejection.

Success or terminal failure must immediately close privileged pairing exposure.

The idle registration QR itself is not tied to this 30-minute TTL.

## 12. Identity binding and security UX

The user experience is deliberately simple because:
- the user is physically looking at the node;
- the user intentionally scanned that node's QR;
- the action occurs on the user's local network;
- the user explicitly confirms the discovered T1.

Therefore no complex human security ceremony is required.

However backend security remains automatic and non-optional:
- random pairing_id;
- one-time Setup Secret / PoP;
- exact hardware/pairing binding;
- replay tombstone;
- bounded transaction;
- encrypted/authenticated credential delivery or an equivalently reviewed secure handoff;
- per-node credentials and trust state.

```text
COMPLEX_USER_SECURITY_PROMPTS=false
MACHINE_SECURITY_RETAINED=true
```

The current manual:
`scan -> copy GHN3W2 text -> paste into Terminal`
path is engineering-only evidence handling and is not acceptable as the product flow.

## 13. No-app Setup Secret handoff requirement

The current Manager design expects Setup Secret to arrive through a local private Manager interface, while current tests manually bridge the QR to that interface.

The productized no-app flow must replace this manual bridge.

Architecture requirements:

```text
MANUAL_SETUP_SECRET_COPY=false
CLI_SETUP_SECRET_HANDOFF=false
RAW_SETUP_SECRET_VISIBLE_TO_USER=false
RAW_SETUP_SECRET_IN_URL=false
RAW_SETUP_SECRET_IN_BROWSER_HISTORY=false
```

Phone browser and/or node software may mediate the handoff automatically, but the exact transport mechanism requires a dedicated protocol/source design review.

That design must preserve the existing security goals without requiring a dedicated app or technical user verification.

This is a real implementation blocker and must not be hand-waved away.

## 14. LCD as primary progress/failure surface

The LCD is the primary normal-product status surface after scan.

Recommended user-level state categories:

```text
IDLE_UNREGISTERED = 联机注册 + QR
DISCOVERING       = 联机注册进行中 / compact progress state
WAIT_CONFIRM      = 等待确认
REGISTERING       = 注册中
SUCCESS           = 注册成功
ERROR             = short text + E-code
```

Exact wording/layout is a later 128x64 UI review.

Initial failure-code classes:

```text
E01 = 未找到主机
E02 = 主机不可用
E03 = 注册网络中断
E04 = 注册超时
E05 = 注册失败
E06 = 当前二维码失效
```

Internal diagnostics may remain much more detailed. LCD codes are intentionally coarse and user-oriented.

On a recoverable pre-transaction error, keep the same QR.

On a terminal pairing transaction failure/expiry:
- preserve the old pairing ID as replay tombstone;
- generate a fresh random pairing ID according to ADR-0008;
- show a newly generated registration QR.

## 15. Unavoidable phone-only failure boundary

LCD can report a scan-triggered failure only after the scan request actually reaches the node.

If the phone is not on the same reachable local network and cannot open the node-local QR URL at all, the node has no event proving that a scan occurred.

Therefore:

```text
PHONE_CANNOT_REACH_NODE
-> NODE_CANNOT_KNOW_SCAN_OCCURRED
-> BROWSER_CONNECTION_FAILURE_IS_UNAVOIDABLE_FIRST_FEEDBACK
```

The product should minimize this case through clear provisioning flow and local URL design, but architecture must not pretend the LCD can diagnose an event the node never received.

Once the browser reaches the node, subsequent T1 discovery/registration failures should preferentially surface on LCD.

## 16. Retirement scope

Node retirement remains a reserved lifecycle concept, but is not part of the current product-development priority.

```text
NODE_RETIREMENT_ARCHITECTURE=RESERVED
NEW_NODE_RETIREMENT_DEVELOPMENT=DEFERRED
NODE_RETIREMENT_UI_CURRENT_SCOPE=false
C07_EXISTING_SOURCE_REOPEN=false
```

Existing retirement code/evidence is not deleted or regressed. The current first-registration redesign must not spend scope on new retirement features.

## 17. Required source-design changes

A later source-design gate must at minimum address:

1. decouple QR visibility from `pairing_handoff_ready`;
2. remove idle automatic T1 discovery from unregistered product behavior;
3. replace the “正在查找主机” idle LCD state;
4. expose a minimal node-local registration page reachable by standard phone camera QR;
5. trigger active discovery only from the scan request;
6. split always-safe T1 discoverability from privileged pairing exposure;
7. provide multi-T1 selection without automatic choice;
8. trigger the exact identity-bound T1 transaction only after user confirmation;
9. raise first-registration transaction TTL to 1800 seconds;
10. automate Setup Secret handoff without app/CLI/manual copy;
11. define LCD progress/error state machine and regression coverage;
12. preserve ADR-0008 replay/renewal semantics;
13. leave retirement development out of scope.

## 18. Current classification

```text
ARCHITECTURE_REVIEW_RESULT=CLOSED_WITH_SOURCE_DESIGN_REQUIRED

PRODUCT_UI_TERM=联机注册

PAIRING_QR_AFTER_WIFI=ALWAYS_AVAILABLE_WHILE_UNREGISTERED
IDLE_T1_DISCOVERY=false
QR_SCAN_STARTS_T1_DISCOVERY=true
USER_CONFIRM_STARTS_PAIRING_TRANSACTION=true
FIRST_REGISTRATION_TRANSACTION_TTL_SECONDS=1800

DEDICATED_APP_REQUIRED=false
PHONE_ROLE=SCAN_AND_MINIMAL_BROWSER_CONFIRM
PRIMARY_PROGRESS_FEEDBACK=LCD
PRIMARY_FAILURE_FEEDBACK=LCD_ERROR_CODE

MANUAL_SECRET_COPY=false
NORMAL_USER_CLI_ACCESS=false
NORMAL_USER_BACKEND_ACCESS=false

NODE_RETIREMENT_NEW_DEVELOPMENT=DEFERRED

CURRENT_PAIRING_HANDOFF_READY_DISPLAY_GATE=PRODUCT_MISMATCH
CURRENT_RAW_QR_COPY_PASTE_FLOW=ENGINEERING_ONLY
V0_7_LCD_SEARCHING_HOST_ROW=STALE
SUCCESSOR_ADR_REQUIRED=true

PRODUCT_SOURCE_MUTATION=false
LIVE_MUTATION=false
MERGE=false
```

## 19. Proposed next gate

```text
N3W_SCAN_TRIGGERED_FIRST_PAIRING_SOURCE_DESIGN_20261026_01
```

That gate should produce the exact protocol and component design before any product code is changed, with special attention to the app-less Setup Secret handoff and the separation between passive T1 discoverability and privileged pairing exposure.
