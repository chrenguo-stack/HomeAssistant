# N3-W T1 S20 clean-product 三服务凭据绑定修补设计（2026-10-10）

## 1. 上游结论

S19 隔离身份/ACL 验收保持 `CLOSED_PASS`。S20 fresh source preflight 在生产账号创建前 fail-closed：

```text
S20_PREFLIGHT_RESULT=FAIL_CLOSED
S20_FAILURE_CLASS=SOURCE
SOURCE_DEFECT_PROVEN=false
PRODUCTION_CLIENT_CREATION=false
PRODUCTION_BROKER_STARTED=false
BOARD_ACCESS=false
```

本修补只处理“clean-product 三服务凭据如何从生成端安全交给实际消费者”的源码/部署合同，不修改 T1 live runtime，不创建生产账号，不启动 Broker，不开放 8883，不生成 node 身份。

## 2. 冻结产品关系

生产服务身份仍只有三类：

```text
provisioning
manager
homeassistant
```

其中 Provisioning 不是第四个容器。当前产品源码已经证明它由 greenhouse-manager 的 N3-W pairing runtime 消费，用于首次配对时向 Broker 创建真实 node 身份。

因此 clean-product 的实际消费者关系冻结为：

```text
Manager MQTT service credential
  -> greenhouse-manager process
  -> GH_MQTT_PASSWORD_FILE

Provisioning DynSec credential
  -> same greenhouse-manager process
  -> GH_N3W_PROVISIONING_PASSWORD_FILE

Home Assistant MQTT credential
  -> Home Assistant MQTT integration
  -> official MQTT config-flow/config-entry
```

真实 node credential 继续只允许 Gate F 按真实节点生成：

```text
PRECREATE_NODE_CREDENTIAL=false
NODE_CREDENTIAL_COUNT_BEFORE_GATE_F=0
```

## 3. Manager + Provisioning 修补方向

新增 clean-product service credential bundle，只生成三服务身份，不复用旧 `t1_migration_package.py`。

bundle 必须生成三个彼此独立的随机密码文件：

```text
manager/password
provisioning/password
homeassistant/password
```

目录模式 0700，文件模式 0600，不输出秘密到 stdout、日志、GitHub、Compose environment 或 argv。

greenhouse-manager 使用两份不同的只读挂载：

```text
manager/password
  -> /run/secrets/gh_manager_mqtt_password
  -> GH_MQTT_PASSWORD_FILE

provisioning/password
  -> /run/secrets/gh_n3w_provisioning_mqtt_password
  -> GH_N3W_PROVISIONING_PASSWORD_FILE
```

Manager username/client ID 与 Provisioning username/client ID 继续来自 `service_identity_plan.py`，不另建第二套命名 authority。

正式 deployment apply 前必须 fresh 解析 exact Manager image/runtime UID/GID，再把两份 secret 的 owner 绑定到该运行身份；不得硬编码历史 UID/GID。

## 4. Home Assistant 边界

当前 repository 的历史迁移合同明确：

```text
official_config_flow_only=true
direct_storage_edit_forbidden=true
automatic_apply=false
```

Home Assistant 官方当前文档也把 Broker host/port/username/password/custom client ID 放在 MQTT integration 的 UI/config flow 中，而不是普通 YAML broker 配置。

因此本修补**不通过直接写 `.storage` 来伪造自动化闭环**。

clean-product bundle 可以安全持久保存 Home Assistant 独立 password，并生成不含密码正文的本地 handoff metadata；但在没有新的、被验证的官方自动消费路径之前：

```text
HA_FRESH_MQTT_AUTOMATIC_CONSUMER=CLOSED_FALSE
READY_FOR_REAL_SERVICE_IDENTITY_AUTHORIZATION=false
```

后续产品决策只有两类可接受路线：

1. 保留 Home Assistant 官方 MQTT config-flow，产品首次安装时允许一次受控 UI/onboarding 动作，但不能要求用户手工抄录明文密码；
2. 单独开发并验证一个受支持的自动 Home Assistant config-flow/bootstrap 路径，仍禁止直接编辑 `.storage`。

在该决策关闭前，不得为了“自动化”引入未受支持的 storage patch。

## 5. 本轮 source repair 范围

新增：

```text
host/greenhouse-manager/src/greenhouse_manager/ops/t1_clean_service_credential_bundle.py
host/greenhouse-manager/tests/ops/test_t1_clean_service_credential_bundle.py
```

必须证明：

- exactly three service credentials；
- zero node credentials；
- 三个密码独立生成；
- secret root/子目录 0700、文件 0600；
- Manager 与 Provisioning 两个不同 password-file target；
- Compose fragment 只做 read-only bind；
- environment metadata 不含密码值；
- Home Assistant handoff 明确 `automatic_apply=false` 与 `direct_storage_edit_forbidden=true`；
- manifest/report 不泄漏任何密码。

## 6. 本轮不做

```text
T1_RUNTIME_MUTATION=false
PRODUCTION_DYNSEC_MUTATION=false
PRODUCTION_CLIENT_CREATION=false
PRODUCTION_BROKER_START=false
HOST_8883_PUBLICATION=false
HOMEASSISTANT_STORAGE_EDIT=false
HOMEASSISTANT_CONFIG_FLOW_WRITE=false
BOARD_ACCESS=false
PR_MERGE=false
```

## 7. 预期关闭点

本轮源码修补 PASS 后只允许得到：

```text
MANAGER_CLEAN_PRODUCT_SECRET_BINDING_SOURCE=PASS
PROVISIONING_CLEAN_PRODUCT_SECRET_BINDING_SOURCE=PASS
NODE_PRECREATION_GUARD=PASS
HA_PRIVATE_CREDENTIAL_STAGING_SOURCE=PASS
HA_AUTOMATIC_CONSUMER=OPEN_DECISION
READY_FOR_REAL_SERVICE_IDENTITY_AUTHORIZATION=false
```

下一门应先解决 Home Assistant fresh-product credential consumer；在此之前不进入生产三服务账号写入。
