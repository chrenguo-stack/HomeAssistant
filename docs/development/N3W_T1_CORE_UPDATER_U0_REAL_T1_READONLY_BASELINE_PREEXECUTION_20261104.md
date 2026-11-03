# N3-W T1 Core Updater — U0 Real T1 Read-only Baseline Preexecution

Date: 2026-11-04

## 1. Gate

```text
GATE=N3W_T1_CORE_UPDATER_U0_REAL_T1_READONLY_BASELINE_20261104_01
PURPOSE=freeze explicit upgrade baseline A from the current accepted clean-reference T1_B
TARGET=T1_B
T1_B_SSH=root@192.168.68.194
T1_A_ACCESS=false
BOARD_ACCESS=false
LIVE_PRODUCT_MUTATION=false
UPDATER_APPLY=false
UPDATER_ROLLBACK=false
SERVICE_RESTART=false
CONFIG_MUTATION=false
```

U0 is observation only. It does not choose target B and does not prove an A -> B upgrade.

## 2. Source and exact updater authority

```text
PR=774
EXACT_SOURCE_HEAD=4dd39befedce891bd2db3cc84c592d41f778bc51
SOURCE_REVIEW=N3W_T1_CORE_UPDATER_A2_PER_MODULE_SOURCE_CLOSURE_REVIEW_20261104_01:CLOSED_PASS
WORKFLOW_RUN_ID=41697300611
WORKFLOW_ARTIFACT_ID=13261072174
WORKFLOW_ARTIFACT_NAME=n3w-t1-core-updater-manager-b863ddd95909
WORKFLOW_ARTIFACT_DIGEST_SHA256=cb070fdc1a10b2a17675449b3fc0e4bc868fac88a1e1f878ca2203a5d4b39aac
UPDATER_PYZ_SHA256=54f2e6299fa8905d33033ea86b5d449f16ad4dcd6ae8c7a3e9d647d6001e22fa
```

The artifact is reused only as the exact reviewed transport for
`t1-core-updater.pyz`. U0 must not execute or stage the included Manager tar or target
manifest.

## 3. Why the command is read-only

The only updater operation permitted in this gate is:

```text
t1-core-updater.pyz baseline
```

The baseline path performs current-state observation only:

- systemd state queries;
- Docker Compose render / running-service queries;
- Docker image/container inspection;
- current listener observation;
- current Manager/Home Assistant MQTT-authenticated-session evidence from Broker logs;
- Home Assistant HTTP health probe;
- read-only SQLite integrity/schema observation;
- fixed configuration/custom-component hashes;
- persistent-path metadata;
- FC4/System CA hashes and Broker certificate semantic verification;
- Dynamic Security top-level structure hash;
- MQTT identity hashes without exposing credential values;
- Home Assistant registry storage version observation.

It does not call the V2 transaction store, Docker load, image-binding rewrite, service stop/start,
apply, rollback, pairing mutation, registration mutation, or board operations.

## 4. Temporary transport boundary

The reviewed pyz may be copied only to a bounded temporary path on T1_B:

```text
/tmp/n3w-u0-readonly-4dd39bef/t1-core-updater.pyz
```

This temporary tool staging is not product/runtime configuration mutation. No file below
`/etc/n3wfc4`, `/opt/HomeAssistant`, `/opt/greenhouse-secrets`,
`/var/lib/greenhouse-manager`, `/var/lib/n3wfc4-broker`,
`/var/lib/n3wfc4-homeassistant`, or `/var/lib/n3w-t1-core-updater` may be created,
changed, or removed by U0.

## 5. Required observations

A successful U0 baseline must prove:

```text
BASELINE_SCHEMA=gh.n3w-t1-core-updater-baseline/1
STACK_COMPONENTS=manager,homeassistant,broker
PLATFORM_ALL=linux/arm64
A1_CLASSIFICATION_SHA256=e664ced300ea2bb743b116550b7a3e22237e7f556f54400a060eef30671d30e7
MANAGER_BINDING_MODE=dynamic
HA_BINDING_MODE=dynamic|legacy_static
BROKER_BINDING_MODE=dynamic|legacy_static
PAIRING_REGISTRATION_CONFLICT=false
CERTIFICATE_LIFECYCLE_CONFLICT=false
NO_SECRET_VALUES_IN_OUTPUT=true
```

HA/Broker `legacy_static` is permitted in U0 and is recorded as baseline fact. It does not
authorize HA/Broker upgrade; those mutations remain fail-closed until a separate runtime-template
convergence gate.

## 6. Two-read stability rule

Run the exact same baseline command twice without any intervening mutation. The two JSON outputs
must be byte-identical. This proves the frozen baseline contains stable upgrade authority rather
than transient container IDs, timestamps, restart counts, socket counts, row counts, or other A1
diagnostic/runtime-drift fields.

If the two outputs differ, STOP and classify the differing field before accepting baseline A.

## 7. Stop conditions

U0 stops without mutation on any of the following:

- source/artifact/pyz digest mismatch;
- updater output status STOP or nonzero exit;
- unsupported component platform;
- required N3-W role unit unhealthy;
- relevant failed unit;
- product service set not exactly Manager/Home Assistant/Broker;
- active pairing/registration listener;
- active Broker certificate-lifecycle service;
- missing current Manager/HA MQTT authentication;
- Home Assistant HTTP health outside the allowed set;
- unsafe/unusable persistent directory;
- SQLite integrity failure;
- A1 hard-identity capture failure;
- two baseline outputs not byte-identical.

No repair, restart, cleanup, retry-by-mutation, apply, rollback, or runtime-template convergence is
authorized inside this gate.

## 8. Expected closure

```text
U0_RESULT=PASS|STOP
BASELINE_A_CAPTURED=true|false
BASELINE_A_SHA256=<sha256 of exact baseline JSON>
T1_PRODUCT_MUTATION=false
SERVICE_RESTART=false
UPDATER_TRANSACTION_CREATED=false
NEXT_GATE=U1_PREPARATION only after U0 PASS
```
