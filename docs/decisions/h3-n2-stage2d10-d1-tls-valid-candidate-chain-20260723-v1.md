# H3/N2 Stage 2D-10 D1：采用新的 TLS 有效候选链

- 决策编号：`D1-H3N2-STAGE2D10-TLS-CANDIDATE-20260723-01`
- 决策日期：2026-07-23
- 决策状态：`APPROVED`
- 决策类型：D1 产品/技术路径决策
- 后续执行门：`LOCKED_SOURCE_AND_COMPILE_ONLY`

## 1. 背景

Stage 2D-9 V69 已完成一次受控 `PREPARE_CANDIDATE`，并形成以下已验收持久化状态：

```text
active_generation=0
candidate_generation=1
candidate_state=PREPARED
candidate_digest_match=true
mqtt_operation_attempted=false
```

该候选在 Stage 2D-9 的测试边界内有效，因为该阶段明确禁止 Wi-Fi、MQTT 和 Broker 操作。但候选凭据中的 `ca_pem` 持久化值是字面测试标识 `stage2d9-test-ca`，并不是可由 TLS 栈解析的 PEM CA 证书。

Stage 2D-10 G4 的职责包括使用恢复出的候选配置完成真实隔离 TLS/MQTT 验证。继续使用当前候选将无法满足“精确恢复既有候选”和“真实 TLS 校验”两个约束。

## 2. 已批准决策

采用新的 TLS 有效候选链，不对当前 V69 候选执行 `ACTIVATE_PROFILE`。

新的候选链必须同时满足：

1. `ca_pem` 是完整、可解析且与隔离 Broker 证书链匹配的 PEM CA；
2. Broker 主机名、端口、TLS server name、CA、用户名、客户端 ID、密码和 topic root 形成同一份不可变候选描述；
3. 私密证书、私钥、密码和命令材料只进入私密保管，不提交到 Git 或公共 Artifact；
4. 公共源码和 Artifact 只保存 SHA-256、长度、用途、证书公钥/证书指纹等非秘密绑定信息；
5. 新候选必须经过新的不可变 Artifact、独立 U1 校验和独立一次性 D2 授权；
6. 只有重启后只读验证再次确认 `active_generation=0`、`candidate_generation=1`、`candidate_state=PREPARED` 且候选摘要精确匹配，才允许回到 Stage 2D-10 G4。

## 3. 明确拒绝的替代方案

以下路径不采用：

- 禁用 TLS 证书校验；
- 将 `stage2d9-test-ca` 静默解释为真实证书或证书别名；
- 在 G4 中放宽候选字段或摘要绑定；
- 在激活时替换、补写或修正当前候选；
- 复用 V69 Artifact、命令、授权或私密执行材料；
- 重放任何已经退休或消费的 Stage 2D-9 D2；
- 将 `CLEANUP_TEST_STATE` 隐含并入 G4。

这些方案会破坏候选不可变性、TLS 真实性、授权边界或证据可审计性。

## 4. 阶段调整

新增受控输入修正阶段：

```text
H3/N2 Stage 2D-9R G3R
TLS-valid PREPARE_CANDIDATE replacement chain
```

建议执行顺序：

```text
冻结隔离测试 PKI 与 Broker 身份
→ 生成公开摘要描述符和私密材料清单
→ 源码/host/compile-only 验证
→ 生成新的 LOCKED 不可变 Artifact
→ U1 主机私密保管与 Artifact 校验
→ 独立 D2：受控恢复测试板基线
→ 使用新 Artifact 单次 PREPARE
→ 固件自动重启
→ 单次只读 VERIFY
→ 冻结新的 PREPARED 输入
→ 返回 Stage 2D-10 G4
```

## 5. 当前测试板状态

当前 V69 测试板状态视为历史验收结果，保持不变：

```text
active_generation=0
candidate_generation=1
candidate_state=PREPARED
candidate_tls_usable=false
activation_authorized=false
cleanup_authorized=false
additional_board_operation_authorized=false
```

“`candidate_tls_usable=false`”是对 Stage 2D-10 输入适用性的结论，不否定 Stage 2D-9 V69 在其原始无网络 PREPARE 验收范围内的通过结果。

## 6. 当前授权边界

本 D1 只批准技术路线和源码开发，不批准任何实板或网络执行。

当前仍禁止：

- 板卡、串口、Flash、物理 NVS 操作；
- `PREPARE_CANDIDATE`、`ACTIVATE_PROFILE`、`CLEANUP_TEST_STATE`；
- Wi-Fi、MQTT、Broker 或真实 TLS 连接；
- eFuse、Secure Boot、Flash Encryption；
- M401A、T1、Home Assistant、Mosquitto、greenhouse-manager；
- 生产固件、生产凭据、Ready、merge、release 或部署。

任何物理恢复、擦写、烧录、PREPARE、VERIFY 或隔离 Broker 执行，均需要新的精确 D2。

## 7. 后续完成标准

Stage 2D-9R 进入授权前审核时，至少应具备：

- 新候选字段和规范化摘要算法冻结；
- TLS CA 与 Broker 证书链离线校验通过；
- hostname/SAN 和 server-name 校验通过；
- 公共与私密材料严格分离；
- host 故障矩阵覆盖无效 PEM、错误 CA、错误 SAN、错误密码、过期证书、摘要错配和秘密泄漏；
- 两次干净编译字节一致；
- LOCKED manifest 中所有实板、网络和写授权为 false；
- 独立恢复镜像及恢复后只读状态判定；
- 新 `.py` 和 `.sh` 文件使用从未出现过的唯一名称。

Stage 2D-10 PR 在新的 TLS 有效 PREPARED 输入形成前保持 Draft 和 LOCKED。