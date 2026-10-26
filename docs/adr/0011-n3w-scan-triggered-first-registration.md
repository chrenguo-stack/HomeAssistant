# ADR-0011: N3-W scan-triggered first registration and LCD-first user feedback

- Status: accepted for source design
- Date: 2026-10-26
- Scope: unregistered N3-W node first registration, scan-triggered Manager discovery, app-less confirmation, bounded pairing exposure, LCD feedback
- Supersedes:
  - the V0.7 LCD rule that maps `Wi-Fi connected + Manager not found` to an idle “正在查找主机” state;
  - ADR-0007 §3.2 only where it requires the Setup Secret itself to be carried by the user-facing LCD QR;
  - ADR-0008 “Product Setup Secret interface” only for the normal first-registration product path that previously depended on local UDS/CLI/UI secret import.
- Retains:
  - ADR-0007 device-generated one-time Setup Secret, HMAC/HKDF bootstrap and encrypted credential delivery;
  - ADR-0008 random pairing transaction, terminal renewal and replay-tombstone semantics;
  - ADR-0008 local UDS as an engineering/ops interface rather than normal-user first-registration UX.

## Decision

The product-facing action is named **联机注册**.

After Wi-Fi provisioning succeeds, an unregistered node immediately exposes a registration QR on LCD. The node does not actively discover T1 while idle.

```text
WIFI_UNPROVISIONED
-> Wi-Fi provisioning QR

WIFI_CONNECTED + UNREGISTERED
-> 联机注册 QR
-> no active T1 discovery
-> no pairing window
-> no registration transaction timer
```

A standard phone camera opens a node-local browser page. No dedicated app is required.

The first valid scan-session request received by the node is the trigger for one bounded T1 discovery operation.

```text
PHONE_SCAN
-> NODE_LOCAL_PAGE
-> VALID_SCAN_SESSION
-> ACTIVE_T1_DISCOVERY
```

If no T1 is found, no first-registration transaction is created and the node returns to the same registration QR after an LCD error indication.

If one or more T1 candidates are found, the phone page shows only simple human-facing match information. The user explicitly chooses/accepts a candidate and presses **确认联机注册**.

In the normal product UI path, that confirmation asks the node to start the privileged first-registration transaction.

```text
SCAN
-> DISCOVER
-> SHOW MATCH
-> USER CONFIRM
-> START FIRST-REGISTRATION TRANSACTION
```

The T1 authorization boundary is intentionally broader than the QR/browser UX boundary: any client already on the trusted LAN is authorized to initiate first registration through 47110. QR possession, the scan token and browser confirmation are not cryptographic T1 authorization credentials. A trusted-LAN client may therefore invoke the bootstrap endpoint directly; that capability is an explicit accepted property of the product threat model.

The first-registration transaction maximum lifetime is 1800 seconds. During normal Manager uptime, privileged pairing exposure has exactly two semantic close conditions: successful Manager COMMIT or expiry of the canonical transaction deadline. Browser exit, explicit user cancellation, protocol error, pairing failure or other pre-deadline error does not by itself close 47112 or renew the pairing identity. Manager/process restart is a separate fail-closed process-boundary invalidation defined below, not a third normal transaction close condition.

The 1800-second bound is **per node transaction**, not a global T1 pairing mode. V1 permits only one active first-registration transaction at a time.

Example:
- node A is confirmed and receives its own deadline `A_confirm + 1800s`;
- if A commits after 80 seconds, A's remaining ~1720 seconds are discarded immediately and privileged pairing exposure closes;
- node B then requires a new scan/confirmation and receives a fresh `B_confirm + 1800s` deadline;
- no time budget is inherited or shared across A/B/C.

If B requests confirmation while A is still active, T1 returns a busy result; B does not consume/renew its pairing ID and may retry after A either commits successfully or reaches its deadline. A Manager restart invalidates A separately under the restart rule below.

## User surfaces

Normal-user surfaces are limited to:

```text
NODE_LCD
PHONE_SYSTEM_CAMERA
MINIMAL_NODE_LOCAL_BROWSER_PAGE
```

Normal users do not use:

- Linux;
- Docker;
- SSH;
- CLI;
- IP or port configuration;
- MQTT configuration;
- Home Assistant backend configuration;
- raw Setup Secret copying;
- raw pairing payload copying.

The browser is not a long-lived management application. It only:
1. starts a scan session;
2. displays discovered T1 candidates;
3. collects one explicit confirmation;
4. shows a minimal final result.

LCD remains the primary normal-product progress and failure surface.

## Discovery / pairing separation

T1 discoverability and privileged pairing exposure are separate services.

Target T1 listener semantics:

```text
47110/tcp = always-on low-privilege registration bootstrap service
47111/udp = always-on low-privilege discovery responder
47112/tcp = privileged pairing HTTP, closed while idle
```

mDNS discovery may advertise the 47110 registration bootstrap service.

An idle T1 is discoverable, but cannot accept pairing protocol traffic on 47112.

## Node-local registration portal

The production QR is a directly actionable URL, not the raw `GHN3W2` payload.

The node runs a narrow local HTTP registration portal only while:
- Wi-Fi is connected; and
- the node is unregistered.

The QR URL contains no Setup Secret, hardware ID, pairing ID or long-lived credential.

A RAM-only random scan token binds the displayed QR to the current local browser session. The scan token is not pairing correctness authority and is not persisted across reboot.

Recommended QR shape:

```text
http://<current-node-IPv4>:47113/register#t=<random-scan-token>
```

The fragment is read by page JavaScript and posted back to the same node origin. The Setup Secret never enters the phone page, URL, browser history or query string.

If DHCP changes the node IPv4 address, the QR is regenerated automatically. The user never types an IP address.

A generic ESPHome `web_server` is not used; the product should implement a narrow registration-only HTTP surface.

## Automatic Setup Secret handoff

ADR-0007 remains authoritative: first registration uses the node-generated one-time Setup Secret and simplified HMAC/HKDF bootstrap. Application-layer X25519 is not reintroduced.

After the user confirms a selected T1, the node itself transfers the Setup Secret to T1 through the registration bootstrap service. The phone does not carry the secret.

The 47110 bootstrap transport must provide confidentiality. Source design freezes:

- TLS on the bootstrap service;
- a T1 bootstrap certificate generated by product initialization;
- discovery publishes the SHA-256 fingerprint of the active bootstrap certificate;
- the node pins the discovered fingerprint for that user-confirmed candidate;
- Setup Secret is posted only after the TLS peer fingerprint matches;
- the secret is never logged, echoed or persisted by the bootstrap HTTP layer.

In the normal phone flow this is user-confirmed TOFU for the local T1 candidate. It protects against passive LAN observation and accidental endpoint mismatch without adding certificate or key prompts to the user.

The first-registration authorization model is explicitly **trusted-LAN authorization**: any client whose source is accepted as local/trusted LAN is allowed to initiate a new first-registration bootstrap. The QR and scan token protect the normal node-local user workflow but are not T1 authorization credentials. Consequently, a malicious or compromised client already inside the trusted LAN can intentionally initiate an enrollment attempt; that is an accepted consequence of the chosen trust boundary, not a protocol bypass.

The local-network active-spoofing residual risk is also accepted under this trusted-LAN model. Discovery-bound certificate pinning remains required so the normal node flow does not send Setup Secret bytes before the selected endpoint's advertised leaf fingerprint is matched.

## Identity-bound dynamic pairing window

A successful 47110 confirmation does not create credentials by itself.

T1 creates one RAM-only first-registration intent containing at least:

```text
hardware_id
pairing_id
setup_secret
source_ip
manager_id
system_id
expires_at
consumed=false
```

The intent then opens 47112 only for that exact transaction.

47112 must reject before durable registration mutation when:
- hardware ID differs;
- pairing ID differs;
- source IP differs from the confirmed node;
- the intent is expired or consumed;
- another incompatible first-registration intent is active.

The current manual `peer_ip` operator input is removed from the product path. T1 derives the peer/source IP from the accepted TLS bootstrap request and uses route-selected local addressing internally.

## Setup Secret lifecycle

The bootstrap endpoint stores Setup Secret only in the RAM-only first-registration intent.

When the bound node sends the accepted `/hello`:
1. the identity/source binding is checked first;
2. the Manager creates/updates the exact pending registration with the shared transaction deadline;
3. only then is the Setup Secret imported into the existing simplified pairing coordinator;
4. `/begin` and the existing HMAC/HKDF encrypted bundle path continue.

The retained mutable Manager-side Setup Secret buffers are zeroized on:
- successful Manager COMMIT;
- transaction expiry;
- Manager restart or equivalent process-boundary loss of the in-memory intent.

Implementations must avoid logging or persisting the secret and must keep unavoidable transient parser/library copies bounded in lifetime. The zeroization requirement applies to mutable buffers owned by the first-registration intent/coordinator; it does not claim that a high-level runtime can prove erasure of every temporary immutable process-memory copy.

Pre-deadline browser cancellation, protocol error or pairing failure does not itself destroy the intent or close 47112. The transaction remains bound to the same identity/source and absolute deadline and may retry within that deadline.

Manager restart is fail-closed: it destroys the in-memory intent and closes 47112. The old transaction is terminal and must never be resumed. Its old pairing ID is retained as a replay tombstone under ADR-0008. On the next registration attempt the node generates a **new pairing ID**; after a fresh confirmation, T1 creates a **new transaction** with a new full `now + 1800s` deadline. No remaining time, intent, Setup Secret copy or deadline from the old transaction is inherited.

Manager restart is therefore a process-boundary invalidation, not a third normal runtime close condition.

## One canonical deadline

The product first-registration transaction uses one canonical deadline:

```text
FIRST_REGISTRATION_TTL_SECONDS=1800
```

The same deadline bounds:
- the dynamic 47112 pairing exposure;
- the pending registration record created by the accepted hello;
- the simplified pairing session;
- the in-memory Setup Secret intent.

Existing 120-second repair authorization remains separate and is not widened.

No first-registration path may retain a shorter hidden TTL that can expire before the canonical 1800-second deadline.

## LCD state model

The fifth LCD page remains the registration surface while the node is unregistered.

Product states:

```text
IDLE_UNREGISTERED
DISCOVERING
WAIT_CONFIRM
REGISTERING
SUCCESS
ERROR
```

Initial user error classes:

```text
E01 = 未找到主机
E02 = 主机不可用
E03 = 主机忙
E04 = 网络中断
E05 = 注册超时
E06 = 注册失败
E07 = 二维码失效
```

Multiple T1 candidates are not an error; LCD shows a short “请在手机选择” state while the phone page lists candidates.

Recoverable pre-transaction failure returns to the same registration QR.

A transaction that reaches its 1800-second deadline retains the old pairing ID as a replay tombstone. Manager restart applies the same old-ID terminal rule because the in-memory authority is lost. In either case the device follows ADR-0008 renewal semantics, generates a new pairing ID and displays a new QR before a later fresh transaction.

A pre-deadline pairing/protocol failure does not by itself consume or renew the pairing ID; it remains inside the existing transaction until success or deadline.

LCD may use short Chinese text plus the E-code because of the 128×64 display constraint.

## Success authority

Neither QR scan, discovery, browser confirmation, Setup Secret handoff, credential bundle delivery nor local persistence alone is “联机注册成功”.

Success is shown only after the existing final pairing acknowledgement causes Manager COMMIT.

Then:
- T1 immediately closes 47112;
- Setup Secret is cleared;
- the node briefly shows “注册成功”;
- the browser page may show the same simple success state;
- the node enters normal provisioned runtime.

## Multi-T1 behavior

Discovery may return multiple candidates.

The node must not select by:
- RSSI;
- response latency;
- manager ID ordering;
- system ID ordering.

The phone page presents candidates using a simple product label such as:

```text
温室主机 <short-system-id>
```

The user chooses one. No technical addresses or certificate fingerprints are shown.

## Retirement scope

Retirement remains architecturally reserved, but new retirement implementation work is deferred.

```text
NODE_RETIREMENT_ARCHITECTURE=RESERVED
NEW_NODE_RETIREMENT_DEVELOPMENT=DEFERRED
C07_EXISTING_SOURCE_REOPEN=false
```

This ADR does not delete or rewrite existing retirement source or historical evidence.

## Compatibility / migration

The following are classified as engineering-only or superseded product behavior:

- idle automatic Manager discovery by an unregistered node;
- the LCD idle text “正在查找主机”;
- QR visibility gated by Manager `/hello`;
- raw QR code copy/paste into Terminal;
- normal-user use of `greenhouse-manager-pairing import`;
- operator-supplied `peer_ip` as a normal first-registration input.

Existing CLI and UDS paths may remain for engineering, diagnostics and controlled recovery, but they are not the product first-registration path.

## Required implementation proof

Before product live acceptance, source and tests must prove:

1. no active T1 discovery before a valid scan-session request;
2. registration QR remains available with no T1 present;
3. no Setup Secret appears in QR URL, browser page, logs or public evidence;
4. T1 discovery stays available while 47112 is closed;
5. the normal phone flow uses confirmation to open one exact identity/source-bound 47112 transaction;
6. a trusted-LAN client can initiate 47110 without QR possession, while a non-local source is rejected;
7. no hidden 120/600-second timeout truncates the 1800-second transaction;
8. wrong identity/source traffic cannot mutate registration state while the window is open;
9. successful Manager COMMIT closes 47112 immediately;
10. canonical deadline expiry closes 47112 and leaves no active credential/key/trust state;
11. a pre-deadline browser/protocol/pairing failure does not prematurely close the privileged window or mint a fresh transaction;
12. Manager restart closes fail-closed, tombstones the old pairing ID, and a later attempt uses a new pairing ID plus a fresh full 1800-second deadline;
13. LCD error mappings work without backend/CLI interaction;
14. multiple T1 candidates require user selection;
15. normal physical acceptance uses phone scan + browser confirm, not secret copy/paste.


## Transaction isolation

```text
FIRST_REGISTRATION_TTL_SCOPE=PER_TRANSACTION
FIRST_REGISTRATION_TTL_SECONDS=1800
MAX_CONCURRENT_FIRST_REGISTRATIONS_V1=1

T1_FIRST_REGISTRATION_AUTHORITY=TRUSTED_LAN_SOURCE
QR_POSSESSION_REQUIRED_FOR_T1_AUTHORIZATION=false
NORMAL_PRIVILEGED_WINDOW_CLOSE_CONDITIONS=MANAGER_COMMIT_OR_DEADLINE
SUCCESS_CLOSES_PRIVILEGED_WINDOW_IMMEDIATELY=true
PREDEADLINE_ERROR_CLOSES_PRIVILEGED_WINDOW=false
MANAGER_RESTART_FAIL_CLOSED=true
MANAGER_RESTART_OLD_PAIRING_ID_TERMINAL=true
MANAGER_RESTART_REQUIRES_NEW_PAIRING_ID=true
MANAGER_RESTART_NEW_TRANSACTION_GETS_FRESH_1800S=true
UNUSED_TTL_CARRIED_FORWARD=false
NEXT_NODE_REQUIRES_NEW_CONFIRMATION=true
NEXT_NODE_GETS_FRESH_1800S_DEADLINE=true
```

The always-on low-privilege 47110/47111 services are not part of this timer. Only the identity/source-bound privileged first-registration intent and 47112 exposure are governed by the per-transaction deadline.
