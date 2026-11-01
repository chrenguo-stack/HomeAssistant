# N3-W T1 S20 生产服务账号/密码交付只读预检（2026-10-10）

## 冻结的上游验收

S19 隔离服务身份与权限设计验收已 CLOSED_PASS：R1 静态三服务 10/17/9 ACL、R3 Provisioning MQTT DynSec 控制查询、R5 节点→Manager→HA 正向投递、R6A 正确 ID/错误 ID/匿名拒绝、R6B 跨主题不合法发布/订阅及测试专用允许订阅但默认接收拒绝全部通过。R2/R4 旧失败按测试可观察性/管理员错作业务发送端历史留档，没有抹除。

截至 R6B 现场输出，生产 `/var/lib/n3wfc4-broker/dynamic-security.json` 的现用 SHA256 保持 `94f3c0a3dbed90f3d2a3e96696dba8bed8093194903aeed106559090764d1ad5`，S18 私有备份原数据 SHA256 `93c751a788200498869de39a3218a82de53e5cd3d29170360ea55959d0af85da`，host TCP/8883 未发布，正式 Broker 未启动、45 volumes/guard 不变，临时数据已删除。三生产服务账号尚未写入，不应假装存在。

## 主线源码的可用能力（只读确认）

- `host/greenhouse-manager/src/greenhouse_manager/runtime/service_identity_plan.py`：定义 provisioning/manager/homeassistant 的独立 username、client ID、角色/ACL/随机密码；绑定 main blob SHA `19d95cfe59c12ee0abeaddf8c777fb663a5bd399`。
- `host/greenhouse-manager/src/greenhouse_manager/runtime/dynsec_api.py`：包含按规划创建 role、client 和默认 ACL 的 DynSec 控制命令，main blob SHA `6a75b60de88689524ec3b6d0105e0b3f66f5a682`。
- `host/greenhouse-manager/src/greenhouse_manager/runtime/config.py`：支持 Manager MQTT 的 `GH_MQTT_PASSWORD_FILE` 与独立 Provisioning 的 `GH_N3W_PROVISIONING_PASSWORD_FILE`，并处理 `GH_MQTT_USERNAME`、`GH_MQTT_CLIENT_ID`、`GH_N3W_PROVISIONING_USERNAME`、`GH_N3W_PROVISIONING_CLIENT_ID`；main blob SHA `fabb2affa9fb8ce76aa8ed94ce4f4ea9745402cd`。
- `protocols/pairing/gh-t1-manager-runtime-secret-ownership-gate-v1.md` main blob SHA `02b001967c7356adc0d6adee53854f3fb3643bb7`：Manager 必须使用与其实际运行 UID/GID 匹配、0600、只读挂载到 `/run/secrets/gh_manager_mqtt_password` 的文件；内联 `GH_MQTT_PASSWORD` 必须为空，并先用运行镜像下的 `--check-config`/固定 fallback 仅做只读验证。此为曾有迁移现场的已归档安全约束，fresh T1 部署仍需实际 image/Compose/UID 映射新鲜验证，不能直接宣称旧方案已部署。
- 发现历史 `host/greenhouse-manager/src/greenhouse_manager/ops/t1_migration_package.py` main blob SHA `3714a63f13f38f3f82a5f6c54a274ccebc23a3ca` 的旧迁移材料生成**三服务 + 一个 node 账号**。它不能不加修改用于 clean-product 首次配对 T1：Node 仍须首次 Gate F 后按实体逐节点生成，不允许预置共享或假节点身份。
- 仓库存在 Home Assistant MQTT 凭据轮换相关的测试，但截至本门只读源码检查，**尚未确认 fresh T1 的 HA 运行时实际秘密文件挂载/运行 UID/消费位置和精确 deployment binding**；此为待验事实，不是断言 HA 功能缺失。

## S20 进入生产账号创建前必须确定的 5 个条件

1. 真实 Manager 容器/image 版本、运行 UID、Manager MQTT 和 Provisioning **两套分离密码文件**的 0600 owner、只读 mount 和运行时读取路径，且无生产 plaintext env / argv。
2. Home Assistant 真实运行时（非旧迁移容器）的 MQTT 凭据创建、保存、消费和恢复路径；不依赖在 Broker 建账号之后手工把密码抄入 UI。
3. 账号/角色与持久化目录按配置的唯一责任方，密钥生成后只在受保护文件中一次写入，断电和容器重建后不丢失。
4. 更新真实 DynSec 前、后精确备份、单独 staging、失败 STOP、清晰回滚/继续边界；不复用历史迁移工具自动生成 node；admin 原身份与默认拒绝必须保留。
5. 正式启动 Broker/TLS/8883 的安全闸门独立于三服务账号写入门：可信且来源可证明的镜像、证书/主机名、受控 Compose 部署、guard、TLS 管理与实际客户端收发均须另行验证。

## 当前只读门结论

已有 Manager 文件读取机制、Provisioning 独立文件接口、三角色生成源和隔离 ACL 行为证据；生产运行时 credential handoff **尚未完成完整闭环绑定**，不能现在直接创建三服务真实账号。下一步仅做精确生产部署文件、Manager/HA runtime secret ownership 和最新 T1 环境的 source-to-runtime read-only check，确认三个密码各自由哪个消费者接收。若发现缺失先以源代码/部署设计做有限修补并测试，而非直接在 T1 投放凭据。

```text
S19_ISOLATED_ACL_ACCEPTANCE=CLOSED_PASS
S20_GATE=PRODUCTION_THREE_SERVICE_SECRET_HANDOFF_PREFLIGHT
S20_SCOPE=SOURCE_AND_T1_READ_ONLY
S20_PRODUCTION_CLIENT_CREATION=false
S20_PRODUCTION_BROKER_START=false
S20_HOST_8883_PUBLICATION=false
S20_BOARD_ACCESS=false
PR541=OPEN_DRAFT
```


## 2026-10-10 fresh source rebind closure

本轮按 formal handoff 的 S20 只读合同重新绑定 exact main、PR #541 与当前生产源码。源码侧首先出现阻断，因此按“第一处 substantive mismatch 即 STOP”规则，没有继续要求 T1 SSH 现场取证，也没有执行任何生产写入。

已证明：

- exact main 仍为 `d423211b6196c2f2f0f01dff072c4f877fbe58ee`；本轮 source rebind 时 PR #541 为 OPEN DRAFT，HEAD `9c55ee465668d822369a8e61a5d88d1ed37fe1fd`，相对 main ahead 83 / behind 0。
- `service_identity_plan.py` 继续定义 Provisioning、Manager、Home Assistant 三个独立服务身份与随机密码；`config.py` 继续支持 Manager 的 `GH_MQTT_PASSWORD_FILE` 和独立的 `GH_N3W_PROVISIONING_PASSWORD_FILE`。
- `n3w_simplified_product_runtime.py` 证明 Provisioning 身份由 Manager 产品运行时实际消费，用于节点身份动态创建；它不是第四个独立服务容器。
- 历史 Manager migration 路线具有 `/run/secrets/gh_manager_mqtt_password` 的 0600 / 只读挂载合同，但当前 clean-product fresh deployment 尚无冻结的 Manager production image、运行 UID/GID 与两份独立密码文件的最终 Compose/runtime binding。
- Home Assistant 历史迁移源码能够生成敏感的 MQTT reconfigure handoff，并要求走 Home Assistant 官方 MQTT Reconfigure；该路径明确 `automatic_apply=false`、需要操作者动作。它不能证明当前 fresh-product T1 已具有自动生成、持久保存、自动消费并在容器重建后恢复的 Home Assistant 生产凭据闭环。
- 当前 PR #541 没有加入一份能够把 Manager、Provisioning 和 Home Assistant 三条凭据消费链完整冻结下来的 fresh production deployment package；历史迁移包还会同时生成一个 node 身份，因此仍禁止直接复用到 Gate F 前的 clean-product T1。

因此本门没有达到“全部三个生产消费者 exact proven”的 PASS 条件。该结果不推翻 S19，也不证明 Broker/Manager 业务逻辑有产品缺陷；它证明的是 **生产部署与秘密交付的 source-to-runtime binding 仍不完整**。

```text
=== N3W T1 S20 SERVICE CREDENTIAL HANDOFF READONLY CLOSURE ===
EXECUTION_ID=N3W_T1_S20_PRODUCTION_THREE_SERVICE_CREDENTIAL_HANDOFF_AND_DEPLOYMENT_PREFLIGHT
AUTHORIZATION=READ_ONLY
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
MAIN_EXACT_REBIND=PASS:d423211b6196c2f2f0f01dff072c4f877fbe58ee
PR541_STATE_AND_EXACT_HEAD=PASS:OPEN_DRAFT@9c55ee465668d822369a8e61a5d88d1ed37fe1fd
SOURCE_PLAN_BOUND=PASS
T1_HOST_FRESH_READONLY_REBIND=NOT_EXECUTED_SOURCE_GAP_STOP
ARMBIAN_SSH_DOCKER_GUARDS_PRESERVED=NOT_RECHECKED_THIS_GATE
DOCKER_VOLUMES_45_PRESERVED=NOT_RECHECKED_THIS_GATE
TWO_PROJECT_NETWORKS_EMPTY=NOT_RECHECKED_THIS_GATE
GUARD_FIRST_JUMPS_LAST_DROP=NOT_RECHECKED_THIS_GATE
REAL_DYNSEC_SHA_MATCH=NOT_RECHECKED_THIS_GATE
S18_BACKUP_SHA_MATCH=NOT_RECHECKED_THIS_GATE
BROKER_CONFIG_SHA_MATCH=NOT_RECHECKED_THIS_GATE
BROKER_STOPPED=LAST_S19_EVIDENCE_ONLY_NOT_FRESH_RECHECKED
HOST_8883_NOT_PUBLISHED=LAST_S19_EVIDENCE_ONLY_NOT_FRESH_RECHECKED
MANAGER_ROLE_AND_CLIENT_ID_BOUND=PASS_SOURCE
MANAGER_RUNTIME_UID_SECRET_FILE_MOUNT_CONSUMER=SOURCE_GAP_FRESH_DEPLOYMENT_UNBOUND
PROVISIONING_ROLE_AND_CLIENT_ID_BOUND=PASS_SOURCE
PROVISIONING_SEPARATE_SECRET_FILE_CONSUMER=SOURCE_GAP_FRESH_DEPLOYMENT_UNBOUND
HA_ROLE_AND_CLIENT_ID_BOUND=PASS_SOURCE
HA_FRESH_MQTT_SECRET_FILE_AND_INTEGRATION_CONSUMER=SOURCE_GAP_ONLY_HISTORICAL_OPERATOR_RECONFIGURE_PATH
SECRETS_READ=false
PRODUCTION_CLIENT_CREATION=false
PRODUCTION_BROKER_STARTED=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
SOURCE_DEFECT_PROVEN=false
S20_PREFLIGHT_RESULT=FAIL_CLOSED
S20_FAILURE_CLASS=SOURCE
READY_FOR_REAL_SERVICE_IDENTITY_AUTHORIZATION=false
NEXT_ROUTE=S20_SCOPED_MISSING_CONSUMER_OR_DEPLOYMENT_BINDING_REVIEW
STOP=true
=== END ===
```

下一步仍返回高阶模型做缺口收敛设计；不得把本次 FAIL_CLOSED 自动转换为生产账号创建、Broker 启动或 T1 mutation 授权。


## 2026-10-10 clean-product credential binding source repair progress

原 S20 preflight 的 `FAIL_CLOSED / SOURCE` 后，已完成第一轮 source repair candidate：

- 三服务 clean credential bundle：三密码独立、0600、Manager/Provisioning 两个不同 password-file、HA 独立 password + bootstrap metadata、Gate F 前 node credential 固定为 0；
- Home Assistant fresh-first-boot 路径：新增 `n3w_mqtt_bootstrap` custom integration，仅在 MQTT entry 为 0 时调用 HA 自身 MQTT config-flow；已有 entry 精确匹配则 no-op，否则 fail closed；不直接编辑 `.storage`；
- fresh Broker source 增加 authenticated 1883 listener；host deployment gate 只允许 `127.0.0.1:1883`，TLS/8883 继续 `0.0.0.0:8883` 与既有 KF-097 防护；
- clean deployment source gate 冻结最终三个容器服务和两个项目网络，校验 Manager/Provisioning/HA secret read-only mount 与 1883/8883 publication ownership；
- Home Assistant source candidate 绑定 stable `2026.10.0`，upstream MQTT config-flow blob `9181013edc6686b6ac482b4061b3f5e48ba4ff77`；OCI digest/ARM64 runtime 仍未绑定。

focused source CI 在 `6dd2476e7be0b3f31253309c091a1576cf017303` 已 PASS：N3W T1 deployment gate run `38028806480`、Broker ingress guard run `38028806459`、public safety run `38028806482`。

exact Home Assistant isolated runtime acceptance 已启动于 source head `af5cd031979bce091965468d587a361ee86ccf5f`，run `38028945518`；经过三次 assistant poll 仍为 IN_PROGRESS，因此按项目规则停止轮询。不得把 pending 写成 PASS。

完整进度 authority：

`docs/development/N3W_T1_S20_CLEAN_PRODUCT_CREDENTIAL_BINDING_SOURCE_REPAIR_PROGRESS_20261010.md`

```text
S19_ISOLATED_IDENTITY_AND_ACL_ACCEPTANCE=CLOSED_PASS
S20_SOURCE_REPAIR_CANDIDATE=IMPLEMENTED
S20_FOCUSED_SOURCE_CI=PASS
HA_ISOLATED_RUNTIME_CI=PENDING_NO_MORE_POLLING
READY_FOR_REAL_SERVICE_IDENTITY_AUTHORIZATION=false
PRODUCTION_CLIENT_CREATION=false
PRODUCTION_BROKER_STARTED=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
STOP=WAIT_FOR_HA_ISOLATED_CI_RESULT
```
