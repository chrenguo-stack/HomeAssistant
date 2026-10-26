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

mDNS discovery may advertise the 47110 registration bootstrap service, but product advertisement and UDP discovery are scoped to the product LAN interface defined below.

An idle T1 is discoverable from the trusted product LAN, but cannot accept pairing protocol traffic on 47112.

## Trusted product LAN authority

For V1, **trusted LAN** has one exact meaning. It is not “any RFC1918/private address”.

The product authority is the same customer-LAN authority already used by the T1 ingress design:

```text
TRUSTED_PRODUCT_LAN_INTERFACE=eth0
TRUSTED_PRODUCT_LAN_AUTHORITY=NetworkManager current eth0 IPv4 state
TRUSTED_PRODUCT_LAN_REQUIREMENT=exactly one current valid IPv4 subnet
IPV6_FIRST_REGISTRATION_AUTHORIZED=false
LOOPBACK_FIRST_REGISTRATION_AUTHORIZED=false
LINK_LOCAL_FIRST_REGISTRATION_AUTHORIZED=false
GENERIC_RFC1918_FALLBACK=false
```

The decision contract is:
- `eth0` must be connected;
- NetworkManager must report at least one IPv4 address and all reported IPv4 addresses must resolve to exactly one subnet;
- unspecified, loopback, multicast, link-local and `/0` states are invalid;
- if zero or multiple distinct IPv4 subnets are present, first-registration admission fails closed;
- only a source IPv4 contained in that one current subnet is trusted for product first registration;
- Docker bridge, VPN, loopback, link-local, other RFC1918/private networks and IPv6 are not trusted merely because they are locally reachable;
- there is no manual customer CIDR in the product configuration and no fallback to the predecessor broad `is_local_source()` address-class test.

47110 must reject a source outside the current trusted product subnet. 47111 must not answer it. mDNS registration advertisement must be scoped to `eth0` rather than every host interface.

The host-side NetworkManager authority is reused without widening the greenhouse-manager container privileges. The host ingress-guard/NetworkManager integration atomically publishes a non-secret runtime state file under a dedicated host runtime directory. The Manager mounts that **directory** read-only and re-reads the state for product registration decisions; it does not require D-Bus, `nmcli`, `NET_ADMIN` or another host-control capability inside the container.

The publication contract is versioned and contains only:
- schema/version;
- interface name (`eth0`);
- `available=true|false`;
- the current trusted IPv4 subnet when available;
- a reason/status code;
- publication time/generation metadata.

It contains no credential, Setup Secret, node identity or pairing identity. Public logs/evidence must not print the raw customer subnet.

On every host guard execution, including NetworkManager dispatcher events:
- a valid unique subnet is atomically published as `available=true`;
- disconnected, invalid, zero-subnet or ambiguous state is atomically published as `available=false`;
- the previous valid subnet must not be left behind as authority after a fail-closed transition.

The Manager treats missing, malformed, unavailable or schema-invalid state as **no trusted product LAN**. The runtime directory bind-mount is used rather than a single-file bind so host-side atomic replacement cannot leave the container pinned to a predecessor inode.

The trusted-subnet decision therefore follows DHCP/subnet changes without freezing a historical customer address. If the authority is unavailable or ambiguous, 47110/47111 remain non-authorizing/fail-closed even if their sockets exist.

For an already active 47112 transaction, each request still requires both the original exact `source_ip` match and membership of that source in the **current** trusted product subnet. A subnet/link change does not mint a new transaction or refresh the deadline; an unreachable or no-longer-trusted transaction remains bounded by its original deadline unless Manager process-boundary invalidation occurs.

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

The first-registration authorization model is explicitly **trusted-LAN authorization**: any client whose source IPv4 is inside the exact current trusted product subnet above is allowed to initiate a new first-registration bootstrap. The QR and scan token protect the normal node-local user workflow but are not T1 authorization credentials. Consequently, a malicious or compromised client already inside that subnet can intentionally initiate an enrollment attempt; that is an accepted consequence of the chosen trust boundary, not a protocol bypass.

The local-network active-spoofing residual risk is also accepted under this trusted-LAN model. Discovery-bound certificate pinning remains required so the normal node flow does not send Setup Secret bytes before the selected endpoint's advertised leaf fingerprint is matched.

## Identity-bound dynamic pairing window

A successful 47110 confirmation does not create credentials by itself.

Before 47110 can report `accepted=true`, T1 also creates a minimal durable **first-registration attempt ledger**. The ledger contains no Setup Secret and is the replay/restart authority for the pre-`/hello` interval.

Minimum durable fields:

```text
pairing_id                  primary replay key
hardware_id_sha256          SHA-256 of canonical hardware_id
opened_at
expires_at
state                       ACTIVE | COMMITTED | EXPIRED | RESTART_INVALIDATED
phase                       BOOTSTRAP_ACCEPTED | HELLO_OBSERVED | BUNDLE_STAGED | COMMITTING | TERMINAL
cleanup_state               NONE | REQUIRED | COMPLETE | FAILED
node_id                     nullable; internal recovery binding only
dynsec_prestate_absent      nullable boolean
application_key_prestate_absent nullable boolean
application_key_epoch       nullable integer
terminal_at                 nullable
terminal_reason             nullable
```

The raw Setup Secret, scan token, source IP, MQTT password, application-key material and SYSTEM_PEER_KEY are not stored in this ledger. `node_id` is internal recovery metadata and must not be emitted in public diagnostics.

Transaction-start authority is the durable `ACTIVE` ledger commit, not receipt of the HTTP request body. The ordering is:

```text
validate request + trusted product subnet
-> check replay / one-active-transaction constraints
-> prepare non-active RAM intent
-> durably insert ACTIVE attempt with the one canonical deadline
-> activate RAM intent
-> open exact 47112 exposure
-> only then return accepted=true
```

If the process dies before the durable `ACTIVE` commit, no transaction was accepted and the same pairing ID may retry. If the process dies at or after that commit, startup invalidation below makes the pairing ID terminal even if `/hello` was never reached.

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

Manager restart is fail-closed: it destroys the in-memory intent and closes 47112.

Before 47110/47111/47112 become product-ready on startup, Manager reconciles every durable attempt that is not already cleanly terminal. The first durable startup action for an unfinished attempt is to make its old pairing ID terminal:
- if its deadline already passed, state becomes `EXPIRED`;
- otherwise state becomes `RESTART_INVALIDATED`;
- `cleanup_state` becomes `REQUIRED`.

The old transaction must never be resumed. Its pairing ID remains a durable replay tombstone even when restart happened **before the first /hello** and therefore before `RegistrationRegistry` had created a pairing-session row.

Restart invalidation also owns all **uncommitted persistent side effects** created after `/hello`. Existing source can persist an automatic NODE_ID/lease, Broker Dynamic Security client/role and a STAGED or temporarily ACTIVE application-key epoch before the final receipt has fully committed the transaction. Losing the RAM session must not strand those objects and must not make the next fresh pairing ID look like an existing-identity repair.

The startup reconciler therefore uses the exact old pairing ID to locate and cross-check the registration row, validates the canonical hardware-ID SHA-256 against the ledger, and then applies one of three outcomes:

1. **Durable commit proven.** If the exact pairing ID already owns MQTT credential generation 1 in ACTIVE state, the same node has the expected ACTIVE application key, the exact Broker identity exists, and registration/node binding is consistent, the final receipt commit is considered durably complete even if the process died before the ledger could be marked COMMITTED. The ledger is promoted to `COMMITTED`; no rollback occurs.
2. **Commit not reached.** If exact ACTIVE MQTT generation 1 does not exist, automatic destructive cleanup is allowed only when the two-part ownership proof below is complete. The reconciler then removes only transaction-owned Broker identity, revokes the exact transaction-owned staged/temporarily-active application-key epoch, rolls back the automatic NODE_ID approval/lease, terminalizes the old registration session, and records `cleanup_state=COMPLETE`.
3. **Ambiguous or unsafe state.** Any cross-store mismatch, unprovable ownership, partial state that cannot be safely classified, or cleanup failure records `cleanup_state=FAILED` and keeps all product first-registration listeners fail-closed. It must not guess, delete an unowned DynSec object, or permit a new registration transaction.

For DynSec cleanup ownership, the transaction must first prove the exact deterministic target client/role absent and durably record `dynsec_prestate_absent=true` before provisioning them. For the initial application key, the new NODE_ID must likewise have no predecessor key state before staging and that prestate is durably recorded.

Those prestate facts are **necessary but not sufficient** destructive-cleanup authority. After the complete stage operation returns successfully, and before the encrypted bundle is returned to the node, Manager must durably advance the ledger to `phase=BUNDLE_STAGED`, bind the exact `node_id`, and record the exact initial `application_key_epoch`.

Automatic DynSec/application-key cleanup after restart requires both the corresponding durable prestate-absent proof **and** a durable `BUNDLE_STAGED` or later phase proving the stage operation completed successfully. If the process dies in the narrow cross-system gap after an external object may have been created but before `BUNDLE_STAGED` is durably recorded, ownership is ambiguous. The reconciler keeps registration fail-closed and must not automatically delete that object. This preserves KF-060: create-attempt/target-presence is not ownership proof.

The never-reused NODE_ID is an additional binding, not a substitute for this two-part ownership proof.

The same reconciliation machinery is used on canonical deadline expiry. The privileged listener closes at the deadline immediately; a failed cleanup cannot reopen it and instead leaves registration unavailable until cleanup succeeds or a separate recovery path is authorized.

A later 47110 request that reuses a terminal ledger pairing ID is rejected with the same ADR-0008 terminal semantics:
- expired attempt -> `status=rejected`, `reason=expired`, `transaction_disposition=terminal`;
- committed/restart-invalidated/replayed attempt -> `status=rejected`, `reason=replay_detected`, `transaction_disposition=terminal`.

For this successor bootstrap flow, that terminal bootstrap result invokes the **same durable pairing-ID renewal primitive** used by ADR-0008 terminal `/hello` handling. The node must durably persist a fresh random pairing ID before retrying 47110. Only after the new ID is active, old-attempt cleanup is complete, and a fresh confirmation succeeds may T1 create a **new transaction** with a new full `now + 1800s` deadline.

No remaining time, intent, Setup Secret copy or deadline from the old transaction is inherited. Manager restart is therefore a process-boundary invalidation, not a third normal runtime close condition.

## System peer trust is outside the registration transaction

`SYSTEM_PEER_KEY` remains a long-lived **T1/system-level** authority under ADR-0007/0008. To keep first-registration rollback exact, product initialization creates or validates the system peer-trust record **before** the registration services become ready. A first-registration transaction only reads the existing system peer trust; it must not call a create-or-rotate path.

Therefore:
- node registration never rotates SYSTEM_PEER_KEY;
- an aborted/expired/restart-invalidated node transaction has no transaction-owned peer-trust object to clean up;
- bundle issuance uses the already-existing peer-trust generation;
- missing/corrupt system peer trust fails registration readiness closed rather than creating it inside an active node transaction.

## One canonical deadline

The product first-registration transaction uses one canonical deadline:

```text
FIRST_REGISTRATION_TTL_SECONDS=1800
```

The same deadline bounds:
- the durable first-registration attempt ledger row;
- the dynamic 47112 pairing exposure;
- the pending registration record created by the accepted hello;
- the simplified pairing session;
- the in-memory Setup Secret intent.

Final receipt handling and expiry are serialized. A final delivery receipt accepted at or before the deadline may durably enter `COMMITTING`; once that transition is claimed, expiry cannot race it. If no such commit claim exists by the deadline, the transaction expires and enters the cleanup path above. User-visible success still requires the exact durable cross-store commit oracle to pass.

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
6. trusted-LAN authority equals NetworkManager current `eth0` unique IPv4 subnet, with no broad RFC1918/`is_local_source()` fallback;
7. 47110 rejects and 47111 does not answer sources outside that exact subnet; loopback, link-local, VPN/Docker/other private subnets and IPv6 are not product-authorized by default;
8. a trusted-product-LAN client can initiate 47110 without QR possession;
9. durable attempt `ACTIVE` state is committed before `accepted=true` and contains no Setup Secret;
10. restart before `/hello` still makes the old pairing ID terminal/replay-detected;
11. restart after `/hello` but before final durable commit either proves the exact transaction committed or rolls back only transaction-owned NODE_ID/DynSec/application-key side effects;
12. DynSec/application-key cleanup requires both durable prestate-absent proof and a durable BUNDLE_STAGED-or-later completion marker; target presence alone never proves ownership;
13. a crash between possible external creation and durable BUNDLE_STAGED leaves product first registration fail-closed rather than guessing or deleting;
14. SYSTEM_PEER_KEY is initialized/validated as T1 baseline before registration readiness and is only read by node registration;
15. a terminal bootstrap response drives the ADR-0008 durable fresh-pairing-ID renewal path before any retry;
16. no hidden 120/600-second timeout truncates the 1800-second transaction;
17. wrong identity/source traffic cannot mutate registration state while the window is open;
18. successful Manager COMMIT closes 47112 immediately;
19. canonical deadline expiry closes 47112 and reconciles uncommitted transaction-owned credential/key state;
20. a pre-deadline browser/protocol/pairing failure does not prematurely close the privileged window or mint a fresh transaction;
21. Manager restart closes fail-closed, tombstones the old pairing ID, and a later attempt uses a new pairing ID plus a fresh full 1800-second deadline only after cleanup is complete;
22. LCD error mappings work without backend/CLI interaction;
23. multiple T1 candidates require user selection;
24. normal physical acceptance uses phone scan + browser confirm, not secret copy/paste.


## Transaction isolation

```text
FIRST_REGISTRATION_TTL_SCOPE=PER_TRANSACTION
FIRST_REGISTRATION_TTL_SECONDS=1800
MAX_CONCURRENT_FIRST_REGISTRATIONS_V1=1

T1_FIRST_REGISTRATION_AUTHORITY=NETWORKMANAGER_ETH0_UNIQUE_IPV4_SUBNET
TRUSTED_PRODUCT_LAN_INTERFACE=eth0
GENERIC_RFC1918_OR_IS_LOCAL_SOURCE_FALLBACK=false
IPV6_FIRST_REGISTRATION_AUTHORIZED=false
LOOPBACK_FIRST_REGISTRATION_AUTHORIZED=false
QR_POSSESSION_REQUIRED_FOR_T1_AUTHORIZATION=false
DURABLE_FIRST_REGISTRATION_ATTEMPT_LEDGER=true
SETUP_SECRET_PERSISTED_IN_ATTEMPT_LEDGER=false
ACTIVE_ATTEMPT_COMMITTED_BEFORE_ACCEPTED_RESPONSE=true
RESTART_PRE_HELLO_PAIRING_ID_TOMBSTONED=true
RESTART_POST_HELLO_UNCOMMITTED_SIDE_EFFECT_RECONCILIATION=true
DYNSEC_DESTRUCTIVE_CLEANUP_REQUIRES_DURABLE_PRESTATE_OWNERSHIP=true
APPLICATION_KEY_CLEANUP_REQUIRES_DURABLE_PRESTATE_OWNERSHIP=true
AMBIGUOUS_RECONCILIATION_FAILS_REGISTRATION_CLOSED=true
SYSTEM_PEER_TRUST_INITIALIZED_BEFORE_REGISTRATION_READY=true
SYSTEM_PEER_TRUST_MUTATED_BY_REGISTRATION=false
TERMINAL_BOOTSTRAP_RESULT_USES_ADR0008_RENEWAL=true
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
