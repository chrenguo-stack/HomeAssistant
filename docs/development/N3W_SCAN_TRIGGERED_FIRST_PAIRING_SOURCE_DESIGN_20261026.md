# N3-W scan-triggered first registration source design — 2026-10-26

## 0. Task / boundary

```text
TASK=N3W_SCAN_TRIGGERED_FIRST_PAIRING_SOURCE_DESIGN_20261026_01
BASE_MAIN=507dbd49495c558b1344f7d713938b733b3bad18
ARCHITECTURE_AUTHORITY=docs/adr/0011-n3w-scan-triggered-first-registration.md

MODE=SOURCE_DESIGN_ONLY
PRODUCT_SOURCE_MUTATION=false
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
BOARD_MUTATION=false
PAIRING_EXECUTION=false
MERGE=false
```

This design translates ADR-0011 into exact components, source seams, protocol boundaries, tests and implementation order.

Authority note:
- ADR-0011 intentionally replaces the old product requirement that the Setup Secret itself be encoded in the user-facing QR;
- ADR-0011 also replaces the UDS/CLI secret-import path as the normal first-registration product entry;
- ADR-0007 HMAC/HKDF bootstrap security and ADR-0008 random pairing/replay semantics remain authoritative;
- the UDS remains available for engineering/ops use.

It does not declare implementation complete.

## 1. Current-source findings

### 1.1 Node already creates pairing material before Manager discovery

Current:

`firmware/esphome_rc/components/greenhouse_n3w_core/n3w_simple_pairing_client.cpp`

`prepare_bootstrap_()`:
- loads/creates Setup Secret;
- loads or creates a durable random pairing ID.

Therefore the node already possesses enough local material to prepare a registration QR before T1 exists.

### 1.2 Idle node currently performs automatic discovery

Current:

`SimpleProductComponent::loop()`

calls `advance_pairing_()` whenever the product is unprovisioned.

`advance_pairing_()` eventually calls:

```text
SimplePairingClient::run_once()
-> discover_()
-> send_hello_()
-> pair_with_()
```

This is incompatible with ADR-0011 because discovery must be user-scan-triggered.

### 1.3 QR display is incorrectly gated by Manager hello

Current:

`firmware/esphome_rc/f1_0_rc2/packages/n3w_product_transport.yml`

requires:

```text
Wi-Fi connected
AND !provisioned
AND pairing_handoff_ready()
```

before it renders the pairing QR.

`pairing_handoff_ready_` is only set after Manager `/hello` returns PROCEED.

This gate must stop controlling QR visibility.

### 1.4 T1 discovery and privileged pairing are currently coupled

Current simplified pairing runtime assembles:
- UDP 47111 discovery;
- HTTP 47112 pairing;
- one shared worker lifecycle.

The dynamic pairing controller starts them together.

Therefore a factory pairing-disabled T1 currently has neither active pairing HTTP nor simplified UDP discovery.

ADR-0011 requires these to be split.

### 1.5 Current T1 open path requires operator-supplied peer_ip

`DynamicPairingWindowController.open_window(peer_ip=...)` uses the supplied IP to select the broker-side local address.

This is suitable for controlled engineering onboarding but not the product user path.

The product path must derive the node source IP from the node's accepted registration-bootstrap TLS request.

### 1.6 Current timers conflict with the 30-minute product transaction

Current independent limits include:
- dynamic window default 300 s;
- dynamic window max 600 s;
- registration pending TTL default 120 s;
- simplified pairing session TTL default 120 s and max 600 s;
- ordinary repair intent capped at 120 s.

Only ordinary repair should remain at 120 s.

The first-registration path must use one 1800-second canonical deadline.

## 2. Target component split

### 2.1 Node

Add narrow first-registration components under:

`firmware/esphome_rc/components/greenhouse_n3w_core/`

Recommended files:

```text
n3w_registration_portal.h/.cpp
n3w_registration_discovery.h/.cpp
n3w_registration_state.h/.cpp
n3w_registration_bootstrap_client.h/.cpp
```

Keep current:
- `n3w_simple_pairing_client.*` for the actual authenticated pairing protocol;
- `n3w_simple_product_component.*` as the top-level product orchestrator.

Responsibilities:

```text
RegistrationPortal
  phone-local HTTP page/API only

RegistrationDiscovery
  scan-triggered T1 mDNS/UDP candidate collection only

RegistrationBootstrapClient
  TLS-pinned user-confirm request to T1 47110
  no pairing protocol

SimplePairingClient
  /hello -> /begin -> proof -> credentials -> ACK

SimpleProductComponent
  state orchestration only
```

### 2.2 T1

Add a permanently available, low-privilege registration bootstrap layer separate from dynamic pairing.

Recommended runtime modules:

```text
host/greenhouse-manager/src/greenhouse_manager/runtime/
  n3w_registration_discovery.py
  n3w_registration_bootstrap.py
  n3w_first_registration_intent.py
  n3w_first_registration_ledger.py
  n3w_trusted_product_lan.py
```

`n3w_trusted_product_lan.py` owns the Manager-side product first-registration admission parser/checker. It does **not** query NetworkManager directly from the container. The host-side NetworkManager/KF-097 authority atomically publishes a versioned trusted-product-LAN state file; the Manager mounts the parent runtime directory read-only and re-reads that file for registration decisions. The Manager image does not gain D-Bus, `nmcli`, `NET_ADMIN` or another host-control capability. Shared fixtures/contract tests must keep the host decision and Manager parser semantics equivalent.

`n3w_first_registration_ledger.py` owns the non-secret durable attempt/tombstone lifecycle needed to make restart-before-`/hello` non-replayable.

Modify:

```text
n3w_dynamic_pairing_window.py
n3w_simplified_pairing_runtime.py
n3w_simplified_pairing_endpoint.py
n3w_simplified_pairing.py
registration.py
config.py
app.py
```

The always-on Manager process owns:
- low-privilege discovery;
- low-privilege TLS bootstrap;
- dynamic privileged pairing window controller.

## 3. Ports and exposure

Freeze product semantics:

```text
47110/tcp = registration bootstrap TLS
47111/udp = registration discovery fallback
47112/tcp = privileged pairing HTTP
```

Idle factory/normal T1:

```text
TCP47110=LISTEN
UDP47111=LISTEN
TCP47112=CLOSED
```

This intentionally replaces the earlier acceptance assumption that 47111 must be closed whenever pairing is disabled.

Security meaning:

- 47110/47111 are not pairing exposure;
- they cannot issue credentials;
- they cannot create NODE_ID or activate credential/key/trust state by themselves;
- 47112 is the only privileged pairing protocol surface;
- the T1 authorization boundary is **NetworkManager current `eth0` unique IPv4 subnet**, not generic private-address classification;
- a source is product-authorized only when its IPv4 belongs to that exact current subnet;
- loopback, link-local, IPv6, Docker/VPN/other private subnets and generic RFC1918 ranges are not product-authorized merely because they are locally reachable;
- QR possession, node scan token and browser confirmation are normal-product UX controls, not T1-side authorization credentials;
- in the normal phone flow, user confirmation causes the node to submit 47110; however a client already inside the trusted product subnet is intentionally permitted to submit an equivalent valid bootstrap request directly.

There is no product fallback to current broad `pairing_discovery.is_local_source()` semantics.

## 4. T1 passive discovery protocol

### 4.1 Trusted product LAN admission

Freeze one admission source of truth:

```text
TRUSTED_PRODUCT_LAN_INTERFACE=eth0
TRUSTED_PRODUCT_LAN_AUTHORITY=NetworkManager current eth0 IPv4 state
TRUSTED_PRODUCT_LAN_CARDINALITY=exactly one distinct IPv4 subnet
GENERIC_RFC1918_FALLBACK=false
IPV6_FIRST_REGISTRATION_AUTHORIZED=false
LOOPBACK_FIRST_REGISTRATION_AUTHORIZED=false
LINK_LOCAL_FIRST_REGISTRATION_AUTHORIZED=false
```

The host decision mirrors the already proven KF-097 guard contract:
1. `eth0` must be NetworkManager-connected;
2. read current `IP4.ADDRESS` from NetworkManager;
3. every nonempty value must parse as IPv4 interface state;
4. reject unspecified, loopback, multicast, link-local and `/0`;
5. all valid addresses must collapse to exactly one IPv4 network;
6. zero or multiple distinct networks => fail closed;
7. a request source is authorized only if its IPv4 belongs to that exact network.

Authority transport is frozen as a host-published runtime file rather than in-container NetworkManager access:

```text
HOST_TRUSTED_LAN_RUNTIME_DIR=/run/n3wfc4-trusted-lan
HOST_TRUSTED_LAN_STATE_FILE=/run/n3wfc4-trusted-lan/state.json
MANAGER_TRUSTED_LAN_MOUNT=/run/n3w/trusted-product-lan
MANAGER_TRUSTED_LAN_STATE_FILE=/run/n3w/trusted-product-lan/state.json
MOUNT_MODE=directory bind, read-only
```

The host publisher writes by temp-file + fsync/close + atomic replace inside the directory. A directory bind is required; a single-file bind is forbidden because atomic replacement could otherwise leave the container pinned to a predecessor inode.

State schema is narrow and non-secret:

```json
{
  "schema": "gh.trusted-product-lan/1",
  "interface": "eth0",
  "available": true,
  "subnet": "<current IPv4 CIDR>",
  "reason": "unique_ipv4_subnet",
  "published_at": "<UTC timestamp>",
  "generation": "<opaque host-local generation>"
}
```

When NetworkManager state is disconnected, invalid, absent or ambiguous, the host atomically publishes `available=false` with no usable subnet. It must not leave a predecessor valid subnet as current authority.

The Manager treats missing, malformed, wrong-schema, wrong-interface or `available=false` state as no trusted product LAN. Raw customer subnet is never written to public logs/evidence.

Host firewall defense-in-depth uses the same decision for product registration ingress:
- TCP/47110 allowed only from `eth0 + current trusted subnet`;
- UDP/47111 allowed only from `eth0 + current trusted subnet`;
- TCP/47112, when a listener exists, is also limited to `eth0 + current trusted subnet`;
- no loopback exception exists for these product registration ports;
- zero/ambiguous/unavailable trusted subnet => DROP for these product registration ports.

This host guard does not replace application-layer source/identity checks; it prevents off-interface/off-subnet traffic from reaching the product listeners.

47111 behavior:
- answer UDP discovery only when the datagram source passes this admission;
- scope mDNS registration advertisement to `eth0`;
- do not advertise/respond on Docker, VPN, loopback or other host interfaces;
- if trusted-subnet authority is unavailable/ambiguous, emit no product discovery response.

47110 uses the same admission decision. No second independent “local network” definition is allowed.

The host publisher is refreshed at product activation and on relevant NetworkManager dispatcher events; customer LAN CIDR is not frozen into Compose/env/source. A DHCP/subnet change therefore changes the trusted product subnet without manual configuration. The Manager re-reads the mounted state rather than caching a predecessor subnet across requests.

For an active first-registration transaction, 47112 keeps its exact original `source_ip` binding and also rechecks that source against the current trusted product subnet on every request. A subnet change never refreshes the transaction or its deadline.

### 4.2 Candidate protocol

Introduce a dedicated candidate schema rather than advertising a closed pairing endpoint.

Example:

```json
{
  "schema": "gh.registration.candidate/1",
  "manager_id": "manager-...",
  "system_id": "system-...",
  "system_id_hint": "1a2b3c4d",
  "host": "192.0.2.10",
  "bootstrap_scheme": "https",
  "bootstrap_port": 47110,
  "bootstrap_path": "/v1/registration/confirm",
  "bootstrap_tls_sha256": "<64 lowercase hex>",
  "protocol": "gh.n3w.first-registration/1",
  "ttl_s": 30,
  "busy": false
}
```

Notes:
- the example address is documentation-only;
- real host uses route-selected local IPv4;
- discovery returns no Setup Secret, pairing ID, credential, CA private material or privileged 47112 path;
- `system_id_hint` supports a human label such as `温室主机 1A2B`;
- `busy` may be shown as “主机忙” but must not disclose another node identity.

mDNS:
- advertise the registration bootstrap service, not the dynamic pairing endpoint.

UDP:
- continue nonce/request-ID correlation;
- local-source check;
- strict schema;
- rate limit;
- no amplification-sized response.

## 5. T1 bootstrap TLS

### 5.1 Certificate

Product initialization creates a dedicated T1 registration-bootstrap TLS certificate/key.

Requirements:
- generated per T1/system;
- private key never sent to nodes;
- mounted read-only into greenhouse-manager;
- active leaf certificate SHA-256 fingerprint is available to the discovery service;
- replacement/rotation changes the advertised fingerprint.

The node does not need to understand system CA before first registration.

It uses user-confirmed TOFU:
1. scan-triggered discovery obtains candidate + certificate fingerprint;
2. phone shows simple T1 identity;
3. user confirms;
4. node performs the TLS handshake to the selected candidate;
5. the leaf certificate DER SHA-256 is checked against the selected candidate before any HTTP request body containing Setup Secret is transmitted;
6. only after an exact match may the node send Setup Secret.

No fingerprint is shown to the user.

Implementation rule:
- `skip_cert_common_name_check`, disabled CA verification, or a post-request certificate check is not certificate pinning;
- if `esp_http_client` cannot enforce the exact leaf fingerprint before body transmission, the bootstrap client must use an `esp_tls` / mbedTLS handshake path with an explicit verification callback and only construct/send the HTTP request after pin success;
- pin mismatch must close the socket and map to E02 without emitting Setup Secret bytes.

### 5.2 Bootstrap endpoint

```text
POST /v1/registration/confirm
```

Exact request:

```json
{
  "schema": "gh.registration.confirm/1",
  "manager_id": "<selected manager>",
  "system_id": "<selected system>",
  "hardware_id": "<node hardware id>",
  "pairing_id": "<current random pairing id>",
  "setup_secret": "<43-char base64url secret>"
}
```

The HTTP layer:
- requires TLS;
- accepts only source IPv4 inside the current NetworkManager-derived `eth0` trusted product subnet;
- rejects loopback, link-local, IPv6, Docker/VPN/other subnets and all generic private-address fallback;
- treats trusted-product-subnet membership as sufficient authorization to initiate first registration;
- does not require proof of QR possession, scan token possession or browser confirmation;
- intentionally permits a trusted-product-LAN client to submit its own syntactically valid hardware ID, pairing ID and Setup Secret;
- uses exact field sets;
- rejects oversized input;
- is rate limited;
- never logs request body;
- never echoes Setup Secret;
- does not persist Setup Secret.

This is an explicit threat-model decision, not an accidental bypass. A malicious or compromised client already inside the trusted product subnet may initiate an enrollment attempt and, if it follows the bound 47110 -> 47112 flow from the same accepted source, may complete that enrollment. Product security therefore relies on the exact current `eth0` subnet boundary for initiation authorization. The node QR remains the normal-user entry point but is not a Manager authorization token.

Response on acceptance:

```json
{
  "schema": "gh.registration.confirm-result/1",
  "accepted": true,
  "status": "accepted",
  "manager_id": "<manager>",
  "system_id": "<system>",
  "pairing_host": "<route-selected local host>",
  "pairing_port": 47112,
  "pairing_path": "/v2/pairing",
  "expires_in_seconds": 1800
}
```

The response contains no credentials or secret.

A terminal replay/expiry response uses the ADR-0008 terminal vocabulary so the node can enter the same durable pairing-ID renewal path:

```json
{
  "schema": "gh.registration.confirm-result/1",
  "accepted": false,
  "status": "rejected",
  "reason": "replay_detected",
  "transaction_disposition": "terminal"
}
```

For an attempt whose canonical deadline already expired, `reason=expired` may be returned instead. Both terminal reasons require the same durable fresh-pairing-ID renewal primitive used by existing terminal `/hello` handling before 47110 is retried.

Non-terminal conflict responses classify at least:

```text
registration_busy
identity_invalid
manager_mismatch
system_mismatch
trusted_product_lan_unavailable
source_not_trusted_product_lan
bootstrap_tls_mismatch (node-local classification)
bootstrap_unavailable
```

## 6. Durable first-registration attempt ledger

Add one persistent table owned by `n3w_first_registration_ledger.py`:

```text
first_registration_attempts

pairing_id TEXT PRIMARY KEY
hardware_id_sha256 TEXT NOT NULL
opened_at TEXT NOT NULL
expires_at TEXT NOT NULL
state TEXT NOT NULL
terminal_at TEXT
terminal_reason TEXT
```

Allowed states:

```text
ACTIVE
COMMITTED
EXPIRED
RESTART_INVALIDATED
```

The table deliberately does **not** contain:
- Setup Secret;
- raw hardware ID;
- scan token;
- source IP;
- credential material;
- TLS private material.

`pairing_id` is the exact durable replay key. `hardware_id_sha256` is only a non-secret binding/audit value and is never used as a replacement for the exact runtime hardware-ID check on 47112.

### 6.1 Transaction-start ordering

47110 acceptance order is frozen:

```text
strict request validation
-> trusted product LAN admission
-> existing-terminal-pairing-id check
-> one-active-transaction check
-> prepare non-active mutable RAM intent
-> deadline = now + 1800
-> durable INSERT ACTIVE attempt
-> activate RAM intent with the same deadline
-> open exact identity/source-bound 47112
-> return accepted=true
```

The `ACTIVE` database commit is the **transaction-start authority**.

If failure occurs before that commit, the Manager must not return `accepted=true`; no transaction exists and the node may retry the same pairing ID.

If the durable commit succeeds but 47112 cannot yet be exposed, the row remains `ACTIVE` with the original deadline. The same-process exact duplicate request may retry completion of the same transaction; it must not create a second row or a new deadline. If the RAM intent is no longer available, the service fails closed and does not reconstruct a new intent with a refreshed deadline.

### 6.2 Replay decision

Before accepting a new 47110 transaction:
- no ledger row for pairing ID -> may proceed if all other checks pass;
- `ACTIVE` row + exact current-process RAM intent/source/identity -> idempotent same transaction only;
- terminal row -> reject terminal;
- `ACTIVE` row with no matching current RAM intent -> fail closed; never reinterpret as fresh.

Terminal mapping:

```text
EXPIRED             -> expired + terminal
COMMITTED           -> replay_detected + terminal
RESTART_INVALIDATED -> replay_detected + terminal
```

Terminal rows are replay tombstones and are not garbage-collected while the product registration database remains authoritative.

### 6.3 Startup invalidation

Before any product 47110/47111/47112 service becomes active after Manager startup:

```text
for every ACTIVE first_registration_attempt:
  if now >= expires_at:
    state = EXPIRED
    terminal_reason = expired
  else:
    state = RESTART_INVALIDATED
    terminal_reason = manager_restart
  terminal_at = now
commit
```

Only after that atomic sweep succeeds may product registration listeners be considered ready.

This closes the exact restart-before-`/hello` hole: the old pairing ID remains terminal even though no `RegistrationRegistry.pairing_sessions` row ever existed.

### 6.4 Terminal updates

On final ACK -> Manager COMMIT:
- mark ledger row `COMMITTED`;
- then/atomically with exposure closure, clear intent and close 47112.

On canonical deadline:
- mark row `EXPIRED`;
- clear intent and close 47112.

The ledger terminal update must never persist Setup Secret.

## 7. FirstRegistrationIntent

New RAM-only Manager object:

```python
FirstRegistrationIntent(
    hardware_id,
    pairing_id,
    setup_secret,
    source_ip,
    manager_id,
    system_id,
    opened_at,
    expires_at,
    consumed,
)
```

Properties:
- exactly one active first-registration intent in V1;
- duplicate exact confirmation from the same source may be idempotent only when it matches the current `ACTIVE` ledger row and current RAM intent;
- conflicting second identity gets busy/conflict;
- the intent deadline must equal the durable ledger deadline exactly;
- Manager restart destroys the intent and fail-closes 47112;
- startup atomically terminalizes predecessor `ACTIVE` ledger rows before listeners become ready;
- the old transaction must not resume after Manager restart;
- the old pairing ID becomes terminal/replay-tombstoned under ADR-0008 even when restart happened before `/hello`;
- the next registration attempt must use a new pairing ID and, after fresh confirmation, a new full 1800-second transaction;
- retained mutable secret buffers are explicitly zeroized on success, deadline expiry and Manager/process-boundary invalidation;
- unavoidable transient high-level runtime/parser copies must be bounded in lifetime and must never be logged or persisted; the design does not claim provable erasure of every immutable process-memory copy;
- no raw identity/secret in logs;
- public diagnostics use SHA-256 identities only.

The RAM intent is the current-process authority for opening 47112. The durable ledger is the cross-restart replay/terminal authority. Neither can substitute for the other.

## 8. Dynamic pairing window redesign

Split current responsibilities.

### 8.1 Registration discovery remains outside the window

47111 is not started/stopped by `DynamicPairingWindowController`.

### 8.2 47112 becomes identity-bound

Replace the product-path concept:

```text
open_window(peer_ip, seconds)
```

with an internal operation conceptually equivalent to:

```text
open_first_registration(intent)
```

The engineering CLI may retain `open_window(peer_ip,...)` as a separate engineering path until explicitly retired.

The product window has:
- expected hardware ID;
- expected pairing ID;
- expected source IP;
- exact 1800-second deadline.

Before `RegistrationRegistry.observe_hello()`, the pairing HTTP endpoint checks all three.

Mismatch must fail before durable registration mutation.

## 9. Setup Secret bridge into existing coordinator

Current `SimplifiedPairingCoordinator.import_setup_secret()` requires a PENDING registration.

Do not weaken that invariant.

New sequence:

```text
bootstrap confirm
-> store secret only in FirstRegistrationIntent
-> open exact 47112 window

node /hello
-> validate source/hardware/pairing against intent
-> RegistrationRegistry.observe_hello(... exact shared deadline ...)
-> if hello accepted:
     coordinator.import_setup_secret(...)
-> return hello PROCEED

node /begin
-> existing Setup Secret proof
-> existing HKDF bootstrap
-> existing encrypted credential delivery
-> existing ACK/COMMIT
```

This preserves ADR-0007/0008 security flow while removing manual UDS secret import from the normal user path.

The existing Manager-owned UDS and `greenhouse-manager-pairing import` remain engineering/ops interfaces, not normal first-registration UX.

## 10. Canonical 1800-second deadline

Create one product constant:

```text
FIRST_REGISTRATION_TTL_SECONDS=1800
```

At bootstrap confirmation:

```text
deadline = now + 1800 s
```

The same absolute deadline is supplied to all first-registration layers, including the durable attempt ledger.

Transaction isolation is explicit:

```text
FIRST_REGISTRATION_TTL_SCOPE=PER_TRANSACTION
MAX_CONCURRENT_FIRST_REGISTRATIONS_V1=1
UNUSED_TTL_CARRIED_FORWARD=false
NEXT_NODE_REQUIRES_NEW_CONFIRMATION=true
NEXT_NODE_GETS_FRESH_1800S_DEADLINE=true
```

A/B/C registration example:
- A confirmation creates only Transaction-A;
- if A commits at 80 s, Transaction-A and 47112 close immediately and its unused time is discarded;
- if A encounters a pre-deadline browser/protocol/pairing error, Transaction-A remains the same identity/source-bound transaction and keeps the same absolute deadline;
- B then requires a new confirmation and starts Transaction-B with a full new 1800-second deadline only after A commits or A reaches its deadline;
- while A remains active, B receives `registration_busy` and retains its current pre-transaction QR/pairing identity;
- if Manager restarts while A is active, A is fail-closed and terminal, A's old pairing ID is not resumed, and the next attempt uses a new pairing ID plus a fresh `now + 1800s` deadline.

Manager restart never carries forward the old deadline, remaining time, intent or Setup Secret.

Required source changes:

### `n3w_dynamic_pairing_window.py`

- product maximum becomes at least 1800;
- product first-registration window receives absolute deadline or exactly 1800 s;
- repair/recovery timing remains separately bounded.

### `registration.py`

Extend `observe_hello()` with an optional authorized expiry/deadline override used only by the identity-bound first-registration path.

Default callers retain current `pending_ttl_s` behavior.

The new path must not mutate the global pending TTL.

### `n3w_simplified_pairing.py`

Permit product first-registration session lifetime up to 1800 s.

`begin()` continues:

```text
expires_at = min(session deadline, registration expires_at)
```

but both values now derive from the same first-registration deadline.

Ordinary repair:
- remains <=120 s;
- is not widened by this design.

## 11. Privileged-window close semantics

Current engineering onboarding closes the window externally.

The product first-registration controller owns the 47112 lifetime.

During normal Manager uptime there are exactly two semantic close conditions:
- final ACK -> Manager COMMIT;
- canonical 1800-second deadline expiry.

Pre-deadline browser cancellation, explicit user cancellation, protocol error, pairing failure or retryable worker error does not by itself close 47112, clear the transaction, renew the pairing ID or mint a fresh 1800-second budget. The same exact identity/source-bound transaction remains active until Manager COMMIT or its original absolute deadline.

Manager restart, process loss, or an equivalent runtime failure that destroys the in-memory intent is handled separately as **fail-closed process-boundary invalidation**:
- 47112 is closed;
- the old transaction is terminal and cannot be resumed;
- the old pairing ID becomes a replay tombstone;
- the next attempt generates a new pairing ID;
- a fresh confirmation creates a new transaction with a full new 1800-second deadline;
- no old remaining time or deadline is inherited.

This restart/fault rule is not a third normal transaction close condition; it is the consequence of losing the RAM-only authority required to keep the privileged window valid.

After successful COMMIT or deadline expiry:
- 47110/47111 remain available;
- 47112 has zero listener;
- retained mutable intent/coordinator Setup Secret buffers are zeroized;
- intent is cleared;
- success/timeout state may remain available to the node/browser for a short non-secret observation period.

## 12. Node registration portal

### 12.1 Server lifetime

Custom narrow HTTP server on node port 47113.

Start only when:

```text
Wi-Fi connected
AND node unregistered
```

Stop when:
- Wi-Fi disconnects;
- registration commits;
- product enters unrecoverable local error.

Do not enable generic ESPHome `web_server`.

### 12.2 QR

Generate a RAM-only 128-bit scan token.

QR URL:

```text
http://<current STA IPv4>:47113/register#t=<base64url scan token>
```

Rules:
- no Setup Secret;
- no pairing ID;
- no hardware ID;
- no broker/T1 locator;
- no long-lived credential.

On IPv4 change, regenerate the QR URL.

The scan token:
- is RAM-only;
- may rotate on boot;
- is not pairing correctness authority;
- only authorizes local portal actions for the currently displayed QR.

### 12.3 HTTP routes

```text
GET  /register
POST /api/v1/register/start
POST /api/v1/register/status
POST /api/v1/register/confirm
POST /api/v1/register/retry
```

All dynamic API requests require:
- current scan token or derived scan-session token;
- same current unregistered state;
- local source;
- bounded body;
- rate limit.

The static page:
- contains inline HTML/CSS/JS only;
- no external network resources;
- no analytics;
- no cookies;
- no localStorage;
- no Setup Secret;
- `Cache-Control: no-store`.

The first successful `start` request is the actual scan trigger.

## 13. Node discovery session

Add RAM-only state:

```text
IDLE
DISCOVERING
CANDIDATES_READY
WAIT_CONFIRM
BOOTSTRAP
PAIRING
SUCCESS
ERROR
```

No discovery code runs in `IDLE`.

On `/start`:
- create/attach scan session;
- perform one bounded discovery sequence;
- collect up to a small fixed maximum of candidates;
- dedupe by manager/system/endpoint;
- do not auto-select multiple candidates.

Recommended discovery budget:
- mDNS first;
- UDP fallback;
- total active search bounded to approximately 5–10 seconds;
- no repeated discovery loop after the scan session becomes idle/error.

This discovery budget is not the 30-minute pairing transaction TTL.

## 14. Phone page

Exactly one healthy candidate:

```text
联机注册

节点：<friendly node suffix>
主机：温室主机 <system hint>

[确认联机注册]
```

Multiple candidates:
- show simple candidate buttons;
- no IP, port, fingerprint, MQTT or certificate details.

No candidate:
- minimal text may say `未找到主机，请查看设备屏幕`;
- LCD E01 remains primary.

After confirmation:
- browser page says `正在联机注册，请查看设备屏幕`;
- it polls node-local status only;
- it never calls T1 directly.

## 15. Node confirmation -> T1 bootstrap

`POST /api/v1/register/confirm` validates:
- scan session still current;
- pairing ID has not changed;
- selected candidate still valid;
- node remains unregistered.

Then:
1. set LCD state REGISTERING/BOOTSTRAP;
2. connect node -> T1 47110 via TLS;
3. pin certificate fingerprint from the selected candidate;
4. send `gh.registration.confirm/1`;
5. on acceptance, receive 47112 locator/deadline;
6. invoke existing `SimplePairingClient` against that exact endpoint.

The phone never receives Setup Secret.

## 16. Refactor `SimplePairingClient`

Current `run_once()` couples discovery + hello + full pairing.

Refactor into explicit phases while preserving protocol logic:

```text
prepare_bootstrap()
pair_with_candidate(candidate, transaction_deadline)
resume_pending_ack()
```

The scan-triggered registration orchestrator owns discovery.

Remove/stop using automatic `run_once() -> discover_()` from normal unregistered loop.

`pair_with_candidate()`:
- sends hello;
- honors ADR-0008 WAIT / RENEW semantics;
- proceeds through begin/establish/credentials/ack;
- reports terminal result to registration state.

Do not make `pairing_handoff_ready` a display authority.

It may be deleted or retained only as an internal protocol-state diagnostic.

## 17. LCD source changes

Current:

`firmware/esphome_rc/f1_0_rc2/packages/display.yml`

and:

`n3w_product_transport.yml`

must change so:

### Idle unregistered

```text
联机注册
<QR>
扫码注册
```

Exact final 128×64 wording/layout may be tuned after render tests.

### During discovery

```text
联机注册
正在搜索
```

### Waiting for phone choice/confirmation

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

Error text may occupy two lines if required by font/layout.

Recoverable error:
- display for a short bounded time;
- return automatically to the registration QR.

No “正在查找主机” idle state remains.

## 18. Error mapping

Internal errors stay detailed.

User LCD mapping:

```text
DISCOVERY_EMPTY                     -> E01
DISCOVERY_TIMEOUT                   -> E01

BOOTSTRAP_CONNECT_FAILED            -> E02
BOOTSTRAP_TLS_PIN_MISMATCH          -> E02
BOOTSTRAP_SERVICE_UNHEALTHY         -> E02

T1_REGISTRATION_BUSY                -> E03

WIFI_LOST_DURING_ACTIVE_TRANSACTION -> E04
PAIRING_HTTP_UNREACHABLE            -> E04

TRANSACTION_DEADLINE                -> E05

PROTOCOL_REJECTED_NON_RENEWABLE     -> E06
CREDENTIAL_STAGE_FAILED             -> E06
FINAL_COMMIT_FAILED                 -> E06

TERMINAL_EXPIRED
TERMINAL_REPLAY_DETECTED
OR LOCAL_QR_SESSION_STALE           -> E07
```

A user error code is not the engineering root-cause code.

## 19. QR renewal behavior

Pre-transaction discovery/bootstrap failure:
- do not consume pairing ID;
- keep current QR/pairing identity.

Pre-deadline pairing/protocol failure inside an active transaction:
- does not close 47112;
- does not consume or renew the pairing ID;
- does not create a new transaction or refresh the 1800-second deadline;
- may retry only inside the same identity/source-bound transaction before the original deadline.

Canonical deadline expiry:
- preserve the expired pairing ID as a replay tombstone;
- use existing ADR-0008 renewal path;
- generate a fresh pairing ID durably;
- QR updates;
- a later fresh confirmation receives a new full 1800-second deadline.

Manager restart/process-boundary invalidation:
- also makes the old pairing ID terminal/replay-tombstoned because the RAM-only intent authority is gone;
- never resumes the old transaction;
- requires a new pairing ID before the next registration transaction;
- the next confirmed transaction receives a fresh full 1800 seconds.

A `replay_detected` response for an already terminal old pairing ID follows the same ADR-0008 renewal path and must not reopen the old transaction.

No whole-NVS reset.

## 20. Browser / network edge cases

### Phone cannot reach node

If the phone never reaches the node-local page, the node cannot know a scan occurred.

The browser's connection failure is unavoidable first feedback.

No LCD error is synthesized without a node-observed event.

### Phone closes browser after confirm

Registration continues because the confirmed transaction is node/T1-owned.

LCD remains authoritative.

### Phone closes browser before confirm

No first-registration transaction exists.

Scan session expires and node returns to idle QR without changing pairing ID.

### Node Wi-Fi changes IPv4

Idle QR regenerates.

Active browser session may fail; user rescans.

No fixed IP configuration is required.

## 21. Existing engineering onboarding

`tools/n3w_t1_first_pairing_onboarding.py` remains temporarily as an engineering/diagnostic tool.

It must no longer be used as proof of final product UX.

Specifically:

```text
scan raw GHN3W2
-> copy string
-> paste into Terminal
```

is prohibited for final product acceptance.

A later acceptance executor should instead inspect public-safe Manager/DB/listener evidence while the physical operator performs:

```text
phone scan
-> browser candidate
-> confirm
-> LCD success/error
```

No secret enters chat, GitHub or terminal output.

## 22. Source files expected to change in implementation

### Node

```text
firmware/esphome_rc/components/greenhouse_n3w_core/
  n3w_simple_product_component.h
  n3w_simple_product_component.cpp
  n3w_simple_pairing_client.h
  n3w_simple_pairing_client.cpp
  <new registration portal/discovery/bootstrap/state files>

firmware/esphome_rc/f1_0_rc2/packages/
  n3w_product_transport.yml
  display.yml
  core.yml (only if registration server integration requires it)
```

### T1 / Manager

```text
host/greenhouse-manager/src/greenhouse_manager/runtime/
  app.py
  config.py
  registration.py
  n3w_dynamic_pairing_window.py
  n3w_simplified_pairing.py
  n3w_simplified_pairing_endpoint.py
  n3w_simplified_pairing_runtime.py
  n3w_registration_discovery.py
  n3w_registration_bootstrap.py
  n3w_first_registration_intent.py
  n3w_first_registration_ledger.py
  n3w_trusted_product_lan.py
```

### Host / firstboot / deployment

Expected source scope includes:
- host-side trusted-product-LAN publisher/guard using the existing KF-097 NetworkManager decision contract;
- shared pure trusted-subnet decision helper or exact cross-contract fixtures so Broker and registration guards cannot drift;
- NetworkManager dispatcher integration that republishes valid or fail-closed state on relevant `eth0` events;
- creation/ownership of `/run/n3wfc4-trusted-lan`;
- read-only **directory** bind into Manager at `/run/n3w/trusted-product-lan`;
- registration-port INPUT guard for 47110/tcp, 47111/udp and 47112/tcp using the exact same trusted subnet;
- dedicated registration-bootstrap TLS certificate/key generation;
- secret mount ownership/permissions;
- listener/firewall/port inventory;
- exact-release seal coverage.

Likely files include `tools/n3w_broker_ingress_guard.py` or a factored shared host-network authority module, NetworkManager dispatcher/systemd assets, and both production compose variants. Exact implementation paths are fixed during R1 source work, but the security contract above is not optional.

These are source changes but not live T1 mutation until a separately authorized deployment gate.

## 23. Test plan

### A. Node idle

Prove:
- Wi-Fi connected + unregistered shows registration QR;
- no T1 discovery call occurs for at least an accelerated long idle interval;
- raw Setup Secret not in QR URL;
- raw pairing/hardware IDs not in QR URL;
- no generic ESPHome web server enabled.

### B. Scan trigger

Prove:
- GET page alone does not start transaction;
- valid start with current scan token starts exactly one discovery session;
- repeated start is idempotent;
- invalid/stale token does nothing.

### C. Discovery

Prove:
- zero candidates -> E01 -> same QR;
- one candidate -> WAIT_CONFIRM;
- multiple candidates -> no automatic selection;
- retry requires a new user/browser action.

### D. Bootstrap TLS

Prove:
- exact certificate fingerprint required;
- fingerprint mismatch sends no Setup Secret;
- secret absent from logs/results;
- source IP captured by T1;
- no operator peer_ip needed.

### E. Trusted product LAN admission

Prove with shared contract vectors against the KF-097 decision semantics:
- only NetworkManager current `eth0` unique IPv4 subnet is trusted;
- host publisher emits versioned state by atomic replacement and emits `available=false` for zero/ambiguous/disconnected/invalid state;
- Manager has only a read-only directory mount and no NetworkManager/D-Bus/control capability;
- Manager rejects missing/malformed/wrong-schema/wrong-interface/unavailable state;
- Manager re-reads state and does not cache predecessor subnet across requests;
- generic RFC1918 address outside the exact subnet is rejected;
- loopback rejected for product first registration;
- link-local rejected;
- IPv6 rejected in V1;
- Docker/VPN/other interface source rejected even when privately addressed;
- host INPUT guard rejects non-trusted sources for 47110/47111/47112;
- 47111 emits no response outside the trusted subnet;
- mDNS registration advertisement is scoped to `eth0`;
- DHCP/subnet change republishes authority without static customer CIDR;
- 47110/47111/47112 application checks and host guard consume the same authority contract;
- raw customer CIDR does not enter public evidence.

### F. Durable attempt ledger / restart-before-hello

Prove:
- 47110 cannot return `accepted=true` before durable `ACTIVE` insert commits;
- ledger contains pairing ID + hardware hash + timestamps/state only and no Setup Secret/source IP/scan token;
- restart after 47110 acceptance but before `/hello` converts old `ACTIVE` row to terminal;
- same old pairing ID receives terminal `replay_detected` or `expired`, never a fresh deadline;
- bootstrap terminal result invokes the existing durable ADR-0008 pairing-ID renewal primitive;
- fresh pairing ID is durably committed before the next 47110 attempt;
- same-process exact duplicate preserves the original deadline;
- `ACTIVE` ledger row without matching RAM intent fails closed and cannot be reconstructed with a fresh deadline;
- terminal rows remain replay tombstones.

### G. Identity-bound window

Prove:
- a trusted-product-LAN client may initiate 47110 without QR possession or scan-token proof;
- the normal phone flow still uses node QR + browser confirmation;
- wrong hardware rejected before DB write once an intent is active;
- wrong pairing ID rejected before DB write;
- wrong source IP rejected before DB write;
- source IP must still belong to current trusted product subnet on each 47112 request;
- exact duplicate is safe/idempotent;
- second competing node receives busy;
- 47112 is closed while idle and closes on Manager COMMIT or canonical deadline expiry.

### H. Deadline and restart

Accelerated-clock tests prove one shared deadline.

Production constants prove:

```text
FIRST_REGISTRATION_TTL_SECONDS=1800
```

Prove:
- pre-deadline browser/protocol/pairing failure does not close 47112 or refresh the deadline;
- success closes immediately;
- expiry closes at the exact shared deadline;
- Manager restart fail-closes the old transaction;
- old pairing ID cannot resume after Manager restart;
- next attempt uses a new pairing ID and a fresh full 1800-second deadline;
- no first-registration 120/600-second hidden limit remains.

Repair TTL remains <=120.

### I. Pairing security

Reuse current vectors/tests to prove:
- Setup Secret proof remains HMAC;
- HKDF bootstrap remains;
- encrypted credential bundle remains;
- final delivery digest ACK remains commit authority;
- replay tombstones remain.

### J. LCD

Golden/source tests cover every state/error string and ensure all glyphs exist.

### K. End-to-end simulated browser

A phone-like HTTP client:
1. opens node page;
2. starts scan session;
3. receives one/multiple T1 candidates;
4. confirms;
5. proves T1 47112 transition closed -> open -> closed;
6. proves Manager COMMIT;
7. proves browser never handles Setup Secret.

### L. Physical acceptance

Physical Board/T1 acceptance is a later separately authorized gate.

Mandatory normal flow:
- phone camera scan;
- browser confirmation;
- LCD feedback;
- no terminal secret paste.

## 24. Implementation order

Recommended staged source implementation:

```text
R1  trusted-product-LAN authority + passive discovery/bootstrap skeleton
R2  durable first-registration attempt ledger + restart tombstone tests
R3  identity-bound 47112 window + unified 1800 s deadline
R4  node local registration portal + QR
R5  scan-triggered discovery + multi-T1 selection
R6  node->T1 TLS bootstrap + terminal-bootstrap renewal + SimplePairingClient refactor
R7  LCD state/error integration
R8  full simulated end-to-end + regression / safety
R9  exact artifact build and independent source review
R10 separately authorized physical acceptance
```

Do not combine physical mutation with R1-R8.

## 25. Explicit non-goals

```text
DEDICATED_MOBILE_APP=false
HA_BACKEND_USER_FLOW=false
MANUAL_IP_INPUT=false
MANUAL_SECRET_COPY=false
IDLE_NODE_DISCOVERY=false
AUTO_SELECT_MULTIPLE_T1=false
NEW_RETIREMENT_DEVELOPMENT=false
WHOLE_NVS_RESET=false
BOARD_FLASH_IN_THIS_GATE=false
T1_LIVE_DEPLOYMENT_IN_THIS_GATE=false
```

## 26. Design closure

```text
SOURCE_DESIGN_RESULT=CLOSED_REPAIRED_READY_FOR_FOCUSED_CLOSURE_REVIEW

UI_TERM=联机注册
QR_VISIBLE_AFTER_WIFI_WHILE_UNREGISTERED=true
SCAN_TRIGGERS_DISCOVERY=true
CONFIRM_TRIGGERS_NORMAL_PRODUCT_TRANSACTION=true

T1_FIRST_REGISTRATION_AUTHORITY=NETWORKMANAGER_ETH0_UNIQUE_IPV4_SUBNET
TRUSTED_PRODUCT_LAN_INTERFACE=eth0
TRUSTED_LAN_AUTHORITY_TRANSPORT=HOST_ATOMIC_STATE_FILE_DIRECTORY_BIND
HOST_TRUSTED_LAN_RUNTIME_DIR=/run/n3wfc4-trusted-lan
MANAGER_TRUSTED_LAN_STATE_FILE=/run/n3w/trusted-product-lan/state.json
MANAGER_NETWORKMANAGER_CONTROL_ACCESS=false
REGISTRATION_INGRESS_HOST_GUARD=true
TRUSTED_PRODUCT_LAN_ZERO_OR_AMBIGUOUS=FAIL_CLOSED
GENERIC_RFC1918_OR_IS_LOCAL_SOURCE_FALLBACK=false
IPV6_FIRST_REGISTRATION_AUTHORIZED=false
LOOPBACK_FIRST_REGISTRATION_AUTHORIZED=false
QR_POSSESSION_REQUIRED_FOR_T1_AUTHORIZATION=false
TRUSTED_LAN_DIRECT_47110_INITIATION_ALLOWED=true

DURABLE_FIRST_REGISTRATION_ATTEMPT_LEDGER=true
ATTEMPT_LEDGER_SETUP_SECRET_PERSISTENCE=false
ACTIVE_ATTEMPT_COMMITTED_BEFORE_ACCEPTED_RESPONSE=true
STARTUP_TERMINALIZES_PREDECESSOR_ACTIVE_ATTEMPTS=true
RESTART_PRE_HELLO_PAIRING_ID_TOMBSTONED=true
TERMINAL_BOOTSTRAP_RESULT_USES_ADR0008_RENEWAL=true

T1_47110_BOOTSTRAP_ALWAYS_ON=true
T1_47111_DISCOVERY_ALWAYS_ON=true
T1_47112_PAIRING_IDLE_CLOSED=true

SETUP_SECRET_PHONE_EXPOSURE=false
SETUP_SECRET_MANUAL_COPY=false
SETUP_SECRET_NODE_TO_T1_TLS=true

FIRST_REGISTRATION_TTL_SECONDS=1800
FIRST_REGISTRATION_TTL_SCOPE=PER_TRANSACTION
MAX_CONCURRENT_FIRST_REGISTRATIONS_V1=1
NORMAL_PRIVILEGED_WINDOW_CLOSE_CONDITIONS=MANAGER_COMMIT_OR_DEADLINE
PREDEADLINE_ERROR_CLOSES_PRIVILEGED_WINDOW=false
MANAGER_RESTART_FAIL_CLOSED=true
MANAGER_RESTART_OLD_PAIRING_ID_TERMINAL=true
MANAGER_RESTART_REQUIRES_NEW_PAIRING_ID=true
MANAGER_RESTART_NEW_TRANSACTION_GETS_FRESH_1800S=true
UNUSED_TTL_CARRIED_FORWARD=false
NEXT_NODE_REQUIRES_NEW_CONFIRMATION=true
NEXT_NODE_GETS_FRESH_1800S_DEADLINE=true
REPAIR_TTL_UNCHANGED=true

LCD_PRIMARY_FEEDBACK=true
NODE_RETIREMENT_NEW_DEVELOPMENT=DEFERRED

SOURCE_MUTATION=false
LIVE_MUTATION=false
MERGE=false
```

Proposed next gate:

```text
N3W_SCAN_TRIGGERED_FIRST_PAIRING_SOURCE_DESIGN_REPAIR_R2_FOCUSED_CLOSURE_REVIEW_20261026_01
```

The focused closure review must independently verify:
- product trusted-LAN admission is exactly NetworkManager current `eth0` unique IPv4 subnet and cannot fall back to broad `is_local_source()`;
- the host publishes that authority atomically into a dedicated runtime directory, Manager reads it through a read-only directory bind, and no extra NetworkManager/D-Bus/control privilege is added to the container;
- fail-closed host publication and registration-port ingress rules cannot leave a predecessor valid subnet authoritative after normal NetworkManager state transitions;
- zero/ambiguous subnet, loopback, link-local, IPv6, Docker/VPN/other private networks are fail-closed for product first registration;
- QR possession/scan token/browser confirmation remain UX controls, not T1 authorization credentials;
- the normal node flow still performs pre-body TLS fingerprint matching before emitting Setup Secret bytes;
- 47110 durable `ACTIVE` attempt commit happens before `accepted=true`;
- the ledger stores no Setup Secret and closes restart-before-`/hello` replay;
- terminal bootstrap `expired/replay_detected` drives the same ADR-0008 durable pairing-ID renewal primitive;
- identity/source/current-subnet binding occurs before DB mutation on 47112;
- Manager COMMIT and canonical deadline expiry are the only normal-uptime privileged-window close conditions;
- pre-deadline failure does not refresh or replace the transaction;
- Manager restart is fail-closed, old pairing ID is terminal, and the next attempt uses a new pairing ID plus a fresh full 1800-second deadline;
- Setup Secret retained-buffer zeroization wording is implementable and does not make impossible claims about every immutable runtime copy;
- any current regression gate that still assumes idle UDP47111=0 is retargeted during implementation;
- no new false-PASS path was introduced by the R2 repair.
