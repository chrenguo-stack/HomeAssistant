# N3-W P4 — 使用空白业务数据部署新版 Manager 的已批准技术路线（2026-10-09）

## 背景与状态

用户提出：当前旧 Manager 数据可能已没有继续保留于新系统的价值，是否可以**全新部署**以尽快继续首次配对，而不做历史配对/凭据/replay 迁移。

用户已明确同意**新 Manager 不继承旧设备历史配对关系**；本文件现为已选定技术方向，**不是生产停止、删除旧库、清理 Broker 或部署授权**。此前生产 R5 三来源冷备份、隔离恢复和原版 Manager 恢复仍然 CLOSED_PASS，不重复执行。所有 ESP32-C6 已长期断电且没有接入传感器；静默遥测检查不再阻断部署计划。

## 核心结论

在明确不要求旧节点保持原配对/凭据身份，并使用一块真正符合 clean-board 合同的板进行产品首次配对时，可以选择 **Manager-only 空白持久状态部署**。它在本项目目标上通常比“迁移 5 个历史身份、replay 高水位、credential generation、relay keys”更直接，也有利于测试首次登记路径。

但“全新 Manager”不等于“全新 T1 整机”：维持 T1 主机、原 Broker TLS8883/双网络/防火墙/证书、当前用于新 Manager 连接 Broker 的服务凭据和稳定 system identity 不变。不得清空 Broker 动态权限数据库、HA 历史实体或系统证书以冒充 Manager-only 初始化成功。Broker 中旧设备 MQTT 账号/ACL、retained state 可能仍存在；它们的清理需独立核实和另行批准。未清除的旧 Broker 残留不应被误宣称是「完整零历史生态」；旧设备重新上电时不保证可用且不得自动视作已配对。

## 最小改造流程（需另行授权才能在 T1 实施）

1. **准备阶段**：确认旧配对状态不再需要**在新 Manager 中延续**。复用精确 P4 ARM64 候选镜像 `n3w-p4-manager:3d86d6bfaf361dc3a3d7295d046f541a544d552d` 的现场构建与已通过的隔离 CLI/source guard；绑定当前 image ID、原容器六个真实 bind mount 与原 Broker 运行参数。不再重做三库业务语义迁移或冷备份完整演练。
2. **独立空目录**：为新 Manager 创建 3 个全新的互不嵌套、root 私有可持久化 RW 数据 Source（registration、n3w、relay-keys），与旧的全部真实 Source 完全隔离；保留相同容器 destination。三条 RO secret source 继续**原样只读**挂载。检查新 Manager 能够对空白 SQLite 注册、凭据生命周期、replay state 建表，relay key 机制按预期初始化；不得复制旧业务 SQLite 或旧 relay-keys。
3. **一次实际切换**：只针对 Manager，自动原子记录预状态。停止原容器，改名保留、不删除（及其旧数据），以现场实际 Docker inspect 同等运行参数创建并启动新版；Broker、HA、TLS、证书、N3W 系统授权不变。设置受监督的失败恢复路径和单一终端 PASS/STOP 报告。
4. **无节点阶段验收**：新版自身健康接口、pairing socket 和只读 P4 CLI 能力、空库 schema 与身份数初始化、到 Broker 的真实连接证据、Broker 本体未重启、原容器随时可恢复。ESP32 全部断电，所以不再要求无数据源情况下 replay 增长。
5. **失败回退**：停止并隔离新容器及**只属于新版本**的数据目录，恢复旧的 parked 原容器及其始终未经新版触碰的三 RW 原数据源。不可用历史 Compose 3 挂载重建旧容器。绝不以空白新库覆盖原库。
6. **首次配对阶段**：原 P4 preboot 五身份 SHA/计数是**旧 Manager 私有状态权威**，切为新空状态后不再是新的 baseline。必须在新 Manager 正常启动后从新空业务状态生成新的身份快照/绑定，更新 QR↔pending binder 的预期基线，保持 P4 setup-secret import 显式独立授权。不能拿旧 `5` 身份快照硬性要求新 Manager 有 5 个历史身份，也不能为求零身份清除旧 T1 备份。
7. **上线和清理**：旧备份和 parked 容器至少保留到产品首次正常启动/配对与回退窗口结束；旧 Broker 帐号、Home Assistant retained/实体污染或物理旧设备归属的清理另立专门计划，严格做范围和身份映射核对，不允许 `docker volume prune`、`docker system prune` 或直接重置 Broker。

## 相比原迁移方案省掉的工作

- 不必把旧 5 个身份和相关 pairing/session/replay/credential 逐条迁入新产品运行数据库。
- 不必检查新产品进程能否直接写旧数据库、如何兼容旧 schema 及原库回退写入。
- 不必在新的部署窗口为了迁移再次暂停旧 Manager 复制三库并比对业务状态。
- **仍必须保留**：旧容器/配置归档、候选 exact image 与 6 mount binding、独立数据目录、Broker 不变、自动 STOP/原版恢复、第一次新库初始化及新基线检查。

## 已确认的业务决策

用户确认允许放弃旧版 Manager 的历史配对关系。今后如果使用旧设备，需要执行独立授权的重新配对流程，不继承旧的 NODE_ID 和 MQTT credentials；历史上不符合 clean-board 资格的板子不能冒充全新产品板。真正替换 T1 Manager 仍需单独批准。

```text
DECISION=CLEAN_MANAGER_STATE_FRESH_DEPLOY_APPROVED
LEGACY_PAIRED_NODES_IN_NEW_MANAGER=DISCARDED_BY_USER_DECISION
BROKER_AND_T1_INFRASTRUCTURE=KEEP
OLD_MANAGER_AND_R5_BACKUP=KEEP_ROOT_PRIVATE
OLD_IDENTITY_PREBOOT_BINDING=REBASE_AFTER_FRESH_MANAGER
CANDIDATE_SOURCE=3d86d6bfaf361dc3a3d7295d046f541a544d552d
PRODUCT_RUNTIME_CLEAN_DEPLOY_SOURCE_DESIGN=SOURCE_CONTRACT_READY_EXECUTOR_PENDING
LIVE_MANAGER_REPLACEMENT_AUTHORIZED=false
BROKER_MUTATION=false
ESP32_FIRST_BOOT=false
```

## 2026-10-09 用户正式决策：采用全新 Manager 空白业务状态

**DECISION=APPROVED**：用户明确确认“同意放弃旧设备在 Manager 中的历史配对关系”。此确认专门授权**方案选择和对应 GitHub 源码/测试推进**，不等于授权清理旧 Broker 账号、擦除旧设备 NVS、删除旧库/旧容器、停止原 Manager、在生产 T1 安装新版或导入 Setup Secret。

```text
P4_DEPLOYMENT_DIRECTION=CLEAN_MANAGER_ONLY
LEGACY_MANAGER_REGISTRATION_MIGRATION=SKIPPED
LEGACY_MANAGER_CREDENTIAL_AND_REPLAY_MIGRATION=SKIPPED
NEW_REGISTRATION_IDENTITIES=0_EXPECTED_PREBOOT
NEW_CREDENTIAL_ASSIGNMENTS=0_EXPECTED_PREBOOT
NEW_REPLAY_SEEN=0_EXPECTED_PREBOOT
NEW_RELAY_KEY_DIR=EMPTY_EXPECTED_PREBOOT
PREVIOUS_FIVE_IDENTITY_SNAPSHOT=HISTORICAL_NOT_NEW_PREBOOT_AUTHORITY
OLD_MANAGER_AND_ALL_PRIVATE_BACKUPS=KEEP_UNMODIFIED
BROKER_DYNSEC_AND_RETAINED_STATE=CURRENT_EXISTING_NOT_FACTORY_RESET
SYSTEM_ID_AND_MANAGER_BROKER_TLS_IDENTITY=KEEP_UNCHANGED
BOARD_FIRST_PAIR_AND_SECRET_IMPORT=SEPARATE_EXPLICIT_AUTHORIZATION
LIVE_MANAGER_REPLACEMENT_AUTHORIZED=false
```

项目源码证据：PR #538 精确候选中 `RegistrationRegistry`、`CredentialLifecycleStore` 和 `ReplayRegistry` 在空白持久目录下均包含数据库建表流程。Node application-key 存储还要求新建私有目录由运行进程拥有，不能仅用 root 0700 随意创建再不经权限验证启动容器。新加 `fresh_state_contract.py` + `test_fresh_state_contract.py`（10 个合成场景）明确约束**三独立且没有任何文件的持久 RW 源**、旧库绝不被新版本使用、首次启动后注册/配对/credential/replay 关键表必须是新建的空表、relay key 目录为空，以及旧版 5 身份 baseline 不能被误当作新版 P4 的预启动身份基线。

**注意**：新产品 Manager 即使空白，既有 Broker DynSec 账号/ACL/retained 消息仍然存在。若未来重新使用历史板，其设备侧的旧配对配置并不会自动失效；必须通过单独授权和真实清理/重新配对流程处理，不能默默复用旧身份。原有 clean-board eligibility 合同（不能重用曾被禁止的历史 P4 板冒充干净板）继续有效。

下一实施门：编写精确候选镜像和原运行配置复制的**一次性 Manager-only 空白部署与旧容器原状态回退执行器**，完成 synthetic fail/recovery tests 后再唯一一次请求生产替换授权。不得将早期“三库历史迁移克隆”设计当作有效执行路线。

新 QR↔PENDING 绑定接口的兼容修改已在 `bridge_handoff.py` 中支持**显式零身份基线**，由 `bind_clean_terminal_projection` 拒绝带旧五身份历史集的快照。其原有五身份路径仍可用于只读历史测试，但不得复用在新 Manager。新增 3 个源端合成回归验证零身份绑定有效、旧五身份不能误入和假造历史数量被拦截；真实部署后的新空库基线仍必须绑定运行中唯一 Manager 的新只读快照并重新计算私有哈希，不能复用旧版五身份文件或凭据。
