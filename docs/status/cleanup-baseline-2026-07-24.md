# greenhouse-manager 模块清理基线报告（2026-07-24）

## 0. 报告状态

- 仓库：`chrenguo-stack/HomeAssistant`
- 冻结分析基线：`main=a3a72d75480362999e70e180f33459198b3951b5`
- 分析范围：`host/greenhouse-manager/src/greenhouse_manager/*.py`
- 本报告为本地草案；尚未写入仓库、未创建清理分支、未打 tag、未删除或修改任何仓库文件。
- 先前 Stage 2D-9R 私密内容预授权探测保持暂停。

## 1. 关键复核结论

### 1.1 模块数量

- 共识别 `117` 个 Python 文件（包含 `__init__.py`）。
- 排除包初始化文件 `__init__.py` 后为 `116` 个业务/包装模块，与任务背景中的 116 个模块一致。

### 1.2 入口点事实与任务前提不一致

- 当前 `pyproject.toml` 实际定义 **60 个** `[project.scripts]`，不是 5 个。
- 本报告仍严格按用户指定的 5 个“批准入口”计算主可达闭包。
- 另外 55 个脚本入口作为“非 Python 配置引用”单独记录；只要入口仍存在，对应模块就不能归入可直接删除的 A 类。

批准的五个入口：

- `greenhouse_manager.app:main`
- `greenhouse_manager.pairing_lab_cli:main`
- `greenhouse_manager.registration_cli:main`
- `greenhouse_manager.t1_preflight:main`
- `greenhouse_manager.t1_backup:main`

### 1.3 五入口静态传递闭包

- 可达：`21` 个文件（含 `__init__.py`），即 20 个业务模块。
- 从这 5 个入口不可达：`96` 个模块。
- 不可达不等于可删除：其中 55 个仍被当前 `pyproject.toml` 注册为 CLI；其余多数有测试、工具脚本、workflow 或协议文档引用。

## 2. 可达模块及调用链

- `app` → `config`, `mqtt_service`
- `mqtt_service` → `config`, `ha_discovery`, `ingest`, `pairing_intake`, `registration`, `topics`
- `ha_discovery` → `ingest`, `topics`
- `ingest` → `topics`
- `pairing_intake` → `registration`
- `registration_cli` → `registration`
- `pairing_lab_cli` → `dynsec_plan`, `pairing_runtime`, `pairing_runtime_config`
- `pairing_runtime` → `pairing_discovery`, `pairing_endpoint`, `pairing_network_service`, `pairing_runtime_config`, `pairing_secure_transport`, `pairing_service`, `registration`
- `pairing_discovery` → `pairing_secure_transport`
- `pairing_endpoint` → `pairing_discovery`, `pairing_secure_transport`, `pairing_service`
- `pairing_network_service` → `pairing_discovery`, `pairing_endpoint`
- `pairing_secure_transport` → `pairing_service`
- `pairing_service` → `dynsec_plan`, `registration`
- `t1_preflight`、`t1_backup` 无包内静态依赖

完整可达清单：

- `greenhouse_manager.__init__`
- `greenhouse_manager.app`
- `greenhouse_manager.config`
- `greenhouse_manager.dynsec_plan`
- `greenhouse_manager.ha_discovery`
- `greenhouse_manager.ingest`
- `greenhouse_manager.mqtt_service`
- `greenhouse_manager.pairing_discovery`
- `greenhouse_manager.pairing_endpoint`
- `greenhouse_manager.pairing_intake`
- `greenhouse_manager.pairing_lab_cli`
- `greenhouse_manager.pairing_network_service`
- `greenhouse_manager.pairing_runtime`
- `greenhouse_manager.pairing_runtime_config`
- `greenhouse_manager.pairing_secure_transport`
- `greenhouse_manager.pairing_service`
- `greenhouse_manager.registration`
- `greenhouse_manager.registration_cli`
- `greenhouse_manager.t1_backup`
- `greenhouse_manager.t1_preflight`
- `greenhouse_manager.topics`

## 3. A 类：不可达 + 无测试/配置/脚本引用

**结果：0 个。**

按加强后的安全标准，没有模块同时满足：

1. 不在五入口传递闭包；
2. tests 中无直接或传递引用；
3. 不被其余包模块 import；
4. 不被 `pyproject.toml`、`tools/`、workflow、compose/systemd 或文档字符串引用。

因此第二步当前没有可以仅凭本报告直接删除的“零风险模块”。

## 4. B 类：五入口不可达，但存在测试或外部引用，需人工判断

共 `85` 个模块。下表中的“CLI”表示它仍是当前 `pyproject.toml` 正式脚本入口。

### B1 核心外围与打包工具（4 个）

| 模块 | 测试引用核对 | 当前配置/外部引用 | 建议 |
|---|---|---|---|
| `__main__` | 未发现专属测试；但属于 `python -m greenhouse_manager` 包装入口 | 否；但存在包内/工具/协议引用 | 保留；除非明确取消 `python -m` 启动方式 |
| `credential_lifecycle` | 直接同名测试族：`tests/test_credential_lifecycle.py` | 否；但存在包内/工具/协议引用 | 保留待续，第四步再判定 |
| `dynsec_api` | 直接同名测试族：`tests/test_dynsec_api.py` | 否；但存在包内/工具/协议引用 | 保留待续，第四步再判定 |
| `service_identity_plan` | 直接同名测试族：`tests/test_service_identity_plan.py` | 否；但存在包内/工具/协议引用 | 保留待续，第四步再判定 |

### B2 node MQTT / isolated lab（10 个）

| 模块 | 测试引用核对 | 当前配置/外部引用 | 建议 |
|---|---|---|---|
| `node_firmware_mqtt_capability_gate` | 直接同名测试族：`tests/test_node_firmware_mqtt_capability_gate.py` | 是：当前正式 CLI | 保留待续，第四步再判定 |
| `node_mqtt_auth_fallback_model` | 直接同名测试族：`tests/test_node_mqtt_auth_fallback_model.py` | 是：当前正式 CLI | 保留待续，第四步再判定 |
| `node_mqtt_board_lab_broker` | 传递测试引用：`tests/test_node_mqtt_board_lab_contract.py` | 否；但存在包内/工具/协议引用 | 保留待续，第四步再判定 |
| `node_mqtt_board_lab_common` | 传递测试引用：`tests/test_node_mqtt_board_lab.py / test_node_mqtt_board_lab_native.py` | 否；但存在包内/工具/协议引用 | 保留待续，第四步再判定 |
| `node_mqtt_board_lab_matrix` | 传递测试引用：`tests/test_node_mqtt_board_lab_contract.py` | 否；但存在包内/工具/协议引用 | 保留待续，第四步再判定 |
| `node_mqtt_board_lab_mqtt` | 传递测试引用：`tests/test_node_mqtt_board_lab_contract.py` | 否；但存在包内/工具/协议引用 | 保留待续，第四步再判定 |
| `node_mqtt_board_lab_native_broker` | 传递测试引用：`tests/test_node_mqtt_board_lab_native.py` | 否；但存在包内/工具/协议引用 | 保留待续，第四步再判定 |
| `node_mqtt_isolated_lab` | 直接同名测试族：`tests/test_node_mqtt_isolated_lab.py` | 是：当前正式 CLI | 保留待续，第四步再判定 |
| `node_mqtt_private_mosquitto` | 直接同名测试族：`tests/test_node_mqtt_private_mosquitto.py` | 是：当前正式 CLI | 保留待续，第四步再判定 |
| `private_mosquitto_builder` | 直接同名测试族：`tests/test_private_mosquitto_builder.py` | 否；但存在包内/工具/协议引用 | 保留待续，第四步再判定 |

### B3 t1_broker_identity_*（25 个）

| 模块 | 测试引用核对 | 当前配置/外部引用 | 建议 |
|---|---|---|---|
| `t1_broker_identity_activation_authorization` | 直接同名测试族：`tests/test_t1_broker_identity_activation_authorization.py` | 是：当前正式 CLI | 保留待续，第四步再判定 |
| `t1_broker_identity_activation_checks` | 传递测试引用：`tests/activation authorization/readiness 测试族` | 否；但存在包内/工具/协议引用 | 保留待续，第四步再判定 |
| `t1_broker_identity_activation_handoff` | 直接同名测试族：`tests/test_t1_broker_identity_activation_handoff.py` | 是：当前正式 CLI | 保留待续，第四步再判定 |
| `t1_broker_identity_activation_readiness_authorization` | 直接同名测试族：`tests/test_t1_broker_identity_activation_readiness_authorization.py` | 是：当前正式 CLI | 保留待续，第四步再判定 |
| `t1_broker_identity_activation_readiness_bundle` | 直接同名测试族：`tests/test_t1_broker_identity_activation_readiness_bundle.py` | 是：当前正式 CLI | 保留待续，第四步再判定 |
| `t1_broker_identity_activation_readiness_transaction_plan` | 直接同名测试族：`tests/test_t1_broker_identity_activation_readiness_transaction_plan.py` | 是：当前正式 CLI | 保留待续，第四步再判定 |
| `t1_broker_identity_activation_transaction` | 直接同名测试族：`tests/test_t1_broker_identity_activation_transaction.py` | 是：当前正式 CLI | 保留待续，第四步再判定 |
| `t1_broker_identity_host_replica_adapters` | 直接同名测试族：`tests/test_t1_broker_identity_host_replica_adapters.py` | 是：当前正式 CLI | 保留待续，第四步再判定 |
| `t1_broker_identity_host_replica_fault_matrix` | 直接同名测试族：`tests/test_t1_broker_identity_host_replica_fault_matrix.py` | 是：当前正式 CLI | 保留待续，第四步再判定 |
| `t1_broker_identity_isolated_adapters` | 传递测试引用：`tests/test_t1_broker_identity_isolated_transaction.py` | 否；但存在包内/工具/协议引用 | 保留待续，第四步再判定 |
| `t1_broker_identity_isolated_helpers` | 传递测试引用：`tests/test_t1_broker_identity_isolated_transaction.py` | 否；但存在包内/工具/协议引用 | 保留待续，第四步再判定 |
| `t1_broker_identity_isolated_transaction` | 直接同名测试族：`tests/test_t1_broker_identity_isolated_transaction.py` | 是：当前正式 CLI | 保留待续，第四步再判定 |
| `t1_broker_identity_live_mount_gate` | 直接同名测试族：`tests/test_t1_broker_identity_live_mount_gate.py` | 是：当前正式 CLI | 保留待续，第四步再判定 |
| `t1_broker_identity_postactivation_audit` | 直接同名测试族：`tests/test_t1_broker_identity_postactivation_audit.py` | 是：当前正式 CLI | 保留待续，第四步再判定 |
| `t1_broker_identity_preactivation_fresh_evidence` | 直接同名测试族：`tests/test_t1_broker_identity_preactivation_fresh_evidence.py` | 是：当前正式 CLI | 保留待续，第四步再判定 |
| `t1_broker_identity_preactivation_gate` | 直接同名测试族：`tests/test_t1_broker_identity_preactivation_gate.py` | 是：当前正式 CLI | 保留待续，第四步再判定 |
| `t1_broker_identity_production_activation_orchestrator` | 直接同名测试族：`tests/test_t1_broker_identity_production_activation_orchestrator.py` | 否；但存在包内/工具/协议引用 | 保留待续，第四步再判定 |
| `t1_broker_identity_production_adapter_skeleton` | 直接同名测试族：`tests/test_t1_broker_identity_production_adapter_skeleton.py` | 是：当前正式 CLI | 保留待续，第四步再判定 |
| `t1_broker_identity_production_broker_driver` | 直接同名测试族：`tests/test_t1_broker_identity_production_broker_driver.py` | 否；但存在包内/工具/协议引用 | 保留待续，第四步再判定 |
| `t1_broker_identity_production_driver_contract` | 直接同名测试族：`tests/test_t1_broker_identity_production_driver_contract.py` | 是：当前正式 CLI | 保留待续，第四步再判定 |
| `t1_broker_identity_production_driver_preflight` | 直接同名测试族：`tests/test_t1_broker_identity_production_driver_preflight.py` | 是：当前正式 CLI | 保留待续，第四步再判定 |
| `t1_broker_identity_production_executor_contract` | 直接同名测试族：`tests/test_t1_broker_identity_production_executor_contract.py` | 是：当前正式 CLI | 保留待续，第四步再判定 |
| `t1_broker_identity_production_transaction_adapter_contract` | 直接同名测试族：`tests/test_t1_broker_identity_production_transaction_adapter_contract.py` | 是：当前正式 CLI | 保留待续，第四步再判定 |
| `t1_broker_identity_production_transaction_adapters` | 直接同名测试族：`tests/test_t1_broker_identity_production_transaction_adapters.py` | 否；但存在包内/工具/协议引用 | 保留待续，第四步再判定 |
| `t1_broker_identity_runtime_binding_manifest` | 直接同名测试族：`tests/test_t1_broker_identity_runtime_binding_manifest.py` | 是：当前正式 CLI | 保留待续，第四步再判定 |

### B4 T1 migration / shadow（7 个）

| 模块 | 测试引用核对 | 当前配置/外部引用 | 建议 |
|---|---|---|---|
| `t1_client_migration_audit` | 直接同名测试族：`tests/test_t1_client_migration_audit.py` | 是：当前正式 CLI | 保留待续，第四步再判定 |
| `t1_migration_package` | 直接同名测试族：`tests/test_t1_migration_package.py` | 是：当前正式 CLI | 保留待续，第四步再判定 |
| `t1_migration_rehearsal` | 直接同名测试族：`tests/test_t1_migration_rehearsal.py` | 是：当前正式 CLI | 保留待续，第四步再判定 |
| `t1_migration_stage` | 直接同名测试族：`tests/test_t1_migration_stage.py` | 是：当前正式 CLI | 保留待续，第四步再判定 |
| `t1_migration_stage_rehearsal` | 直接同名测试族：`tests/test_t1_migration_stage_rehearsal.py` | 是：当前正式 CLI | 保留待续，第四步再判定 |
| `t1_shadow` | 直接同名测试族：`tests/test_t1_shadow.py` | 是：当前正式 CLI | 保留待续，第四步再判定 |
| `t1_shadow_services` | 直接同名测试族：`tests/test_t1_shadow_services.py` | 是：当前正式 CLI | 保留待续，第四步再判定 |

### B5 Home Assistant / node 迁移材料（6 个）

| 模块 | 测试引用核对 | 当前配置/外部引用 | 建议 |
|---|---|---|---|
| `t1_homeassistant_mqtt_legacy_evidence_bridge` | 直接同名测试族：`tests/test_t1_homeassistant_mqtt_legacy_evidence_bridge.py` | 是：当前正式 CLI | 保留待续，第四步再判定 |
| `t1_homeassistant_mqtt_postactivation_handoff` | 直接同名测试族：`tests/test_t1_homeassistant_mqtt_postactivation_handoff.py` | 是：当前正式 CLI | 保留待续，第四步再判定 |
| `t1_homeassistant_mqtt_reconfigure_handoff` | 直接同名测试族：`tests/test_t1_homeassistant_mqtt_reconfigure_handoff.py` | 是：当前正式 CLI | 保留待续，第四步再判定 |
| `t1_homeassistant_mqtt_target_gate` | 直接同名测试族：`tests/test_t1_homeassistant_mqtt_target_gate.py` | 是：当前正式 CLI | 保留待续，第四步再判定 |
| `t1_node_mqtt_migration_readiness_evidence` | 直接同名测试族：`tests/test_t1_node_mqtt_migration_readiness_evidence.py` | 是：当前正式 CLI | 保留待续，第四步再判定 |
| `t1_provisioning_control_identity_recovery` | 直接同名测试族：`tests/test_t1_provisioning_control_identity_recovery.py` | 否；但存在包内/工具/协议引用 | 保留待续，第四步再判定 |

### B6 t1_manager_identity_*（33 个）

| 模块 | 测试引用核对 | 当前配置/外部引用 | 建议 |
|---|---|---|---|
| `t1_manager_identity_fresh_chain_preparation` | 直接同名测试族：`tests/test_t1_manager_identity_fresh_chain_preparation.py` | 是：当前正式 CLI | 保留待续，第四步再判定 |
| `t1_manager_identity_migration_authorization` | 直接同名测试族：`tests/test_t1_manager_identity_migration_authorization.py` | 是：当前正式 CLI | 保留待续，第四步再判定 |
| `t1_manager_identity_migration_execution_authorization` | 直接同名测试族：`tests/test_t1_manager_identity_migration_execution_authorization.py` | 是：当前正式 CLI | 保留待续，第四步再判定 |
| `t1_manager_identity_migration_execution_preparation` | 直接同名测试族：`tests/test_t1_manager_identity_migration_execution_preparation.py` | 是：当前正式 CLI | 保留待续，第四步再判定 |
| `t1_manager_identity_migration_execution_preparation_capture` | 传递测试引用：`tests/test_t1_manager_identity_migration_execution_preparation.py` | 否；但存在包内/工具/协议引用 | 保留待续，第四步再判定 |
| `t1_manager_identity_migration_execution_preparation_capture_archive` | 传递测试引用：`tests/test_t1_manager_identity_migration_execution_preparation.py` | 否；但存在包内/工具/协议引用 | 保留待续，第四步再判定 |
| `t1_manager_identity_migration_execution_preparation_capture_inventory` | 传递测试引用：`tests/test_t1_manager_identity_migration_execution_preparation.py` | 否；但存在包内/工具/协议引用 | 保留待续，第四步再判定 |
| `t1_manager_identity_migration_execution_preparation_common` | 传递测试引用：`tests/test_t1_manager_identity_migration_execution_preparation.py` | 否；但存在包内/工具/协议引用 | 保留待续，第四步再判定 |
| `t1_manager_identity_migration_execution_preparation_constants` | 传递测试引用：`tests/test_t1_manager_identity_migration_execution_preparation.py` | 否；但存在包内/工具/协议引用 | 保留待续，第四步再判定 |
| `t1_manager_identity_migration_execution_preparation_io` | 传递测试引用：`tests/test_t1_manager_identity_migration_execution_preparation.py` | 否；但存在包内/工具/协议引用 | 保留待续，第四步再判定 |
| `t1_manager_identity_migration_execution_preparation_rollback` | 传递测试引用：`tests/test_t1_manager_identity_migration_execution_preparation.py` | 否；但存在包内/工具/协议引用 | 保留待续，第四步再判定 |
| `t1_manager_identity_migration_execution_preparation_validation` | 传递测试引用：`tests/test_t1_manager_identity_migration_execution_preparation.py` | 否；但存在包内/工具/协议引用 | 保留待续，第四步再判定 |
| `t1_manager_identity_migration_execution_preparation_verify` | 传递测试引用：`tests/test_t1_manager_identity_migration_execution_preparation.py` | 否；但存在包内/工具/协议引用 | 保留待续，第四步再判定 |
| `t1_manager_identity_migration_execution_preparation_verify_records` | 传递测试引用：`tests/test_t1_manager_identity_migration_execution_preparation.py` | 否；但存在包内/工具/协议引用 | 保留待续，第四步再判定 |
| `t1_manager_identity_migration_execution_transaction_gate` | 直接同名测试族：`tests/test_t1_manager_identity_migration_execution_transaction_gate.py` | 是：当前正式 CLI | 保留待续，第四步再判定 |
| `t1_manager_identity_migration_failure_diagnostics` | 直接同名测试族：`tests/test_t1_manager_identity_migration_failure_diagnostics.py` | 是：当前正式 CLI | 保留待续，第四步再判定 |
| `t1_manager_identity_migration_host_replica_adapters` | 直接同名测试族：`tests/test_t1_manager_identity_migration_host_replica_adapters.py` | 是：当前正式 CLI | 保留待续，第四步再判定 |
| `t1_manager_identity_migration_legacy_review_bridge` | 直接同名测试族：`tests/test_t1_manager_identity_migration_legacy_review_bridge.py` | 是：当前正式 CLI | 保留待续，第四步再判定 |
| `t1_manager_identity_migration_live_runtime_gate` | 直接同名测试族：`tests/test_t1_manager_identity_migration_live_runtime_gate.py` | 是：当前正式 CLI | 保留待续，第四步再判定 |
| `t1_manager_identity_migration_postrollback_audit` | 直接同名测试族：`tests/test_t1_manager_identity_migration_postrollback_audit.py` | 是：当前正式 CLI | 保留待续，第四步再判定 |
| `t1_manager_identity_migration_preclaim_candidate` | 直接同名测试族：`tests/test_t1_manager_identity_migration_preclaim_candidate.py` | 否；但存在包内/工具/协议引用 | 保留待续，第四步再判定 |
| `t1_manager_identity_migration_preparation` | 直接同名测试族：`tests/test_t1_manager_identity_migration_preparation.py` | 是：当前正式 CLI | 保留待续，第四步再判定 |
| `t1_manager_identity_migration_production_driver_contract` | 直接同名测试族：`tests/test_t1_manager_identity_migration_production_driver_contract.py` | 是：当前正式 CLI | 保留待续，第四步再判定 |
| `t1_manager_identity_migration_production_driver_replica_matrix` | 直接同名测试族：`tests/test_t1_manager_identity_migration_production_driver_replica_matrix.py` | 是：当前正式 CLI | 保留待续，第四步再判定 |
| `t1_manager_identity_migration_production_execution_packet` | 直接同名测试族：`tests/test_t1_manager_identity_migration_production_execution_packet.py` | 否；但存在包内/工具/协议引用 | 保留待续，第四步再判定 |
| `t1_manager_identity_migration_production_host_adapters` | 直接同名测试族：`tests/test_t1_manager_identity_migration_production_host_adapters.py` | 否；但存在包内/工具/协议引用 | 保留待续，第四步再判定 |
| `t1_manager_identity_migration_production_integration` | 传递测试引用：`tests/production orchestrator/runtime 测试族` | 否；但存在包内/工具/协议引用 | 保留待续，第四步再判定 |
| `t1_manager_identity_migration_production_orchestrator` | 直接同名测试族：`tests/test_t1_manager_identity_migration_production_orchestrator.py` | 否；但存在包内/工具/协议引用 | 保留待续，第四步再判定 |
| `t1_manager_identity_migration_production_retained_recovery` | 直接同名测试族：`tests/test_t1_manager_identity_migration_production_retained_recovery.py` | 否；但存在包内/工具/协议引用 | 保留待续，第四步再判定 |
| `t1_manager_identity_migration_production_runtime_probe` | 直接同名测试族：`tests/test_t1_manager_identity_migration_production_runtime_probe.py` | 否；但存在包内/工具/协议引用 | 保留待续，第四步再判定 |
| `t1_manager_identity_migration_production_transaction_adapter_contract` | 直接同名测试族：`tests/test_t1_manager_identity_migration_production_transaction_adapter_contract.py` | 是：当前正式 CLI | 保留待续，第四步再判定 |
| `t1_manager_identity_migration_stdlib_mqtt` | 直接同名测试族：`tests/test_t1_manager_identity_migration_stdlib_mqtt.py` | 是：当前正式 CLI | 保留待续，第四步再判定 |
| `t1_manager_runtime_secret_ownership` | 直接同名测试族：`tests/test_t1_manager_runtime_secret_ownership.py` | 否；但存在包内/工具/协议引用 | 保留待续，第四步再判定 |

### B 类总体判断

- B 类大量模块属于已经被正式 CLI 暴露、但不在本次五入口批准集合中的运维/迁移工具。
- 仅删除模块而不同时移除 CLI、`tools/run_*`、workflow 和协议/状态引用，会造成已安装命令损坏。
- 这些模块必须在第四步按业务簇确认“继续维护、移出正式包、归档到 experiments，或完整废弃”。

## 5. C 类：明显的多版本/同功能变体

共 `11` 个模块，分 5 组。C 类成员也有测试或配置引用，本阶段不删除。

### C1 Home Assistant MQTT 凭据轮换

- 成员：`t1_homeassistant_mqtt_credential_rotation`、`t1_homeassistant_mqtt_credential_rotation_v2`
- 当前最新/活动判断：`t1_homeassistant_mqtt_credential_rotation_v2`
- 依据：文件名版本号更高，且对应 v2 协议和专属测试存在；但当前 pyproject 未直接暴露该组，需在第三步比较覆盖关系。
- `t1_homeassistant_mqtt_credential_rotation`：直接同名测试族：`tests/test_t1_homeassistant_mqtt_credential_rotation.py`；非当前 CLI 目标。
- `t1_homeassistant_mqtt_credential_rotation_v2`：直接同名测试族：`tests/test_t1_homeassistant_mqtt_credential_rotation_v2.py`；非当前 CLI 目标。

### C2 Home Assistant MQTT 迁移材料证据

- 成员：`t1_homeassistant_mqtt_migration_material_evidence`、`t1_homeassistant_mqtt_migration_material_evidence_v2`
- 当前最新/活动判断：`t1_homeassistant_mqtt_migration_material_evidence_v2`
- 依据：当前 `pyproject.toml` 的正式 CLI 明确指向 `_v2`，这是最强的现行版本依据。
- `t1_homeassistant_mqtt_migration_material_evidence`：直接同名测试族：`tests/test_t1_homeassistant_mqtt_migration_material_evidence.py`；非当前 CLI 目标。
- `t1_homeassistant_mqtt_migration_material_evidence_v2`：直接同名测试族：`tests/test_t1_homeassistant_mqtt_migration_material_evidence_v2.py`；当前 CLI 目标。

### C3 manager 提交后连续性审计

- 成员：`t1_manager_identity_postcommit_continuity_audit`、`t1_manager_identity_postcommit_continuity_audit_v2`、`t1_manager_identity_postcommit_continuity_audit_v3`
- 当前最新/活动判断：`t1_manager_identity_postcommit_continuity_audit_v3`
- 依据：当前正式 CLI 明确指向 `_v3`；v1/v2/v3 均有专属测试，第三步必须比较测试价值差异。
- `t1_manager_identity_postcommit_continuity_audit`：直接同名测试族：`tests/test_t1_manager_identity_postcommit_continuity_audit.py`；非当前 CLI 目标。
- `t1_manager_identity_postcommit_continuity_audit_v2`：直接同名测试族：`tests/test_t1_manager_identity_postcommit_continuity_audit_v2.py`；非当前 CLI 目标。
- `t1_manager_identity_postcommit_continuity_audit_v3`：直接同名测试族：`tests/test_t1_manager_identity_postcommit_continuity_audit_v3.py`；当前 CLI 目标。

### C4 T1 迁移就绪检查

- 成员：`t1_migration_readiness`、`t1_migration_readiness_live`
- 当前最新/活动判断：`t1_migration_readiness_live`
- 依据：当前 `greenhouse-manager-t1-migration-readiness` CLI 指向 `_live`；无后缀版本仍有测试，需要比较是否为模型层或旧实现。
- `t1_migration_readiness`：直接同名测试族：`tests/test_t1_migration_readiness.py`；非当前 CLI 目标。
- `t1_migration_readiness_live`：直接同名测试族：`tests/test_t1_migration_readiness_live.py`；当前 CLI 目标。

### C5 node MQTT board-lab 后端

- 成员：`node_mqtt_board_lab`、`node_mqtt_board_lab_native`
- 当前最新/活动判断：暂不能选定单一最新版本
- 依据：`node_mqtt_board_lab` 与 `_native` 各自拥有正式 CLI 和测试，可能是两个并行后端而非简单新旧替代；第三步不得直接删旧。
- `node_mqtt_board_lab`：直接同名测试族：`tests/test_node_mqtt_board_lab.py`；当前 CLI 目标。
- `node_mqtt_board_lab_native`：直接同名测试族：`tests/test_node_mqtt_board_lab_native.py`；当前 CLI 目标。

## 6. 非 Python 引用结论

- 当前 `pyproject.toml` 的 60 个脚本入口是最重要的非 Python 引用；其中 55 个不属于用户指定五入口。
- 历史 T1、broker、manager identity 模块普遍配有 `host/greenhouse-manager/tools/run_*` 启动脚本。
- 多个模块还被 `.github/workflows/`、`protocols/pairing/`、`docs/handoffs/`、`docs/status/` 引用。
- 所以“从五入口不可达”不能直接解释为“仓库孤立”；删除前必须同步决定这些外部入口和证据文件的处置。

## 7. 第一步结论与下一门

```text
CLEANUP_BASELINE_ANALYSIS=COMPLETE
REPOSITORY_MODIFIED=false
FILES_DELETED=0
TAG_CREATED=false
PYTHON_FILES_INCLUDING_INIT=117
OPERATIONAL_MODULES_EXCLUDING_INIT=116
REACHABLE_FROM_APPROVED_FIVE=20
UNREACHABLE_FROM_APPROVED_FIVE=96
A_CLASS_SAFE_DELETE=0
B_CLASS_DECISION_REQUIRED=85
C_CLASS_VARIANT_MEMBERS=11
```

下一步在人工确认前保持关闭。若确认进入第二步，将先重新核验 `main`、工作区 clean、创建独立清理分支，并在任何删除前创建 `pre-cleanup-2026-07-24` 回滚 tag。由于 A 类为 0，第二步预计只形成“无删除闭环”，不会擅自把 B/C 类移入 A 类。
