# N3-W / FC4 Board C First Registration TLS Server-Name Root Cause Closeout and Firmware Repair Handoff

- Version: `V1.0`
- Date: `2026-08-30`
- Repository: `chrenguo-stack/HomeAssistant`
- Nature: documentation-only, public-safe closeout / successor handoff
- Product mutation in this document: `false`
- Board access authorized by this document: `false`

---

## 1. North Star and route

```text
NORTH_STAR=FC4_FINAL_PHYSICAL_ACCEPTANCE
CURRENT_ROUTE_NODE=BOARD_C_FIRST_REGISTRATION
ACTIVE_DETOUR=BOARD_C_TLS_SERVER_NAME_FIRMWARE_REPAIR
RETURN_TO_ROUTE=BOARD_C_FIRST_REGISTRATION_RUNTIME_ACCEPTANCE
NEW_BRANCH_ALLOWED=false
```

The current route remains the original FC4 Final Physical Acceptance route. The TLS repair is a bounded detour created only because a real product blocker has now been proven. It is not a new product branch or architecture change.

---

## 2. Source authority

Frozen FC4 product source remains:

```text
FROZEN_PRODUCT_SOURCE_HEAD=1f80d54ff5f84056e0559a7d8cc80427c5e0bb14
FROZEN_PRODUCT_SOURCE_TREE=f3b8095c62e8a4838eb1b614f05c932f54f5226d
```

Board-C P9 guarded source remains:

```text
GUARDED_HEAD=867c84d9d90f9c56d2446d9aa1a13c31ac593480
GUARDED_TREE=de670366fe452637e802fb261929613047805964
```

The current documentation branch is based on the guarded source and must remain documentation-only until a separately authorized firmware source-repair boundary is created.

The original dirty development worktree must not be reset, stashed, discarded, or reused as the exact repair authority.

---

## 3. Predecessor closeout documents

Read these before any successor work:

1. `docs/development/N3W_FC4_BoardC_SetupSecret_Recapture_Closeout_and_FreshPairingRebind_Handoff_V1.0_20260829.md`
2. `docs/development/N3W_FC4_BoardC_P9_Executor_Oracle_Incident_Supplement_20260829.md`
3. `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`

This document supersedes their route-state snapshots where the later first-registration/TLS evidence is more recent. Historical evidence and consumed authorizations in predecessor documents remain immutable.

---

## 4. Board C first-registration durable commit

After one authorized UDS Setup Secret import, Board C completed the normal automatic first-registration transaction.

Frozen durable result:

```text
CURRENT_REGISTRATION_STATE=APPROVED
CURRENT_NODE_ID_PRESENT=true
CURRENT_REPAIR_AUTHORIZED=false
CURRENT_HARDWARE_RETIRED=false
CURRENT_APPROVAL_EVENT_COUNT=1

CREDENTIAL_ASSIGNMENT_COUNT=1
CREDENTIAL_STATE=ACTIVE
CREDENTIAL_ACTIVE_GENERATION=1
CREDENTIAL_PENDING_GENERATION_PRESENT=false
CREDENTIAL_PAIRING_MATCH=true
CREDENTIAL_NODE_MATCH=true

APPLICATION_KEY_NODE_ACTIVE=true
APPLICATION_KEY_ACTIVE_EPOCH_COUNT=1
APPLICATION_KEY_STAGED_EPOCH_COUNT=0
APPLICATION_KEY_GRACE_EPOCH_COUNT=0

DYNSEC_EXACT_CLIENT_COUNT=1
DYNSEC_EXACT_ROLE_EXISTS=true
DYNSEC_EXACT_ROLE_BOUND=true

REGISTRATION_COMMIT_PROVEN=true
CREDENTIAL_COMMIT_PROVEN=true
APPLICATION_KEY_COMMIT_PROVEN=true
DYNSEC_IDENTITY_PRESENT=true
FIRST_REGISTRATION_COMMIT_PROVEN=true
PRODUCT_BLOCKER_PROVEN=false
```

The first-registration identity/credential/application-key/DynSec transaction is therefore already committed and must not be repeated as part of the TLS repair.

Explicitly forbidden as a TLS workaround:

```text
NO_SETUP_SECRET_REIMPORT
NO_REPAIR_PAIRING
NO_NEW_NODE_ID_ALLOCATION
NO_DYNSEC_REPROVISION
NO_CREDENTIAL_GENERATION_BUMP
NO_APPLICATION_KEY_REPROVISION
NO_NVS_ERASE
```

---

## 5. Runtime route audit

After repeated host-side oracle problems, the mandatory route audit passed and reset the failure fuse.

Frozen route result:

```text
REGISTRATION_COMMIT_PROVEN=true
CREDENTIAL_COMMIT_PROVEN=true
APPLICATION_KEY_COMMIT_PROVEN=true
DYNSEC_IDENTITY_PRESENT=true
BROKER_8883_TLS_CONFIG_COMPLETE=true
MQTT_PROTOCOL_BOUNDARY_STILL_PRESENT=true
BOARD_C_MQTT_PROTOCOL_BOUNDARY_ROUTE_AUDIT=PASS
ACTIVE_FAILURE_STREAK_RESET=true
ROUTE_AUDIT_REQUIRED=false
PRODUCT_BLOCKER_PROVEN=false
```

This proved there was no route drift back into registration, credential, application-key, DynSec or Broker-listener recovery.

---

## 6. Host-side MQTT/TLS boundary evidence

Board C repeatedly opened TCP connections to the Broker 8883 listener, but the Broker never established the current Board C MQTT identity.

The final safe classification was:

```text
BOARD_C_BROKER_TCP_ACTIVITY_PRESENT=true
BOARD_C_MQTT_CLIENT_CONNECTED=false
MQTT_CURRENT_NODE_ID_VISIBLE_TO_BROKER=false
```

The exact current-node log correction also invalidated an earlier correlation assumption: protocol-error lines associated only by source-IP/event grouping were not evidence that the current Board C NODE_ID had been parsed by the Broker.

Therefore the primary failure boundary remained before successful MQTT client establishment.

---

## 7. TLS endpoint and certificate authority facts

The final read-only T1 reconciliation proved all of the following simultaneously:

```text
NODE_BROKER_HOST_KIND=IP
NODE_TLS_SERVER_NAME_KIND=DNS
NODE_BROKER_HOST_EQUALS_TLS_SERVER_NAME=false

BROKER_CERTIFICATE_MATCHES_NODE_BROKER_HOST=false
BROKER_CERTIFICATE_MATCHES_TLS_SERVER_NAME=true
BROKER_CERTIFICATE_CA_VERIFY=true
BROKER_CERTIFICATE_CURRENTLY_TIME_VALID=true
```

This is an intentional and valid product topology:

```text
TCP_CONNECT_TARGET=broker_host
TLS_EXPECTED_SERVER_NAME=broker_tls_server_name
```

The two authorities are not required to be identical.

---

## 8. Frozen firmware source fact

The guarded/frozen `SimpleProductComponent::configure_mqtt_()` configures the MQTT client with:

- broker address from `broker_state_.broker_host`
- broker port
- username
- password
- client ID
- CA certificate

but does not consume the already provisioned/persisted `broker_state_.broker_tls_server_name`.

Frozen result:

```text
FIRMWARE_MQTT_SETS_BROKER_ADDRESS=true
FIRMWARE_MQTT_SETS_BROKER_PORT=true
FIRMWARE_MQTT_SETS_CA_CERTIFICATE=true
FIRMWARE_MQTT_SETS_USERNAME=true
FIRMWARE_MQTT_SETS_PASSWORD=true
FIRMWARE_MQTT_SETS_CLIENT_ID=true
FIRMWARE_MQTT_CONSUMES_TLS_SERVER_NAME=false
```

This is a product-source defect, not a Broker/DynSec/Pairing configuration defect.

---

## 9. Why Phase 4 Board A/B did not expose the defect

The previous clean isolated two-board E2E was real and remains valid for the topology it tested. Both boards completed independent first-use pairing and Direct MQTT telemetry.

However the isolated TLS harness intentionally used the same host IP for all three authorities:

```text
broker_host=host_ip
broker_tls_server_name=host_ip
certificate SAN=IP:host_ip
```

Therefore the firmware could ignore the independent TLS server-name field and still pass TLS validation.

The missing regression dimension was:

```text
broker_host != broker_tls_server_name
```

Specifically, the final-product case now proven on Board C is:

```text
broker_host=IP
broker_tls_server_name=DNS
certificate SAN=DNS only
```

The historical A/B PASS is therefore not contradicted; the old matrix simply did not activate the hidden defect.

---

## 10. One-shot Board C serial diagnostic

Authorization:

```text
AUTHORIZATION=R6-BOARD-C-READ-ONLY-SERIAL-TLS-DIAGNOSTIC-20260830-01
SCOPE=BOARD_C_SINGLE_OPEN_READ_ONLY_SERIAL_TLS_MQTT_DIAGNOSTIC_ONLY
ONE_SHOT=true
REPLAY_PERMITTED=false
```

The authorization was claimed and consumed exactly once.

Frozen execution facts:

```text
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
REPLAY_PERMITTED=false
SERIAL_OPEN_ATTEMPT_COUNT=1
SERIAL_OPEN_COUNT=1
SERIAL_CLOSE_COUNT=1
SERIAL_OPEN_EXACTLY_ONCE=true
SERIAL_WRITE_BYTE_COUNT=0
MODEM_CONTROL_IOCTL_EXECUTED=false
RESET_EXECUTED=false
BOOT_BUTTON_EXECUTED=false
FLASH_EXECUTED=false
FLASH_READ_EXECUTED=false
NVS_ERASE_EXECUTED=false
NVS_READ_EXECUTED=false
REPROVISION_EXECUTED=false
PAIRING_MUTATION_EXECUTED=false
MQTT_MUTATION_EXECUTED=false
BROKER_MUTATION_EXECUTED=false
MANAGER_MUTATION_EXECUTED=false
LIVE_PRODUCT_MUTATION=false
```

Raw serial evidence was retained only in a mode-0600 private evidence boundary and was not published.

This authorization is permanently consumed and must never be replayed.

---

## 11. Board-side TLS evidence

The one-shot serial observation directly proved the client-side TLS failure:

```text
SERIAL_ESP_TLS_LINE_COUNT=12
SERIAL_MBEDTLS_LINE_COUNT=4
SERIAL_TLS_HANDSHAKE_FAILURE_LINE_COUNT=4
SERIAL_CERTIFICATE_VERIFY_FAILURE_LINE_COUNT=8
SERIAL_MBEDTLS_HANDSHAKE_2700_COUNT=4
SERIAL_MBEDTLS_HANDSHAKE_CODE_1=0X2700
```

The safe diagnostic classified:

```text
BOARD_C_SERIAL_TLS_DIAGNOSTIC_STATE=TLS_CERTIFICATE_NAME_OR_VERIFY_FAILURE_OBSERVED
```

A later host-only reconciliation reused the already captured private trace and did not reopen the serial port.

---

## 12. Final root-cause closure

The final reconciliation combined:

1. correct independent Manager delivery of connection address and TLS server name;
2. valid Broker CA chain and certificate lifetime;
3. certificate identity matching the DNS TLS name but not the IP connect target;
4. frozen firmware failure to consume `broker_tls_server_name`;
5. Board-side mbedTLS certificate-verification handshake failure;
6. no successful current Board C MQTT client establishment.

Final terminal result:

```text
TLS_SERVER_NAME_BINDING_ROOT_CAUSE=PROVEN
ROOT_CAUSE=FIRMWARE_IGNORES_PROVISIONED_BROKER_TLS_SERVER_NAME
PRODUCT_BLOCKER_PROVEN=true
FAIL_CLASS=PRODUCT_BLOCKER

BOARD_C_REPAIR_REQUIRED=true
BROKER_REPAIR_REQUIRED=false
MANAGER_REPAIR_REQUIRED=false
DYNSEC_REPAIR_REQUIRED=false
PAIRING_REPAIR_REQUIRED=false
```

This is the authoritative root cause for the current FC4 Board C runtime blocker.

---

## 13. Correct repair design boundary

The repair must preserve the intended architecture:

```text
TCP_CONNECT_TARGET=broker_host
TLS_EXPECTED_SERVER_NAME=broker_tls_server_name
```

The minimal design target is to carry the persisted TLS server name through the ESPHome MQTT ESP32 backend into the exact ESP-MQTT/ESP-IDF server-certificate verification-name field, such as `broker.verification.common_name` where that is the exact-version supported API.

The next source-review session must first verify the exact vendored/generated ESPHome and ESP-IDF interfaces before editing code.

Forbidden workarounds:

```text
DO_NOT_SET_SKIP_CERT_CN_CHECK=true
DO_NOT_DISABLE_SERVER_IDENTITY_VALIDATION
DO_NOT_ADD_CURRENT_SITE_IP_TO_CERTIFICATE_AS_A_WORKAROUND
DO_NOT_FORCE_TCP_BROKER_HOST_TO_EQUAL_TLS_DNS_NAME_AS_A_WORKAROUND
DO_NOT_REPAIR_BROKER_OR_DYNSEC_TO_HIDE_FIRMWARE_DEFECT
```

---

## 14. Mandatory regression matrix

The repair is not acceptable with only a source substring test. At minimum, regression coverage must prove:

| Case | TCP broker host | TLS expected name | Certificate identity | Expected |
|---|---|---|---|---|
| A | DNS-A | DNS-A | DNS-A | PASS |
| B | IP | DNS-A | DNS-A only | PASS |
| C | IP | DNS-B | DNS-A only | FAIL |
| D | IP | DNS-A | correct name, wrong CA | FAIL |
| E | IP | DNS-A | correct name, invalid time | FAIL |

Case B is the critical regression that the former isolated A/B physical E2E did not cover.

Additionally prove the whole state path:

```text
credential/provisioning bundle
-> persisted broker state
-> load_runtime_state_()
-> configure_mqtt_()
-> ESPHome MQTT backend
-> ESP-MQTT / ESP-IDF verification-name field
```

No field may merely exist in the schema while remaining unused at runtime.

---

## 15. Oracle correction from this diagnostic sequence

An earlier serial classifier emitted:

```text
SERIAL_MQTT_CONNECTED_LINE_COUNT=4
```

That result is invalid because the matcher used the bare substring `connected`, which also matches `disconnected`.

The value must not be used as MQTT connection evidence.

Future classifiers must use mutually exclusive structured event matching, complete token/word boundaries, or exact event codes, and must contain a negative regression proving that `connected` cannot match `disconnected`.

---

## 16. Known Failures assignments

The central index has now assigned:

```text
KF-075 = PHYSICAL_HARNESS
         Board-C diagnostic executor authority/transport/oracle incidents

KF-076 = PRODUCT
         Board-C MQTT/TLS server-name binding defect

KF-077 = PHYSICAL_HARNESS
         connected/disconnected log-classifier false positive
```

`KF-076` remains `OPEN` until source repair, tests, exact build/CI and Board C physical runtime acceptance close the product defect.

`KF-077` remains `OPEN` until a machine regression for the matcher boundary is materialized.

---

## 17. Failure-fuse state

The mandatory route audit already passed before the final TLS evidence chain, and the subsequent correction/serial/reconciliation gates completed without a new consecutive executor/preclaim failure pair.

```text
CURRENT_EXECUTOR_FAILURE_STREAK=0
ROUTE_AUDIT_REQUIRED=false
```

If a future repair executor produces two consecutive executor/preclaim nonclosures, the mandatory route-audit rule in `KNOWN_FAILURES_AND_REGRESSION_GUARDS.md` applies before a third successor/preclaim.

---

## 18. Current non-mutation boundary

At this handoff:

```text
SOURCE_REPAIR_EXECUTED=false
BOARD_C_FIRMWARE_UPDATE_EXECUTED=false
BOARD_C_SERIAL_REOPENED=false
T1_RUNTIME_MUTATION_EXECUTED=false
BROKER_MUTATION_EXECUTED=false
MANAGER_MUTATION_EXECUTED=false
DYNSEC_MUTATION_EXECUTED=false
PAIRING_MUTATION_EXECUTED=false
```

No currently consumed physical authorization grants any of those actions.

---

## 19. Next source-repair authorization candidate

Candidate only; not granted by this document:

```text
AUTHORIZATION=R6-BOARD-C-TLS-SERVER-NAME-FIRMWARE-SOURCE-REPAIR-20260830-01
SCOPE=EXACT_GUARDED_SOURCE_TLS_SERVER_NAME_MINIMAL_REPAIR_TESTS_AND_KF_ONLY

AUTHORIZATION_GRANTED=false
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
```

This candidate is source/test/documentation only. It does not authorize Board C access, serial open, firmware flash, T1 runtime mutation, Broker mutation, Manager mutation, DynSec mutation, or pairing mutation.

A later firmware materialization/deployment and Board C physical acceptance must use a separate authorization after source/test/CI closure.

---

## 20. Required start sequence for the next conversation

The next conversation must begin read-only and must not immediately mutate source.

Required order:

1. re-read this document and `KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`;
2. rebind the guarded/frozen source authority and confirm no unexpected code drift;
3. read the exact ESPHome MQTT ESP32 backend and exact ESP-IDF/ESP-MQTT configuration surface used by the frozen build;
4. prove the minimal supported mechanism for independent TCP host and TLS expected server name;
5. design the smallest changed-file/hunk allowlist;
6. design focused source/unit/integration regressions including the IP-host/DNS-name/DNS-only-SAN case;
7. verify the current KF-076/KF-077 status and numbering;
8. only then decide whether to grant the source-repair authorization candidate.

Do not ask the operator to repeat Board C pairing, registration, Setup Secret capture or the consumed serial diagnostic.

---

## 21. Handoff terminal

```text
HANDOFF_VERSION=V1.0
HANDOFF_DATE=2026-08-30

NORTH_STAR=FC4_FINAL_PHYSICAL_ACCEPTANCE
CURRENT_ROUTE_NODE=BOARD_C_FIRST_REGISTRATION
ACTIVE_DETOUR=BOARD_C_TLS_SERVER_NAME_FIRMWARE_REPAIR
RETURN_TO_ROUTE=BOARD_C_FIRST_REGISTRATION_RUNTIME_ACCEPTANCE
NEW_BRANCH_ALLOWED=false

FIRST_REGISTRATION_COMMIT_PROVEN=true
TLS_SERVER_NAME_BINDING_ROOT_CAUSE=PROVEN
ROOT_CAUSE=FIRMWARE_IGNORES_PROVISIONED_BROKER_TLS_SERVER_NAME
PRODUCT_BLOCKER_PROVEN=true
FAIL_CLASS=PRODUCT_BLOCKER

BOARD_C_REPAIR_REQUIRED=true
BROKER_REPAIR_REQUIRED=false
MANAGER_REPAIR_REQUIRED=false
DYNSEC_REPAIR_REQUIRED=false
PAIRING_REPAIR_REQUIRED=false

CURRENT_EXECUTOR_FAILURE_STREAK=0
ROUTE_AUDIT_REQUIRED=false

NEXT_ROUTE_ACTION=BOARD_C_TLS_SERVER_NAME_FIRMWARE_REPAIR_DESIGN
SOURCE_MUTATION_AUTHORIZED=false
BOARD_ACCESS_AUTHORIZED=false
```

End of handoff.
