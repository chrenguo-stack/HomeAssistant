# N3-W Auto Safe Fallback Gate A MQTT Retarget Status — 2026-09-29

This document tracks the staged Gate A validation for the N3-W auto safe fallback design.

## Frozen source authority

```text
SOURCE_HEAD=8210cf7b53e9ec934d145f1c15e9619579c923be
SOURCE_TREE=5d3e6ad7151938ffa7ac23b2b6af6663bcd10c7c
TARGET_BLOB=7279271d469958940c2b51aa4a80602078470891
PATCH_BLOB=49570a83ead08158d4d99c385740fa6d646b5e3d
ESPHOME_VERSION=2026.4.3
ESP_IDF_VERSION=5.5.4
```

Design authority:
`docs/development/N3W_AUTO_SAFE_FALLBACK_DEVELOPMENT_TEST_PLAN_V1_20260929.md`

## Gate A acceptance state

Gate A proves only whether the existing MQTT backend can retarget the runtime TCP/TLS address while preserving TLS and MQTT identity. Full auto fallback remains blocked until physical timing acceptance passes.

```text
RUNTIME_BOUNDED_CANCEL_PROVEN=false
FULL_AUTO_FALLBACK_IMPLEMENTATION_ALLOWED=false
PHYSICAL_ACCEPTANCE_COMPLETE=false
MERGE=false
```

## First T1 isolated-lab attempt

The first activation entered live mutation and failed. Subsequent read-only forensic proved automatic cleanup completed with no lab container, alias, TCP/18883 listener or remote private root left behind. Production Broker restart_count remained 0.

Exact runtime-user forensic then proved:

```text
BROKER_PID1_UID=1883
BROKER_PID1_GID=1883
MOSQUITTO_ACCOUNT_UID=1883
MOSQUITTO_ACCOUNT_GID=1883
BROKER_PROCESS_IS_MOSQUITTO_ACCOUNT=true
```

The first activation staged a root-only mode-0700 directory and root-only mode-0600 Broker files. This is incompatible with the proven 1883:1883 Broker runtime identity.

```text
T1_ISOLATED_LAB_ACTIVATION_ATTEMPT_1=FAIL
T1_ISOLATED_LAB_PREFLIGHT_1_CONSUMED=true
T1_ISOLATED_LAB_FAILURE_CLEANUP=PASS
T1_ISOLATED_LAB_RESIDUE_STATE=CLEAN
T1_ISOLATED_LAB_PERMISSION_ROOT_CAUSE_PROVEN=true
```

## T1 restart and address change

The user intentionally restarted T1 after moving to a different network while travelling. The observed Manager restart_count=1 and T1 address change are therefore expected consequences of that user-initiated transition and are not classified as Gate A failures.

The previous Gate A private application embedded the previous restore-host IPv4 and is superseded.

## Rebind V2

A T1-only network preflight was added so address rebinding does not require live Board B access.

The read-only V2 preflight passed with:

```text
T1_NETWORK_PREFLIGHT_V2=PASS
BROKER_RESTART_COUNT=0
MANAGER_RESTART_COUNT=1
PORT_18883_FREE=true
BROKER_IPV4_WILDCARD_8883=true
T1_MUTATION=false
BOARD_ACCESS=false
DHCP_POOL_EXCLUSION=PASS
```

The active router DHCP allocation pool ends below the two private Gate A candidate addresses. The concrete LAN candidates are intentionally not stored in the public repository.

## Private exact rebuild V2

The private exact rebuild completed on the Mac using the existing exact ESPHome CLI. The rebuilt firmware is bound to the current T1 restore-host address.

```text
PRIVATE_EXACT_REBUILD_V2=PASS
APPLICATION_SIZE=1140352
APPLICATION_SHA256=95a5be58688d5d96a54dbeed0ce0c9e41edbf6d891e6b93763beaae738ca759c
OTADATA_SIZE=8192
OTADATA_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f
CA_CERT_SHA256=59b5ac189ded12aad5e34347d8b9fa9daa4f1544eb8c5c8d72bfa41a1fb63ecd
SERVER_CERT_SHA256=2740a8fd7a649ed297517bd488e83e837abadc2af0375999fe603b6bb7252ee6
SERVER_KEY_SHA256=69961a59147d50e48ddd39fd86b94327c0ccd8bcbdda0b45ae3c3689602ae9e4
BROKER_PORT=18883
TLS_SERVER_NAME=n3w-gate-a.invalid
RESTORE_HOST_REBOUND=true
BOARD_ACCESS=false
BOARD_FLASH=false
T1_MUTATION=false
```

The private bundle path, LAN addresses, MQTT credentials and TLS private material remain outside GitHub.

## Current STOP point

The next live sequence is intentionally blocked until a permission-repaired T1 lab executor is bound to the refreshed private build and a new fresh T1 lab preflight passes.

Required order:

```text
permission-repaired T1 lab executor binding
-> fresh T1 lab read-only preflight
-> new explicit T1 activation authorization
-> isolated T1 lab activation
-> fresh Board B read-only preflight
-> Board B write authorization
-> physical timing gate
-> cleanup
-> rollback as required
```

Do not replay the consumed first activation preflight or authorization. Do not use the superseded private application. Do not write Board B before successful isolated-lab activation under a new fresh preflight and new authorization.
