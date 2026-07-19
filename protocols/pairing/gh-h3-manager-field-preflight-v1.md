# H3 Manager field preflight V1

状态：H3 私有现场验收前只读证据盘点门禁。

## 目的

该门禁位于公共 `ghctl m2 readiness` 与既有
`t1_manager_identity_fresh_chain_preparation --discover-only` 之间。它只负责：

1. 复核公共 H3 实现链来自祖先关系正确且 tracked 工作区干净的仓库；
2. 在操作者指定的本地私有搜索根内定位 legacy-review bridge；
3. 调用既有 bridge 验证器复核 mode、inventory、schema、记录与 SHA-256；
4. 可选地把操作者明确提供的 exact retained Topic 转换为 SHA-256，并选择唯一匹配 bridge；
5. 生成不含真实路径、Topic、凭据或授权值的盘点报告。

它不扫描生产网络，不调用 Docker、MQTT、SSH 或 systemd，不写入私有证据，不创建或
领取授权，不生成 fresh preparation，也不执行 manager 身份迁移。

## 输入

- `--repository`：当前源码仓库；
- `--search-root`：操作者明确指定的本地私有证据搜索根；
- `--expected-retained-topic`：可选的 exact `gh/` Topic，不允许 `+` 或 `#`；
- `--require-baseline-ancestor` 与 `--require-clean`：正式使用时必须启用。

搜索根不得是符号链接。扫描不跟随目录符号链接，最多访问 4096 个目录；只把名称以
`greenhouse-manager-legacy-review-bridge-` 开头的目录交给既有严格验证器。

## 通过语义

无 Topic 时，工具只完成候选盘点：

```text
ready_for_fresh_chain_discovery=false
next_action=SUPPLY_EXPECTED_RETAINED_TOPIC
```

只有明确 Topic 与唯一有效 bridge 的 Topic 哈希一致时：

```text
ready_for_fresh_chain_discovery=true
next_action=RUN_FRESH_CHAIN_DISCOVER_ONLY
```

即使通过，也必须保持：

```text
h3_field_accepted=false
ready_for_live_runtime_gate=false
ready_for_live_apply=false
live_action_authorized=false
production_probe_invoked=false
production_execution_invoked=false
authorization_generated=false
authorization_claimed=false
credential_material_read=false
current_services_modified=false
node_credentials_delivered=false
anonymous_closure_enabled=false
```

下一步只能运行既有 fresh-chain `--discover-only`。不得跳到 live-runtime、授权或执行阶段。
