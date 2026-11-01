# gh-t1-auth-migration-rehearsal-v1

## 1. 目的

本协议定义 M2.4b 的 T1 认证迁移包离线演练门。

演练工具消费两个已经存在于 T1 本机的敏感文件：

1. 经 `gh.m2.t1-backup/1` 校验的真实回退包；
2. 经 `gh.m2.t1-auth-migration/1` 校验的私有认证迁移包。

工具只在从回退包恢复出的 Mosquitto 快照副本上运行。候选容器必须使用：

```text
--network none
```

工具不得连接、停止、重启、重新配置或写入真实 Mosquitto、greenhouse-manager、Home Assistant 或节点。

## 2. 输入绑定

迁移包必须与所选回退包精确绑定。下列字段必须全部一致：

- 回退包文件名；
- 回退包 SHA-256；
- 回退包 schema；
- 回退包记录的 Mosquitto 镜像 ID。

任何不一致都必须在创建候选容器之前阻断。

## 3. 迁移材料一致性

演练工具必须交叉核对以下材料：

- `manifest.json` 中的四个身份；
- `broker/dynsec-request.json` 中的 `createClient`；
- provisioning 客户端配置；
- manager 环境变量与密码文件；
- Home Assistant MQTT 更新描述；
- 节点 MQTT 凭据描述。

四类身份固定为：

```text
provisioning
manager
homeassistant
node
```

username、client ID、generation、role 和密码必须在各文件之间一致。四个运行时密码必须互不相同。

## 4. 候选启动

候选必须：

1. 从回退包恢复 Mosquitto 配置、数据、权限和数值 UID/GID；
2. 使用回退包记录的精确 Mosquitto 镜像 ID；
3. 只修改临时快照副本；
4. 使用迁移包中的一次性 bootstrap admin 密码初始化 Dynamic Security；
5. 在 Dynamic Security 状态生成后立即删除初始化密码文件；
6. 将迁移包中的原始 Dynamic Security 请求通过标准输入发送给候选 Broker。

密码不得进入命令行参数、日志、Git、报告或真实服务环境。

## 5. bootstrap admin 撤除

必须先验证 provisioning 身份能够执行 Dynamic Security `listClients`，之后才允许删除 bootstrap admin。

删除后必须同时满足：

- `admin` 客户端对象不存在；
- bootstrap admin 旧配置无法再次使用；
- provisioning 身份仍可执行 Dynamic Security 管理请求。

该步骤只发生在候选快照中。

## 6. 身份矩阵

### 6.1 节点

节点只能：

- 发布自身 ingress；
- 订阅自身 out。

节点不得：

- 发布其他节点 ingress；
- 发布 canonical state；
- 发布 Home Assistant Discovery；
- 访问 `$CONTROL/#`；
- 使用错误 client ID 登录。

### 6.2 greenhouse-manager

manager 必须能够：

- 接收节点 ingress；
- 发布 canonical state；
- 发布当前冻结的两类 Home Assistant Discovery。

manager 不得：

- 发布 `homeassistant/status`；
- 向节点 ingress 写入数据；
- 访问 `$CONTROL/#`；
- 使用错误 client ID 登录。

### 6.3 Home Assistant

Home Assistant 必须能够：

- 接收 `homeassistant/#`；
- 接收 canonical state；
- 发布 `homeassistant/status`。

Home Assistant 不得：

- 写入 canonical state；
- 写入节点 ingress；
- 访问 `$CONTROL/#`；
- 使用错误 client ID 登录。

### 6.4 provisioning

provisioning 必须能够访问 Dynamic Security 控制请求与响应。

provisioning 不得：

- 发布或订阅 `gh/#`；
- 发布或订阅 `homeassistant/#`；
- 使用错误 client ID 登录。

## 7. legacy anonymous 兼容

撤除 bootstrap admin 后，候选仍必须满足：

- 既有非 `$` 应用 Topic 可匿名发布与订阅；
- 真实 retained telemetry 可恢复；
- 匿名客户端不能访问 `$CONTROL/#`。

该兼容窗口只用于后续逐客户端迁移，不能作为最终安全配置。

## 8. 成功报告

成功报告 schema：

```text
gh.m2.t1-auth-migration-rehearsal/1
```

必须包含：

```json
{
  "network": "none",
  "source_binding": true,
  "exact_package_request_applied": true,
  "exact_package_identity_matrix": true,
  "client_id_binding": true,
  "provisioning_control_only": true,
  "bootstrap_admin_removed": true,
  "provisioning_after_admin_removal": true,
  "legacy_anonymous_after_admin_removal": true,
  "anonymous_control_denied": true,
  "retained_state_recovered": true,
  "current_services_modified": false
}
```

报告不得包含用户名对应密码、bootstrap 密码或完整 Dynamic Security 请求。

## 9. 安全边界

本阶段明确禁止：

- 将迁移包应用到真实 Broker；
- 关闭真实 `allow_anonymous true`；
- 修改 Home Assistant `.storage`；
- 重启真实 Mosquitto、greenhouse-manager 或 Home Assistant；
- 向真实节点下发 MQTT 凭据；
- 将迁移包复制离开 T1 或提交到 Git。

只有该演练门通过后，才可设计下一阶段的真实 Broker 变更计划；真实变更仍需独立显式门禁与可执行回退方案。
