# N3-W T1 Core Updater — U0 Real T1 Read-only Baseline Closure

Date: 2026-11-04

## 1. Gate result

```text
GATE=N3W_T1_CORE_UPDATER_U0_REAL_T1_READONLY_BASELINE_20261104_01
RESULT=PASS
BASELINE_A_CAPTURED=true
BASELINE_A_SHA256=a791377083e76f765ddf978c09025674eda3586d33892e4b609a814706bdfbbc
BASELINE_A_BYTES=2275
T1_PRODUCT_MUTATION=false
SERVICE_RESTART=false
UPDATER_TRANSACTION_CREATED=false
UPDATER_APPLY=false
UPDATER_ROLLBACK=false
BOARD_ACCESS=false
MERGE=false
```

## 2. Exact source and updater authority

```text
PR=774
REVIEWED_SOURCE_HEAD=4dd39befedce891bd2db3cc84c592d41f778bc51
A2_SOURCE_REVIEW=CLOSED_PASS
WORKFLOW_RUN_ID=41697300611
WORKFLOW_ARTIFACT_ID=13261072174
WORKFLOW_ARTIFACT_NAME=n3w-t1-core-updater-manager-b863ddd95909
WORKFLOW_ARTIFACT_DIGEST_SHA256=cb070fdc1a10b2a17675449b3fc0e4bc868fac88a1e1f878ca2203a5d4b39aac
UPDATER_PYZ_SHA256=54f2e6299fa8905d33033ea86b5d449f16ad4dcd6ae8c7a3e9d647d6001e22fa
```

U0 executed only the reviewed V2 `baseline` command. The Manager target manifest and Manager
image tar in the artifact were not used for U0.

## 3. Two-read stability proof

The exact same baseline command was executed twice against the live clean-reference T1_B without
any intervening product mutation.

```text
READ_1_BYTES=2275
READ_2_BYTES=2275
READ_1_SHA256=a791377083e76f765ddf978c09025674eda3586d33892e4b609a814706bdfbbc
READ_2_SHA256=a791377083e76f765ddf978c09025674eda3586d33892e4b609a814706bdfbbc
CMP_EXIT=0
BYTE_IDENTICAL=true
```

This closes the U0 stability requirement. The frozen machine-readable baseline is:

```text
infra/n3w-t1/clean-reference/u0-upgrade-baseline-a-20261104.json
```

## 4. Frozen Baseline A

```text
SCHEMA=gh.n3w-t1-core-updater-baseline/1
A1_CLASSIFICATION_SHA256=e664ced300ea2bb743b116550b7a3e22237e7f556f54400a060eef30671d30e7
MANAGER_IMAGE=local/greenhouse-manager:fresh-b863ddd95909
HOMEASSISTANT_IMAGE=local/n3w-homeassistant:2026.10.0-0c73235a
BROKER_IMAGE=local/n3w-mosquitto:2.1.2-3184566d
MANAGER_PLATFORM=linux/arm64
HOMEASSISTANT_PLATFORM=linux/arm64
BROKER_PLATFORM=linux/arm64
MANAGER_BINDING_MODE=dynamic
HOMEASSISTANT_BINDING_MODE=legacy_static
BROKER_BINDING_MODE=legacy_static
MANAGER_RUNTIME_CONTRACT_SHA256=ad1d38f6191c0c00afcfbee3ca489d5f95a86fefcb17976c273597c04609d6e1
HOMEASSISTANT_RUNTIME_CONTRACT_SHA256=bc69586866551709110435ea25bfdff9d41bc8e366f6ace8d4b7bba3db5f6868
BROKER_RUNTIME_CONTRACT_SHA256=b4e002c7eb494812629b1a99d7e53b712d5f2239460c99334556976b6fdad492
```

The A1 hard authority also freezes the observed fixed configuration hashes, custom-component tree,
persistent path ownership/type, MQTT identity hashes, SQLite schema hashes and user_version,
FC4/System CA hashes, Dynamic Security top-level structure hash, and Home Assistant registry storage
versions.

## 5. Interpretation

U0 does not discover a new product defect.

Manager is already on the current accepted image and uses the dynamic image binding required by the
per-module updater.

Home Assistant and Broker are healthy and part of Baseline A, but their live compose bindings are
still `legacy_static`. That is allowed for U0 and does not invalidate the baseline. It does mean
those two components are not yet independently upgradeable under the V2 per-module updater; a
separate runtime-template convergence gate is required before any HA/Broker image mutation.

## 6. Mutation audit

```text
T1_PRODUCT_CONFIG_CHANGED=false
T1_PRODUCT_STATE_CHANGED=false
SERVICE_RESTART=false
IMAGE_MUTATION=false
IMAGE_BINDING_MUTATION=false
TRANSACTION_STATE_CREATED=false
PAIRING_STATE_CHANGED=false
REGISTRATION_STATE_CHANGED=false
BOARD_MUTATION=false
```

Only a temporary reviewed pyz was copied to `/tmp` for observation and removed by the operator
script. No product/runtime path was used as updater transaction state.

## 7. Next gate

```text
NEXT_GATE=N3W_T1_CORE_UPDATER_U1_MANAGER_A_TO_B_PREPARATION_20261104_01
U1_LIVE_APPLY_AUTHORIZED=false
```

U1 preparation may now bind a Manager successor target against Baseline A and prove the exact
predecessor/target package and plan semantics.

Actual U1 apply remains a live T1 mutation boundary and requires explicit authorization before
execution.
