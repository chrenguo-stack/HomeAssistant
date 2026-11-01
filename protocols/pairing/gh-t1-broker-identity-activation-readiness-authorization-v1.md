# gh-t1-broker-identity-activation-readiness-authorization-v1

状态：M2.4g-5o Draft

## 1. 目的

将操作员对真实 T1 Broker 身份激活的明确决定，绑定到一个已经验证的 activation readiness bundle，而不是仅绑定 handoff 名称或 Home Assistant 目标。

本阶段只创建短时、单次授权材料，不安装 production driver，不执行 live activation。

## 2. 授权请求

授权请求从 mode `0600` readiness bundle 生成，并输出：

- bundle SHA-256；
- production driver、executor、mount、runtime manifest、preflight 和 Home Assistant gate 的 SHA-256；
- Broker runtime 指纹；
- Home Assistant 目标、config entry 和 storage 指纹；
- 固定 activation scope；
- 精确确认字符串。

确认字符串格式：

```text
AUTHORIZE-M2-BROKER-BUNDLE:<bundle-sha256前16位>:<broker-runtime-fingerprint>
```

确认字符串不是密码，但必须由操作员在看到 readiness 摘要后明确提交。

## 3. 授权材料

授权材料必须：

- 写入独立的 `greenhouse-m2-activation-authorizations*` 私有目录；
- 与 runtime binding 目录分离；
- 文件权限精确为 `0600`；
- 原子写入并 fsync 文件及父目录；
- TTL 为 60–1800 秒；
- 使用高熵随机 token；
- `authorization_id` 为 token SHA-256 的前 24 个十六进制字符；
- 完整绑定 readiness bundle 中全部 SHA-256 与脱敏指纹；
- `single_use=true`、`consumed=false`。

stdout 不得包含 token 或完整宿主机路径。

## 4. 验证

授权验证必须重新读取并验证 readiness bundle，并检查：

- 所有 SHA-256 和指纹逐项相等；
- activation scope 未变化；
- token 与 authorization ID 匹配；
- 授权尚未消费；
- 当前时间位于 creation 与 expiry 之间；
- 匿名兼容仍保持开启；
- live apply 仍未启用。

## 5. 固定安全标志

授权请求保持：

- `operator_action_authorized=false`；
- `authorization_created=false`；
- `apply_enabled=false`；
- `ready_for_live_activation=false`；
- `current_services_modified=false`。

授权文件和验证摘要允许：

- `operator_action_authorized=true`；
- `single_use=true`；
- `consumed=false`。

但仍必须保持：

- `apply_enabled=false`；
- `ready_for_live_activation=false`；
- `current_services_modified=false`；
- `preserve_anonymous=true`；
- `anonymous_closure_enabled=false`。

## 6. 禁止行为

本阶段禁止：

- claim 或消费授权；
- 修改 Mosquitto 配置或 Dynamic Security 状态；
- 重启容器；
- 修改 Home Assistant；
- 写入真实节点凭据；
- 提供 `--execute`、`--apply` 或 `--live` 入口。
