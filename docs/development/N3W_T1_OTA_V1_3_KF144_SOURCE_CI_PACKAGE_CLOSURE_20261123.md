# N3-W T1 Core Stack OTA V1.3 — KF-144 source / CI / package closure（2026-11-23）

## 0. Result

```text
TASK=N3W_T1_OTA_V1_3_KF144_SOURCE_CI_PACKAGE_CLOSURE
STATUS=SOURCE_CI_PACKAGE_CLOSED
LIVE_REPAIR_STATUS=PENDING
PR=824
EXECUTABLE_SOURCE_HEAD=1fbe674e25edb4c6fb1a3740042778adc55def68

KF_144=SOURCE_CI_CLOSED_LIVE_REPAIR_PENDING
BROKER_OTA_DEFERRED=true
T1_MUTATION_IN_THIS_CLOSURE=false
```

KF-144 的源码、CI、live predecessor baseline、Manager successor authority 和 exact execution artifacts 已闭合。真实备用 T1 尚未执行 U4 failure retirement、Manager successor、candidate monitoring activation 或新的 HA PREPARE，因此 KF-144 尚不能转为 GUARDED。

## 1. Live failure state carried forward

最后一次只读实机证据：

```text
TRANSACTION_STATUS=ACTIVE
TRANSACTION_PHASE=U4_READY_TO_INSTALL
TRANSACTION_FILE_SHA256=a22a4260401ddb04318afba1b03495edb23a32c68196372987501b50154c2a66
FAILURE_CODE=ha_usb_predecessor_acceptance_baseline_unavailable
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
TARGET_IMAGE_LOADED=false

LIVE_HOMEASSISTANT=local/n3w-homeassistant:2026.10.4-5881590f
LIVE_MANAGER=local/greenhouse-manager:fresh-44e7d7472714
LIVE_BROKER=local/n3w-mosquitto:2.1.2-3184566d
HA_MANAGER_BROKER_HEALTH=PASS
```

诊断证明：

- ordinary production HA configuration 正在运行；
- `n3w_ota_monitoring` config/component 未挂载；
- live Manager 不具备 `_publish_ota_monitoring_self_test`；
- replay DB 存在，但最新自然 telemetry cursor 为 `2026-11-05T04:46:28.285Z`；
- protected-data capture PASS；
- 因此 predecessor acceptance baseline 在该现场结构性不可达，不能通过等待或盲目重试解决。

Attempt 02 的 schema-v3 install authority 最后观察为存在但未 claim/consume；其 `expires_at_unix=1795435177`，release pin `expires_at_unix=1795436977`。两者均已过期，不得在后续会话重放。执行前必须 fresh rebind 文件存在性和 live transaction/runtime 状态。

## 2. Live Generic V2 baseline

```text
BASELINE_SCHEMA=gh.n3w-t1-core-updater-baseline/1
BASELINE_SHA256=78404869cda4b6fe14226b514623880b76045cd9a58a149f063d61edf57dd199

MANAGER_IMAGE=local/greenhouse-manager:fresh-44e7d7472714
MANAGER_IMAGE_ID=sha256:1471828ab07cf9b71c01a6e78994711a5954f0a178b8be087a28bb65a967c7d2
MANAGER_RUNTIME_CONTRACT_SHA256=ad1d38f6191c0c00afcfbee3ca489d5f95a86fefcb17976c273597c04609d6e1

HOMEASSISTANT_IMAGE=local/n3w-homeassistant:2026.10.4-5881590f
HOMEASSISTANT_IMAGE_ID=sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365
HOMEASSISTANT_RUNTIME_CONTRACT_SHA256=bc69586866551709110435ea25bfdff9d41bc8e366f6ace8d4b7bba3db5f6868

BROKER_IMAGE=local/n3w-mosquitto:2.1.2-3184566d
BROKER_IMAGE_ID=sha256:df265f1e2b2e3dc35d5eb194e698c598e01c5ebca370da307b34332f9bf0a563
BROKER_RUNTIME_CONTRACT_SHA256=b4e002c7eb494812629b1a99d7e53b712d5f2239460c99334556976b6fdad492

COMPOSE_SHA256=f5fc319e155e89c50d1a52fa7813a00f3cf36b4203937cae0d99c9ae5dbb9d15
COMPOSE_ENV_SHA256=3aa68488b4b08b0a099fc9492746cfa66e45274b6027a5eb83d8f4aee8c28f18
OTA_INSTALLED_VERSION_ENV_PRESENT=false
LIVE_MANAGER_SELF_TEST_CAPABILITY=false
```

Durable baseline authority:

`infra/n3w-t1/clean-reference/kf144-manager-successor-baseline-20261123.json`.

## 3. Source repair closed

At executable source head `1fbe674e25edb4c6fb1a3740042778adc55def68`:

- no-mutation U4 predecessor-baseline/install-revalidation failure can be represented as a bounded terminal failure without fabricating U13B rollback actions;
- `--retire-precutover-failure` validates exact predecessor runtime, target absence and authorization non-consumption before closing that U4 failure;
- legacy Manager without monitoring self-test now fails candidate activation readiness instead of passing as `natural_only`;
- candidate monitoring runtime has an explicit activation / rollback path;
- Manager + HA candidate activation preserves Broker and image identities;
- activation must prove a real Manager → Broker → HA maintenance self-test round trip;
- `GH_N3W_T1_OTA_INSTALLED_VERSION` is persisted in the same compose env authority as `GH_HOMEASSISTANT_IMAGE` and updated with HA image replacement.

## 4. Exact CI closure

For `1fbe674e25edb4c6fb1a3740042778adc55def68`:

```text
WORKFLOW_TOTAL=22
WORKFLOW_SUCCESS=22
WORKFLOW_FAILURE=0
WORKFLOW_RUNNING=0
WORKFLOW_PENDING=0

FAST_SOURCE_EXACT_CLOSURE=SUCCESS
MANAGER_A_TO_B=SUCCESS
HA_TARGET_BINDING=SUCCESS
FRESH_EXACT_ARM64=SUCCESS
GREENHOUSE_MANAGER_CI=SUCCESS
PUBLIC_REPOSITORY_SAFETY=SUCCESS
```

Key runs:

- Manager A-to-B: run `45175810919`;
- HA target binding: run `45175810759`;
- fresh exact ARM64: run `45175811054`;
- fast source/exact closure: run `45175810490`.

## 5. Manager successor authority

```text
PREDECESSOR_SOURCE_HEAD=44e7d74727147975de88e85c4b18ba3f7493fd76
TARGET_SOURCE_HEAD=1cae18039eeedb7f6dea2e3e352df26dd488a30e

TARGET_MANAGER_IMAGE=local/greenhouse-manager:fresh-1cae18039eee
TARGET_MANAGER_IMAGE_ID=sha256:9547078268e5f2550b46583abbd87d9f0a6bbaa727a0af2c19379ca906954867
TARGET_MANAGER_TAR_SHA256=bbce0ee5c399b2fbc315dcf34affb6391f54864144faba4f9efb983b160c8734
TARGET_MANAGER_TAR_SIZE_BYTES=62953984

COMPATIBILITY_REVIEW_SHA256=5046d2e180db6a0c620cfc91a58577d80a9fac2199b7155ff20015ca61caae03
HA_EXACT_ARM64_MANAGER_MONITORING_ROUND_TRIP=PASS

KF144_MANAGER_PACKAGE_ARTIFACT_ID=14819845760
KF144_MANAGER_PACKAGE_ARTIFACT_DIGEST_SHA256=362c300922816730d4209d450b376769c19319a34d594d2c3a90ea2e31ab143a
KF144_GENERIC_V2_UPDATER_PYZ_SHA256=d43036f333872e2e25272b26552809c8d40cd822efc8f0d414e71878594bf2bc
```

Authority files:

- `infra/n3w-t1/upgrades/manager-1cae18039eee-kf144.json`;
- `infra/n3w-t1/upgrades/manager-1cae18039eee-kf144-compatibility.json`;
- `infra/n3w-t1/clean-reference/kf144-manager-successor-baseline-20261123.json`.

## 6. HA recovery package

```text
HA_RECOVERY_RUN_ID=45175810759
HA_RECOVERY_ARTIFACT_ID=14818806074
HA_RECOVERY_ARTIFACT_DIGEST_SHA256=46bc0cc890b791de8219cabb12eb162136027c2ad7d6ef1c4fb4d3c21a2f009d
HA_RECOVERY_INSTALL_MANIFEST_SHA256=ef8e040fabe2fa1619d1ee28fce1785a535ef85edd15f8f4d416ed780e08fe07
SOURCE_HEAD=1fbe674e25edb4c6fb1a3740042778adc55def68
```

This package contains the repaired `--retire-precutover-failure` and candidate-runtime activation path. It has not been deployed to the spare T1.

## 7. Next live sequence

No further live mutation is performed by this closure.

The next live work must first fresh rebind the spare T1. If the U4 failure/runtime facts remain exact, proceed only under an explicit bounded execution package:

1. patch/install the exact repaired HA recovery package without advancing the HA transaction;
2. retire the proven no-mutation U4 failure and invalidate/remove stale expired install-authority residue through the repaired command;
3. run Generic V2 Manager successor from `fresh-44e7...` to `fresh-1cae...` using artifact `14819845760`;
4. activate candidate monitoring runtime and require the real self-test round trip PASS;
5. only then create a fresh HA PREPARE and resume the 10.4 → 10.0 maintenance transaction;
6. Broker OTA remains deferred.

Any source/runtime/transaction/authorization drift stops the affected live step.
