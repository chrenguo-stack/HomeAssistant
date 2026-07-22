# H3/N2 Stage 2D-9 G3 PREPARE_CANDIDATE 状态

- **状态版本：** V1.1
- **更新日期：** 2026-07-22
- **起始基线：** `2a5272546f25b1b29cf1d6682cf1fc14f1c1be83`
- **开发分支：** `feature/h3-n2-stage2d9-g3-prepare-candidate-20260722-v1`
- **Draft PR：** `#174`
- **阶段状态：** `g3_executor_and_immutable_artifact_development`
- **执行门：** `LOCKED`

## 当前完成

```text
SCOPE_PROTOCOL_FROZEN=true
HOST_TRANSACTION_MODEL_IMPLEMENTED=true
HOST_COMMAND_PROTOCOL_IMPLEMENTED=true
HOST_FAULT_MATRIX_CASES=21
HOST_MODEL_AND_GATE_CI=passed
LOCKED_MANIFEST_TEMPLATE_IMPLEMENTED=true
MANIFEST_GATE_IMPLEMENTED=true
LOCKED_G3_HARNESS_IMPLEMENTED=true
TOKEN_GATED_PREPARE_EXECUTOR_IMPLEMENTED=true
DEDICATED_WRITABLE_TEST_PARTITION_DEFINED=true
LOCKED_RECOVERY_TARGET_IMPLEMENTED=true
REPRODUCIBLE_BUILD_WRAPPER_IMPLEMENTED=true
ARTIFACT_BOUNDARY_GATE_IMPLEMENTED=true
ARTIFACT_PACKAGER_IMPLEMENTED=true
PRIVATE_UNLOCK_PREIMAGE_IN_GIT=false
DEVICE_OPERATION_AUTHORIZED=false
D2_AUTHORIZATION_PRESENT=false
```

## 固定事务

```text
ACTIVE_GENERATION_BEFORE=0
ACTIVE_GENERATION_AFTER=0
CANDIDATE_GENERATION_BEFORE=0
CANDIDATE_GENERATION_AFTER=1
CANDIDATE_STATE_AFTER=PREPARED
PARTITION=gh2d8_p2d9
PARTITION_OFFSET=0x400000
PARTITION_SIZE=0x10000
NAMESPACE=gh2d8_s2d9
```

## 计划状态

| 项目 | 状态 |
|---|---|
| P0 范围和协议 | `complete` |
| P1 Host 事务模型 | `passed_ci` |
| P2 Manifest 和命令 gate | `passed_ci` |
| P3 G3 固件 harness/executor | `implemented_compile_validation_in_progress` |
| P4 专用板与产品板 compile-only | `validation_in_progress` |
| P5 可重复 V67 Artifact | `workflow_implemented_validation_in_progress` |
| P6 证据和一次性执行包 | `not_started` |
| P7 用户主机 Artifact 只读验证 | `not_started` |
| P8 实板 PREPARE | `not_authorized` |
| P9 证据闭环 | `not_started` |

## Artifact 安全边界

```text
ARTIFACT_GENERATION=V67
ARTIFACT_GATE=LOCKED
UNLOCK_DIGEST_PUBLIC=true
UNLOCK_PREIMAGE_PUBLIC=false
FLASH_AUTHORIZED=false
PREPARE_AUTHORIZED=false
VERIFY_AUTHORIZED=false
ACTIVATE_AUTHORIZED=false
CLEANUP_AUTHORIZED=false
NETWORK_AUTHORIZED=false
EFUSE_AUTHORIZED=false
PRODUCTION_AUTHORIZED=false
```

V67 源码只包含私有 one-time unlock preimage 的 SHA-256，不包含 preimage、持久化密钥、授权 JSON、candidate 命令或任何实际凭据。公共 compile-only executor 使用全零 digest，命令面关闭。

## 固定禁止项

```text
ACTIVATE_PROFILE_AUTHORIZED=false
CLEANUP_TEST_STATE_AUTHORIZED=false
WIFI_AUTHORIZED=false
MQTT_AUTHORIZED=false
BROKER_AUTHORIZED=false
EFUSE_OPERATION_AUTHORIZED=false
PRODUCTION_ENVIRONMENT_OPERATION_AUTHORIZED=false
READY_MERGE_RELEASE_AUTHORIZED=false
STAGE2D8_D2_REPLAY_AUTHORIZED=false
```

## 下一步

完成 G3 executor 的专用板、产品板 compile-only 和 V67 双 clean build 可重复性验证；验证通过后冻结 Artifact、补齐 P6 私有/公共证据格式和一次性执行包，再进入新的精确 D2 审核。在 D2 前不连接测试板，不执行 Flash 或 writable NVS。
