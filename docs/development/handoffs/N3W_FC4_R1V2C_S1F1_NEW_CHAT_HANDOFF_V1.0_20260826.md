# N3-W / FC4 R1-V2C-S1-F1 New-Chat Handoff V1.0

- Date: 2026-08-26
- Repository: `chrenguo-stack/HomeAssistant`
- Frozen current-main: `1f80d54ff5f84056e0559a7d8cc80427c5e0bb14`
- Frozen tree: `f3b8095c62e8a4838eb1b614f05c932f54f5226d`
- Current stage: **R1-V2C-S1-F1 read-only classification complete**
- Next objective: **recover exact runtime authority → one minimal runtime-binding successor → Spare-T1 current-main convergence → three-board FC4**

> Public-safe handoff. Private host addresses, local filesystem paths, credentials, Setup Secrets, private keys, raw hardware identities, and private evidence bodies are intentionally omitted.

## 1. Execution model: high-level model reasoning + Codex low-level execution

Continue using the proven split:

```text
high-level model reasoning
+
Codex low-level execution
```

### High-level model responsibilities

The high-level model owns:

- architecture and product-route decisions;
- exact source/image/runtime authority;
- gate and authorization boundaries;
- failure classification;
- minimal correction scope;
- PASS / FAIL / STOP interpretation of Codex closures;
- detection of scope drift and over-engineering;
- deciding when source changes are actually justified.

It must not turn one-time evidence artifacts, temporary tags, helper scripts, or debugging mechanisms into product architecture.

### Codex responsibilities

Codex executes the exact bounded workflow supplied by the high-level model:

- Git / Docker / SSH / Compose / shell / test commands;
- read-only preflight;
- authorized mutation only after the correct claim boundary;
- evidence capture;
- structured closure;
- fail-closed stop at the first substantive mismatch.

Codex must not independently broaden scope, replay consumed authorization, rotate credentials/keys, rewrite databases, modify product source, or access boards unless the current authorization explicitly permits it.

### Standard interaction loop

```text
high-level model: analyze / gate / scope
→ user: explicitly approves mutation authorization when required
→ Codex: exact execution + closure
→ high-level model: audits closure and selects the next route
```

Read-only analysis does not consume live/physical authorization.

## 2. Current product route

```text
N3-W source convergence
→ Spare-T1 current-main convergence
→ FC4 three-board final physical acceptance
→ N3-W product closure
→ N3-L
→ later control-node work
```

Current N3-W architecture remains:

```text
Direct MQTT
+
authenticated ESP-NOW Relay
+
Manager canonical dedup
```

Do not start N3-L, control-node work, new protocols, or new acceptance frameworks before N3-W closure.

## 3. Exact source and candidate authority

```text
MAIN=1f80d54ff5f84056e0559a7d8cc80427c5e0bb14
TREE=f3b8095c62e8a4838eb1b614f05c932f54f5226d
```

Native ARM64 candidate:

```text
IMAGE_ID=sha256:de19ff39546b1958344790aabe1d1af569c69c64818b7e068f6936f11b1ae8bd
OS=linux
ARCH=arm64
VERSION=0.4.99
UID=999
GID=999
```

The candidate identity, labels, architecture, entrypoint, and UID/GID binding passed on Spare T1.

No source/image rebuild is currently justified.

## 4. V2B local cross-architecture route

The local x86_64→ARM64 legacy-builder path failed after the real build command was issued and the authorization was consumed.

The failure did not prove a source or Dockerfile defect. Native ARM64 build on Spare T1 later passed.

Therefore:

```text
LOCAL_X86_64_TO_ARM64_BUILD_ROUTE=ABANDONED_FOR_FC4_ACCEPTANCE
```

Do not return to buildx installation, binfmt repair, Colima repair, or Mac/QEMU debugging unless a new demonstrated blocker requires it.

## 5. V2N native ARM64 result

```text
NATIVE_ARM64_BUILD=PASS
CANDIDATE_LABEL_BINDING=PASS
CANDIDATE_UID_GID_BINDING=PASS
RESOLVER_PROBE_RESULT=PASS
SUCCESSOR_COMPOSE_VALIDATION=PASS
DEPLOYMENT_GATE_RESULT=PASS
```

This is the current candidate authority.

## 6. First V2C live convergence

Broker convergence passed, including LAN and loopback TLS 8883 publication.

The current-main Manager candidate entered a restart loop and the session rolled back successfully to the prior stable Manager/Broker/Home Assistant runtime.

No credential/key rotation, direct database mutation, DynSec mutation, pairing reset/replay, Home Assistant mutation, or board access occurred.

## 7. Restart-loop eliminations

Read-only private-state audit:

```text
OWNER_BINDING=PASS_UID_GID_999
MODE_BINDING=PASS_600_700
PATH_TYPE_BINDING=PASS
```

Do not apply guessed recursive ownership/permission changes.

Read-only cutover chronology:

```text
old Manager exited before candidate start
old-manager/candidate overlap not proven
pairing-port collision not proven
cutover order classified correct
```

## 8. D1 one-shot diagnostic

D1 used `restart=no`, exactly one candidate start, old Manager stopped, and pairing ports proven free before start.

Captured startup failure:

```text
GH_MQTT_CA_FILE is required when GH_MQTT_TLS=true
```

Classification:

```text
MQTT_CONFIGURATION_FAILURE
ROOT_CAUSE_CONFIDENCE=HIGH
```

This was a successor runtime binding omission, not a product image defect.

## 9. S1 MQTT CA binding correction

S1 corrected only Manager→Broker MQTT CA binding.

Proof:

```text
TLS_CHAIN_VERIFY=PASS
TLS_IDENTITY_VERIFY=PASS
CA_CONFIGURATION_ERROR_ABSENT=true
candidate one-shot 60s stable=true
S1_CA_ONLY_DIFF_BINDING=PASS
```

The verified CA correction must be preserved in the next successor runtime.

S1 then exposed two remaining blockers:

```text
MQTT_CONNECTIVITY=FAIL_NOT_AUTHORIZED
PAIRING_SOCKET_HEALTH=FAIL_ABSENT
```

S1 rolled back successfully.

## 10. Latest authority: R1-V2C-S1-F1

### MQTT classification

```text
MQTT_FAILURE_LOG_RECOVERED=true
MQTT_REASON_CODE=CONNACK_NOT_AUTHORIZED
MQTT_REASON_TEXT=Not authorized
BROKER_REJECTED_CONNECTION=true
```

Candidate metadata:

```text
CANDIDATE_MQTT_CLIENT_ID=greenhouse-manager
CANDIDATE_MQTT_USERNAME_CONFIGURED=false
CANDIDATE_MQTT_PASSWORD_CONFIGURED=true
```

Broker-side Manager identity existed, was enabled, role-bound, and connect-authorized. Candidate password material matched the authorized Manager identity, but the identity binding did not.

Final classification:

```text
MQTT_IDENTITY_BINDING=CLIENT_ID_MISMATCH
MQTT_FAILURE_CLASS=MQTT_AUTH_BINDING_ALREADY_WRONG_IN_BASE_SUCCESSOR
```

Do not guess a new username/client-id/password. Recover the exact safe Broker/DynSec Manager identity authority read-only before correction.

### Product-pairing selector classification

```text
GH_N3W_RUNTIME_ENABLED=false
GH_N3W_PRODUCT_PAIRING_ENABLED=false
EXPECTED_MANAGER_SERVICE=BASE_MANAGER
PAIRING_SOCKET_EXPECTED=false
PAIRING_SOCKET_ABSENCE_CLASS=EXPECTED_PRODUCT_PAIRING_DISABLED
PAIRING_FAILURE_CLASS=PRODUCT_PAIRING_DISABLED_IN_SUCCESSOR_RUNTIME
```

Therefore pairing-socket absence was expected for the runtime actually selected; it was not evidence of a socket implementation defect.

## 11. Current live state

The failed successor sessions rolled back to the prior stable runtime.

At the handoff boundary:

```text
old Manager 0.4.98 = running
Broker = running
Home Assistant = running
Manager restart loop = false
```

A new session must still perform a fresh read-only rebind before relying on these facts.

## 12. Consumed authorizations — never replay

```text
R1-V2B-CANDIDATE-IMAGE-MATERIALIZATION-AND-RESOLVER-PRECLAIM-20260826-01
R1-V2N-SPARE-T1-NATIVE-ARM64-CANDIDATE-BUILD-AND-PRELIVE-VALIDATION-20260826-01
R1-V2C-SPARE-T1-CURRENT-MAIN-LIVE-CONVERGENCE-20260826-01
R1-V2C-D1-SPARE-T1-CANDIDATE-ONE-SHOT-STARTUP-DIAGNOSTIC-20260826-01
R1-V2C-S1-SPARE-T1-MQTT-CA-BINDING-AND-CURRENT-MAIN-CONVERGENCE-20260826-01
```

Earlier local tooling recovery authorizations are also historical/consumed and are outside the current product route.

## 13. Next session: compact read-only authority recovery first

Do **not** begin with a new live mutation authorization.

First recover only:

1. exact-main / tree / candidate image binding;
2. current rollback runtime state;
3. Broker/DynSec exact safe Manager identity authority;
4. old-Manager identity binding;
5. base-successor identity source and exact mismatch field;
6. final N3-W product runtime environment/path authority;
7. the already-proven MQTT CA binding.

For final product runtime, recover the authority for these roles without exposing secrets:

```text
GH_N3W_RUNTIME_ENABLED
GH_N3W_PRODUCT_PAIRING_ENABLED
GH_N3W_PAIRING_MANAGER_ID
GH_N3W_PAIRING_BIND_HOST
GH_N3W_PAIRING_ADVERTISED_HOST
GH_N3W_PAIRING_HTTP_PORT
GH_N3W_PAIRING_UDP_PORT
GH_N3W_PROVISIONING_USERNAME
GH_N3W_PROVISIONING_PASSWORD_FILE
GH_N3W_PROVISIONING_CLIENT_ID
GH_N3W_NODE_BROKER_HOST
GH_N3W_NODE_BROKER_PORT
GH_N3W_NODE_BROKER_TLS_SERVER_NAME
GH_N3W_NODE_BROKER_CA_FILE
GH_N3W_PEER_TRUST_DB_PATH
GH_N3W_CREDENTIAL_LIFECYCLE_DB_PATH
GH_N3W_PAIRING_SOCKET_PATH
```

Return safe configured/path/equality metadata only; never output secret values.

## 14. Only after authority recovery: one minimal live successor

If the read-only authority recovery is complete, request one new unique authorization for the smallest runtime correction.

The successor may correct only:

```text
Manager MQTT identity binding
+
final N3-W runtime/product-pairing bindings
+
preserve the already-proven Manager MQTT CA binding
```

It must not modify:

```text
source
Dockerfile
candidate image
database contents
credential generation
application-key generation
SYSTEM_PEER_KEY
DynSec account/role/ACL
pairing state
Home Assistant
boards
```

Recommended validation order:

```text
claim-free exact rebind
→ minimal corrected successor + semantic diff allowlist
→ Broker precondition
→ stop old Manager and prove pairing ports free
→ candidate restart=no one-shot preflight
→ require MQTT_CONNECTIVITY=PASS
→ require PRODUCT_PAIRING_RUNTIME=ACTIVE
→ require PAIRING_SOCKET_HEALTH=PASS
→ live current-main Manager
→ 180s stability
→ STOP
```

If one-shot preflight fails, capture exact logs/inspect before rollback and stop. Do not try multiple guessed repairs under one authorization.

## 15. T1 convergence PASS criteria

At minimum:

```text
MANAGER_IMAGE_ID=sha256:de19ff39546b1958344790aabe1d1af569c69c64818b7e068f6936f11b1ae8bd
MANAGER_REVISION=1f80d54ff5f84056e0559a7d8cc80427c5e0bb14
MANAGER_VERSION=0.4.99
MANAGER_NETWORK_MODE=host
MANAGER_RESTART_LOOP=false
BROKER_RUNNING=true
BROKER_TLS_LAN_8883=PASS
BROKER_TLS_LOOPBACK_8883=PASS
MQTT_CONNECTIVITY=PASS
GH_N3W_RUNTIME_ENABLED=true
GH_N3W_PRODUCT_PAIRING_ENABLED=true
PAIRING_SOCKET_HEALTH=PASS
HA_RUNNING=true
MANAGER_RESTART_DELTA=0
BROKER_RESTART_DELTA=0
HA_RESTART_DELTA=0
CREDENTIAL_ROTATION=false
APPLICATION_KEY_ROTATION=false
SYSTEM_PEER_KEY_ROTATION=false
PAIRING_RESET=false
PAIRING_REPLAY=false
BOARD_ACCESS=false
```

Once T1 convergence passes, freeze T1 and move directly to three-board FC4.

## 16. Three-board FC4 objective

```text
FC4A A/B/C Direct baseline
FC4B B real Wi-Fi loss → Relay
FC4C B Wi-Fi recovery → Direct
FC4D late-add C without A/B repair/reflash
FC4E C real Wi-Fi loss → Relay
FC4F B/C simultaneous Relay
FC4G multi-Relay failover
FC4H A/B/C stable Direct recovery

FINAL=N3W_THREE_BOARD_FINAL_PRODUCT_E2E=PASS
```

Do not require three simultaneous USB serial connections as a product assumption; use wireless/runtime evidence and sequential board access where necessary.

## 17. Navigation constraints

Keep the route short:

```text
read-only authority recovery
→ one minimal runtime-binding successor
→ Spare-T1 current-main convergence
→ three-board FC4
```

Do not return to local cross-architecture build tooling, create a new generalized executor framework, or expand into deferred product lines.

## 18. Suggested new-chat opening

```text
Read docs/development/handoffs/N3W_FC4_R1V2C_S1F1_NEW_CHAT_HANDOFF_V1.0_20260826.md and continue the N3-W / FC4 Final Physical Acceptance.

Continue using “high-level model reasoning + Codex low-level execution”.

Start only with compact read-only authority recovery for:
1. exact-main/candidate/post-rollback runtime binding;
2. exact Broker/DynSec Manager MQTT identity authority;
3. exact final N3-W product-runtime environment/path authority;
4. preservation of the already-proven MQTT CA binding.

Do not perform live mutation or board access yet. After read-only authority recovery, plan one minimal runtime-binding successor to close Spare-T1 current-main convergence, then proceed directly to three-board FC4.
```
