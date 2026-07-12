# gh-t1-auth-migration-readiness-v1

## 1. 目的

本协议定义 M2.4c 的真实 T1 认证迁移就绪审计。

审计只读取当前 T1 状态、已验证回退包和已验证迁移包，生成不可执行的迁移交易计划。它不得修改、重启或重新配置 Mosquitto、greenhouse-manager、Home Assistant、节点或 Docker Compose。

成功报告 schema：

```text
gh.m2.t1-auth-migration-readiness/1
```

## 2. 输入

必须提供：

- 已验证的 `gh.m2.t1-backup/1` 回退包；
- 已验证的 `gh.m2.t1-auth-migration/1` 私有迁移包；
- 真实 Compose 目录；
- 预期 retained telemetry Topic；
- 预定主机秘密目录。

默认路径：

```text
/opt/HomeAssistant/infra/compose/t1
/opt/greenhouse-secrets/mqtt
```

## 3. 只读检查

### 3.1 实时容器

必须检查：

- `mosquitto` 为 `running` 且 restart count 为 0；
- `greenhouse-manager` 为 `running` 且 restart count 为 0；
- 两个容器的真实镜像 ID 与回退包 manifest 一致。

### 3.2 Broker 基线

必须检查：

- 当前 `/mosquitto/config/mosquitto.conf` 可读；
- 当前配置 SHA-256 与回退包中的同一文件一致；
- `allow_anonymous true` 尚未改变；
- Dynamic Security plugin 尚未写入真实配置；
- `/mosquitto/data/dynamic-security.json` 尚不存在；
- 镜像中包含 `mosquitto_dynamic_security.so`；
- 预期 retained Topic 可通过当前匿名兼容模式读取。

### 3.3 manager 基线

只允许报告以下布尔值，不得报告环境变量值：

- `GH_MQTT_USERNAME` 是否为非空；
- `GH_MQTT_PASSWORD` 是否为非空；
- `GH_MQTT_PASSWORD_FILE` 是否为非空。

真实迁移前，三项都必须为 false。

### 3.4 文件与目录

必须检查：

- 回退包为 `0600`；
- 迁移包为 `0600`；
- 迁移包所在目录不允许组或其他用户访问；
- Compose 目录存在；
- 至少存在一个标准 Compose 文件；
- `.env` 存在且为 `0600`；
- 主机秘密目录尚不存在，或为空且仅所有者可访问。

不得读取或输出 `.env` 内容。

### 3.5 隔离候选残留

不得存在下列前缀的残留容器：

```text
gh-m2-restore-
gh-m2-shadow-
gh-m2-shadow-services-
gh-m2-package-rehearsal-
```

## 4. 包绑定

迁移包必须与所选回退包精确匹配：

- 文件名；
- SHA-256；
- schema；
- Mosquitto 镜像 ID。

迁移包必须继续满足：

```json
{
  "apply_enabled": false,
  "current_services_modified": false
}
```

## 5. 交易计划

审计报告可包含交易步骤名称和回退检查点，但必须满足：

```json
{
  "apply_enabled": false,
  "requires_explicit_gate": true,
  "requires_fresh_backup_immediately_before_apply": true
}
```

推荐顺序：

1. 实际变更前重新创建并验证新回退包；
2. 暂存私有秘密文件与 Compose overlay；
3. 保持匿名兼容的前提下启用 Dynamic Security；
4. 验证 provisioning 后撤除 bootstrap admin；
5. 迁移 greenhouse-manager；
6. 通过受支持的 Home Assistant 配置入口迁移 MQTT；
7. 迁移节点凭据；
8. 观察认证链路稳定性；
9. 通过独立门禁关闭匿名访问。

禁止直接编辑 Home Assistant `.storage`。

## 6. 成功条件

报告中全部 gate 必须为 true，且：

```json
{
  "read_only": true,
  "apply_enabled": false,
  "current_services_modified": false,
  "ready": true
}
```

## 7. 安全边界

本阶段禁止：

- 写入真实 Mosquitto 配置或数据；
- 创建真实 Dynamic Security 客户端或角色；
- 创建或复制真实主机秘密；
- 修改 Compose、`.env` 或 Home Assistant；
- 重启任何真实容器；
- 向节点下发凭据；
- 关闭匿名访问；
- 提供自动执行真实迁移的代码路径。

通过本门仅表示当前真实基线与已验证材料一致，不代表已经授权真实迁移。
