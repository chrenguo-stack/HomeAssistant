# gh-t1-auth-migration-package-v1 T1 认证迁移包

状态：Draft / M2.4a  
关联：ADR-0002、`gh-dynsec-profile-v1`、`gh-t1-shadow-service-matrix-v1`、Issue #17

## 1. 前置门

只有真实 T1 快照服务身份候选同时满足以下条件后，才允许生成本迁移包：

- 使用真实回退包及其精确 Mosquitto image ID；
- 候选容器 `network=none`；
- retained canonical telemetry 恢复成功；
- node、manager、Home Assistant、provisioning 四身份矩阵通过；
- client ID 绑定、事务回滚、legacy anonymous 兼容均通过；
- 真实 `mosquitto` 与 `greenhouse-manager` 前后保持运行且重启次数不变；
- 无候选容器残留。

2026-07-12，以上 gate 已在真实 T1 对提交 `d64ec7103817c433a3a90e9512ffe9024ab3a3d1` 验证通过。

## 2. 目标

迁移包用于把已经验证的身份与 ACL 计划转换为一个本机私有、可校验、默认禁止执行的交接物。它包含：

1. Dynamic Security 默认 ACL、legacy anonymous 兼容角色以及四身份创建请求；
2. 一次性 bootstrap admin 密码初始化文件和客户端配置；
3. provisioning 客户端配置；
4. greenhouse-manager 的用户名、固定 client ID、密码文件及 Compose 挂载片段；
5. Home Assistant MQTT 配置项更新描述；
6. 节点 `gh-n1-a9f2f8` 的下一代 MQTT 凭据交接文件；
7. 有序迁移步骤和回退包绑定元数据。

生成迁移包不等于部署。任何文件均不得自动写入真实 Mosquitto、Home Assistant、manager、节点或运行中卷。

## 3. 生成入口

已安装 greenhouse-manager 时：

```bash
greenhouse-manager-t1-migration-package \
  /opt/greenhouse-m2-backups/greenhouse-t1-rollback-<timestamp>.tar.gz \
  /opt/greenhouse-m2-packages
```

T1 不需要安装 venv 或 pip，也可从仓库源码运行：

```bash
python3 host/greenhouse-manager/tools/run_t1_migration_package.py \
  /opt/greenhouse-m2-backups/greenhouse-t1-rollback-<timestamp>.tar.gz \
  /opt/greenhouse-m2-packages
```

输入回退包与输出目录都必须禁止 group/other 访问。输出归档固定为 `0600`。

## 4. 包格式

根 manifest：

```text
schema = gh.m2.t1-auth-migration/1
classification = secret-local-migration
portable_off_host = false
apply_enabled = false
current_services_modified = false
```

manifest 只保存身份名称、username、client ID、role、generation、文件长度和 SHA-256，不保存密码明文。高熵秘密文件的 SHA-256 仅用于本机完整性校验。

主要文件：

```text
manifest.json
README.txt
apply-plan.json
broker/dynsec-request.json
broker/mosquitto-plugin.conf
bootstrap/dynsec-password-init
bootstrap/admin-client.conf
provisioning/mosquitto-client.conf
provisioning/identity.json
manager/manager.env
manager/password
manager/compose-secret-fragment.yaml
homeassistant/mqtt-update.json
homeassistant/identity.json
node/<node_id>/mqtt-credentials.json
node/<node_id>/identity.json
rollback/plan.json
```

归档中所有成员均为普通文件且模式固定为 `0600`；禁止绝对路径、`..`、符号链接、设备文件和额外未登记成员。

## 5. 主机秘密布局

正式部署阶段的目标根目录为：

```text
/opt/greenhouse-secrets/mqtt
```

约束：

- 根目录及身份目录为 `0700`；
- 密码文件为 `0600`；
- 密码不得放入仓库 `.env`、Compose YAML、命令行 argv、Home Assistant 实体或日志；
- manager 通过只读挂载将密码放到 `/run/secrets/gh_manager_mqtt_password`；
- manager 使用 `GH_MQTT_PASSWORD_FILE` 读取密码；
- `GH_MQTT_PASSWORD` 与 `GH_MQTT_PASSWORD_FILE` 不得同时存在；
- 密码文件必须是绝对路径、普通非符号链接文件，且 group/other 无访问权限。

## 6. 迁移顺序

`apply-plan.json` 固定为禁用状态，并记录以下人工 gate：

1. 在保留 `allow_anonymous true` 的前提下安装 Dynamic Security 候选配置；
2. 使用 bootstrap admin 创建 legacy anonymous 兼容策略和四身份；
3. 使用 provisioning 身份重新验证 Dynamic Security 控制链路，然后移除 bootstrap admin；
4. 迁移 greenhouse-manager，并验证 ingress、canonical state、Discovery 和 retained 恢复；
5. 更新 Home Assistant MQTT 配置项，并验证原有实体身份与状态不变；
6. 向真实节点写入新凭据，并验证 RS485 土壤采集及离线本地功能不受影响；
7. 观察稳定性、断网恢复、重启恢复和回退可用性；
8. 只有全部客户端均完成认证后，才允许关闭 anonymous。

任何阶段失败都必须停止推进，不得跳过到关闭 anonymous。

## 7. Home Assistant 边界

`homeassistant/mqtt-update.json` 是秘密交接描述，不是可直接复制到 `.storage` 的补丁。后续执行器必须通过受支持的 Home Assistant 配置项更新路径完成迁移，并在操作前备份、操作后验证：

- MQTT 集成仍连接同一 Broker；
- client ID 与冻结身份一致；
- Discovery topic 和既有实体 unique ID 不变；
- 原有传感器、可用性和 retained 状态均正常。

禁止直接编辑运行中 Home Assistant 的 `.storage` 文件。

## 8. 节点边界

节点凭据交接文件只允许进入后续安全配对或受验证 OTA 流程。不得通过日志、MQTT retained 明文 Topic、LCD、Web UI 或普通 YAML 仓库分发密码。

节点迁移前必须保留旧 generation 的可验证回退路径；新 generation 验证失败时不得撤销旧凭据。

## 9. Bootstrap 管理员

bootstrap admin 仅用于首次加载 Dynamic Security 和创建 provisioning 身份。必须在 provisioning 连接、client ID 绑定和控制 API 均验证通过后删除或禁用，并清除：

- `dynsec-password-init`；
- bootstrap admin 客户端配置；
- 任何临时副本或终端历史中的秘密。

bootstrap admin 不得被 manager、Home Assistant 或节点复用。

## 10. 本阶段安全门

M2.4a 只允许：

- 生成和校验离线迁移包；
- 验证秘密不进入 manifest、stdout、异常和 Git；
- 验证 manager 可以从私有密码文件加载凭据；
- 生成后续迁移所需的禁用步骤和回退元数据。

M2.4a 明确禁止：

- 修改或重启真实 Broker、manager、Home Assistant 或节点；
- 将 Dynamic Security 插件写入真实 Mosquitto 配置；
- 创建真实账号或更改真实 ACL；
- 关闭 `allow_anonymous true`；
- 自动执行 `apply-plan.json`。
