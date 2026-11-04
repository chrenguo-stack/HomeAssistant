# N3-W Pre-U1 normal product runtime acceptance — G0 read-only preflight closure

Date: 2026-11-04

## 0. Result

```text
GATE=N3W_PRE_U1_NORMAL_PRODUCT_RUNTIME_ACCEPTANCE_G0_READONLY_PREFLIGHT_20261104_01
RESULT=CLOSED_PASS
AUTHORIZATION=READONLY_G0
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
HOMEASSISTANT_MUTATION=false
PAIRING_MUTATION=false
UPDATER_APPLY=false
UPDATER_ROLLBACK=false
SERVICE_RESTART=false
MERGE=false
STOP=true
```

G0 is closed PASS. This closure does not authorize G1 or U1.

## 1. Fresh repository binding

```text
REPOSITORY=chrenguo-stack/HomeAssistant
MAIN=e0841a5a43fd5847d5c5c40ab1cece42faedf3c8
PR=774
PR_STATE=OPEN_DRAFT
PR_INPUT_HEAD=2799072be6ee505add2a74d9aa71551f7ae1010c
HANDOFF_RECORDED_HEAD=5fd7b24a3b655d49ff50738893a2bb84af73c3af
HEAD_DRIFT_COMMITS=5
PRODUCT_SOURCE_DRIFT=false
UPDATER_SOURCE_DRIFT=false
BASELINE_A_DRIFT=false
```

The five commits after the handoff head only advanced current-state/index documentation and added the G0 handoff. They did not change product source, updater source, or Baseline A.

Relevant CI on the fresh PR head completed successfully. Conditional image/build workflows that did not apply to the documentation-only delta were skipped rather than failed.

## 2. U0 / U1 authority

```text
U0_RESULT=CLOSED_PASS
U0_REOPEN=false
U1_MANAGER_A_TO_B_STATUS=SUSPENDED
U1_PLAN_PRESERVED=true
U1_LIVE_APPLY_AUTHORIZED=false
MANAGER_B_SOURCE_CREATED=false
```

Normal business-state growth remains allowed runtime drift and is not treated as U0 invalidation.

## 3. Fresh T1 host and product health

The operator executed the bounded read-only G0 capture against T1_B.

```text
HOST_ARCH=aarch64
SYSTEM_STATE=running
RELEVANT_FAILED_UNIT_COUNT=0

DOCKER_SERVICE=active
BROKER_ACTIVATION_SERVICE=active
SERVICES_ACTIVATION_SERVICE=active
REGISTRATION_INGRESS_GUARD=active
CERTIFICATE_LIFECYCLE_TIMER=active
CERTIFICATE_LIFECYCLE_SERVICE=inactive

PRODUCT_CONTAINER_COUNT=3
MANAGER_CONTAINER=running
HOMEASSISTANT_CONTAINER=running
BROKER_CONTAINER=running
```

The certificate lifecycle service is a oneshot service. Its inactive state with the timer active is the normal idle condition and is not an active mutation window.

Fresh running images:

```text
MANAGER_IMAGE=local/greenhouse-manager:fresh-b863ddd95909
HOMEASSISTANT_IMAGE=local/n3w-homeassistant:2026.10.0-0c73235a
BROKER_IMAGE=local/n3w-mosquitto:2.1.2-3184566d
```

Fresh listener contract:

```text
TCP_1883=LISTEN_LOOPBACK
TCP_8883=LISTEN_WILDCARD
TCP_8123=LISTEN
TCP_47110=1
UDP_47111=1
TCP_47112=0
```

## 4. Updater and hard-baseline proof

```text
UPDATER_REVIEWED_SOURCE_HEAD=4dd39befedce891bd2db3cc84c592d41f778bc51
UPDATER_ARTIFACT_ID=13261072174
UPDATER_PYZ_SHA256=54f2e6299fa8905d33033ea86b5d449f16ad4dcd6ae8c7a3e9d647d6001e22fa

UPDATER_STATUS=PASS
UPDATER_TRANSACTION_STATUS=COMMITTED
UPDATER_TRANSACTION_PHASE=COMMITTED
UPDATER_RECOVERY_REQUIRED=false
ACTIVE_UPDATER_MUTATION=false
```

All three component inspect operations returned PASS.

```text
MANAGER_PLATFORM=linux/arm64
HOMEASSISTANT_PLATFORM=linux/arm64
BROKER_PLATFORM=linux/arm64

MANAGER_RUNTIME_CONTRACT_SHA256=ad1d38f6191c0c00afcfbee3ca489d5f95a86fefcb17976c273597c04609d6e1
HOMEASSISTANT_RUNTIME_CONTRACT_SHA256=bc69586866551709110435ea25bfdff9d41bc8e366f6ace8d4b7bba3db5f6868
BROKER_RUNTIME_CONTRACT_SHA256=b4e002c7eb494812629b1a99d7e53b712d5f2239460c99334556976b6fdad492
```

Fresh baseline:

```text
FRESH_BASELINE_RC=0
FRESH_BASELINE_BYTES=2275
FRESH_BASELINE_SHA256=a791377083e76f765ddf978c09025674eda3586d33892e4b609a814706bdfbbc

U0_BASELINE_A_BYTES=2275
U0_BASELINE_A_SHA256=a791377083e76f765ddf978c09025674eda3586d33892e4b609a814706bdfbbc
FRESH_BASELINE_BYTE_IDENTITY_WITH_U0=true
FRESH_BASELINE_COMPATIBLE_WITH_U0=true
```

No hard-authority drift is present.

## 5. Pairing / registration mutation state

```text
PAIRING_WINDOW_STATE=CLOSED
PAIRING_CLOSE_REASON=committed
PAIRING_CONTROL_ACCEPTED=true
TCP_47112=0
ACTIVE_PAIRING_MUTATION=false

CURRENT_REGISTERED_NODE_COUNT=1
ACTIVE_NODE_ID_LEASE_COUNT=1
ACTIVE_CREDENTIAL_ASSIGNMENT_COUNT=1
PAIRING_SESSION_COUNT=1
UNRESOLVED_FIRST_REGISTRATION_COUNT=0
```

The G0 log-only probe observed:

```text
RECENT_DIRECT_ACCEPT_LOG_COUNT=0
CURRENT_NODE_ONLINE_STATE=UNKNOWN_FROM_THIS_LOG_ORACLE
```

This is not promoted to an offline/product-failure claim. KF-140 explicitly forbids using absence of the expected Manager log line as the sole runtime-delivery oracle. G0 does not mutate or access the board to resolve this observation.

## 6. Home Assistant state

```text
HOMEASSISTANT_HTTP_REACHABLE=true
HOMEASSISTANT_ROOT_HTTP_STATUS=302
HOMEASSISTANT_INSPECT_HTTP_STATUS=401
HOMEASSISTANT_ONBOARDING_HTTP_STATUS=200

HOMEASSISTANT_ONBOARDING_USER_DONE=false
HOMEASSISTANT_ONBOARDING_CORE_CONFIG_DONE=false
HOMEASSISTANT_ONBOARDING_ANALYTICS_DONE=false
HOMEASSISTANT_ONBOARDING_INTEGRATION_DONE=false
HOMEASSISTANT_ONBOARDING_COMPLETE=false
```

No Home Assistant user, token, integration, YAML, or storage state was created or modified in G0.

## 7. PASS classification

```text
U0_HARD_BASELINE_COMPATIBLE=true
PRODUCT_SERVICES_HEALTHY=true
NO_ACTIVE_UPDATER_TRANSACTION=true
NO_ACTIVE_PAIRING_MUTATION=true
HOMEASSISTANT_HTTP_REACHABLE=true

G0_RESULT=CLOSED_PASS
```

The zero recent Direct-log count is retained as a non-blocking observation only. It does not override the frozen G0 PASS criteria and does not reopen U0.

## 8. Closure / next boundary

```text
PRE_U1_G0=CLOSED_PASS
NEXT_ROUTE=N3W_PRE_U1_NORMAL_PRODUCT_RUNTIME_ACCEPTANCE_G1_HA_LOCAL_ONBOARDING_20261104_01
AUTO_EXECUTE_NEXT_GATE=false
NEW_G1_AUTHORIZATION_REQUIRED=true

LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
STOP=true
```

G1 is the first gate allowed to create a normal Home Assistant local Owner account if onboarding is still pending. This G0 closure intentionally stops before that mutation.

## 9. Known-failure disposition

```text
NEW_KF_REQUIRED=false
KNOWN_FAILURE_UPDATE_REQUIRED=false
KF140_GUARD_APPLIED=true
```
