# N3-W PR #480 T1 maintenance live closure

Updated: 2026-09-27  
Status: `CLOSED_PASS`

This document records the public-safe source/live closure for the two T1 maintenance items that remained after PR #478.

## Repository binding

```text
PR480_SOURCE_HEAD=1749800677f8c5ecb846edb3bad2550382de78d5
PR480_SOURCE_CI=12_OF_12_PASS
PR480_MERGED=true
PR480_MERGE_COMMIT=20153019301e323c71b861b46f3f818a8fe3f1c2
MAIN_AFTER_PR480=20153019301e323c71b861b46f3f818a8fe3f1c2
PR480_POSTMERGE_PUSH_CI=NOT_OBSERVED_BY_AVAILABLE_WORKFLOW_RUN_QUERY
```

No post-merge run was returned for the merge commit by the available workflow-run query. This is an observability limitation and is not represented as PASS or FAIL.

## Live source binding

Before mutation, live T1 matched the proven pre-PR480 state. Rollback snapshots were created before applying either candidate.

```text
PRE_LIVE_ACTIVATION_UNIT_SHA256=8dc02608dcdabca420e45915ca2afb42c985642db44f414446e45dabf1242a99
PRE_LIVE_MOSQUITTO_CONF_SHA256=a55c2479df1e9ff1d5547edf487f38e7a2edca0b57ccf5dfb7a590dd331a4848
DYNAMIC_SECURITY_JSON_SHA256=6ce50940230717a490e85113ba522bd84465f4133bfc82299e022a55c841377e

POST_LIVE_ACTIVATION_UNIT_SHA256=97cc2dad0f6239634493b430651a51ab9ab3bbc92843c1766d2540d0850c31b3
POST_LIVE_MOSQUITTO_CONF_SHA256=4ed22799fabaa019bea79b19191986e967cfe11444e8af1ced5e70987aeda333
DYNAMIC_SECURITY_JSON_SHA256_UNCHANGED=true
```

## Compose orphan closure

Fresh ownership evidence proved that `fc4-homeassistant` is still a running service under Compose project `n3wfc4`, but is managed by a different Compose authority than the current Broker activation file. It is therefore not a disposable orphan.

The live activation unit now contains:

```text
COMPOSE_IGNORE_ORPHANS=true
```

Acceptance:

```text
COMPOSE_IGNORE_ORPHANS_EFFECTIVE=true
COMPOSE_ORPHAN_WARNING=ABSENT
FC4_HOMEASSISTANT_RUNNING=true
FC4_HOMEASSISTANT_RESTART_COUNT=0
INDEPENDENT_HOMEASSISTANT_RUNNING=true
INDEPENDENT_HOMEASSISTANT_RESTART_COUNT=0
REMOVE_ORPHANS_EXECUTED=false
HOMEASSISTANT_MUTATION=false

COMPOSE_FC4_HOMEASSISTANT_ORPHAN_OWNERSHIP=CLOSED_PASS
```

## Mosquitto 2.1 deprecation closure

The live Broker is Mosquitto 2.1.2. The old global security semantics were migrated from:

```text
per_listener_settings false
plugin /usr/lib/mosquitto_dynamic_security.so
```

to:

```text
global_plugin /usr/lib/mosquitto_dynamic_security.so
```

while keeping the Dynamic Security config binding, TLS listener, anonymous-access policy, persistence, and logging settings unchanged.

An initial candidate test using `/dev/stdin` failed because Mosquitto 2.1.2 requires the config argument to be a file. This was a test-harness defect, not a candidate-config defect. A subsequent isolated validation using the exact production image and a real read-only candidate file returned `Configuration file is OK` and exit code 0.

Acceptance:

```text
PER_LISTENER_SETTINGS_COUNT=0
GLOBAL_DYNSEC_PLUGIN_COUNT=1
DYNSEC_CONFIG_DIRECTIVE_COUNT=1
DYNSEC_CONFIG_MODE=600
PER_LISTENER_SETTINGS_WARNING=ABSENT
DYNAMIC_SECURITY_CONTINUITY=PASS

MOSQUITTO_PER_LISTENER_SETTINGS_DEPRECATION=CLOSED_PASS
```

## Runtime continuity

```text
BROKER_RUNNING=true
BROKER_RESTART_COUNT=0
TCP_8883_LISTEN_COUNT=1

MANAGER_RUNNING=true
MANAGER_RESTART_COUNT_BEFORE=1
MANAGER_RESTART_COUNT_AFTER=1
MANAGER_LOOPBACK_8883_ESTAB_COUNT=1
MANAGER_LOOPBACK_TLS_MQTT_CONTINUITY=PASS

BROKER_AUTH_ERROR_COUNT=0
BROKER_CONNECT_NOTICE_COUNT=2
AUTHENTICATED_MQTT_RUNTIME_PATH=PASS

FC4_HOMEASSISTANT_RUNNING=true
INDEPENDENT_HOMEASSISTANT_RUNNING=true
HOMEASSISTANT_CONTINUITY=PASS
```

## R5 regression guard continuity

```text
GUARD_ACTIVE=active
GUARD_ENABLED=enabled
ACTIVATION_ACTIVE=active
ACTIVATION_ENABLED=enabled

DOCKER_USER_ANCHOR_COUNT=1
DOCKER_USER_ANCHOR_POSITION=1
INPUT_ANCHOR_COUNT=1
INPUT_ANCHOR_POSITION=1
R5_OWNED_CHAIN_RULE_COUNT=3

R5_FIREWALL_CONTINUITY=PASS
AUTOMATIC_ROLLBACK_TRIGGERED=false
FINAL_LIVE_ACCEPTANCE=PASS
PR480_LIVE_REPAIR=CLOSED_PASS
```

No firewall redesign, board access, B2 execution, B3 execution, Home Assistant mutation, or Dynamic Security JSON mutation occurred.

## Remaining explicit scopes

```text
EXTERNAL_UNTRUSTED_ETH0_PHYSICAL_NEGATIVE=NOT_PROVEN
B2_STABLE_T1_HOSTNAME_TLS_IDENTITY=OPEN_OUT_OF_SCOPE
B3_ALREADY_PROVISIONED_NODE_LITERAL_BROKER_IP_MIGRATION=OPEN_OUT_OF_SCOPE
```

These remain separate from PR #480 closure.

## Next route

```text
NEXT_ONE_GATE=N3W_PR474_POST_INFRA_CLOSURE_DISPOSITION_READONLY_REVIEW_20260927_01
PR474_MUTATION=false
BOARD_ACCESS=false
```
