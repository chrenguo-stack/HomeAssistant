# H3/N2 Stage 2D-9R G3R：TLS 有效候选链开发计划

## 1. 阶段目标

在不激活、不修补当前 V69 PREPARED 候选的前提下，开发一条新的测试专用 `PREPARE_CANDIDATE` 链，使持久化候选从生成时即包含真实可验证的 TLS CA 与隔离 Broker 身份。

本阶段只进行源码、host 模型、compile-only、CI、协议、故障矩阵、公开摘要描述符和私密材料边界开发。

## 2. 输入与输出

历史输入：

```text
Stage2D9 V69 result=PASS within no-network PREPARE scope
active_generation=0
candidate_generation=1
candidate_state=PREPARED
candidate ca_pem=non-PEM test marker
```

本阶段不把该状态作为可激活输入。

目标输出：

```text
new immutable source
new TLS-valid candidate descriptor
new private test PKI custody package
new LOCKED firmware Artifact
new recovery Artifact
new host and compile evidence
new exact D2 review package
```

任何实板执行都不属于当前授权范围。

## 3. TLS 候选合同

候选必须包含并绑定以下字段：

- `broker_host`；
- `broker_port=8883`；
- `broker_tls_server_name`；
- 完整 PEM CA；
- MQTT username；
- MQTT client ID；
- MQTT password；
- test-only topic root；
- credential generation；
- candidate digest。

公开描述符还必须记录：

- CA PEM SHA-256；
- CA DER certificate SHA-256；
- Broker leaf certificate SHA-256；
- Broker SPKI SHA-256；
- 证书有效期；
- DNS SAN 精确集合；
- Broker 配置摘要；
- 私密材料包摘要；
- 候选规范化算法版本。

公开仓库不得保存 CA 私钥、Broker 私钥、MQTT 密码、持久化密钥、unlock token、原始命令或本地路径。

## 4. 私密测试 PKI

私密 PKI 应在主机侧离线生成，至少包括：

```text
self-contained test root CA
broker leaf certificate
broker private key
CA public certificate
isolated Broker password material
```

约束：

- 仅用于 `stage2d9r.local` 隔离测试身份；
- leaf certificate 的 DNS SAN 必须精确包含 `stage2d9r.local`；
- 不使用通配符；
- 不使用 IP SAN 作为 hostname 校验替代；
- CA 与 leaf 的 basic constraints、key usage、extended key usage 必须符合角色；
- 私钥文件权限不得宽于 `0600`；
- 私密材料必须有唯一 SHA-256 匹配和显式保管清单；
- Artifact 与源码不得包含私钥或 MQTT 密码。

## 5. 测试板恢复与新 PREPARE 的未来执行顺序

需要独立 D2 后才能执行：

```text
read-only identify current V69 state
→ exact locked recovery to deterministic baseline
→ recovery readback/seed verification
→ erase and flash new Stage2D9R candidate firmware
→ Flash verify and automatic reset
→ start isolated Broker bound to private test PKI
→ send exactly one PREPARE command
→ firmware automatic restart
→ send exactly one read-only VERIFY command
→ stop Broker and retain private evidence
```

Stage 2D-9R 的 PREPARE 行为自身仍不得建立 MQTT 会话。隔离 Broker 在该阶段只用于验证主机侧 PKI/配置一致性和为后续 G4 冻结同一身份，不能被 PREPARE 固件连接。

## 6. 回到 G4 的输入条件

只有以下条件全部成立才可继续 G4：

```text
active_generation=0
candidate_generation=1
candidate_state=PREPARED
candidate_digest_match=true
ca_pem_parseable=true
ca_fingerprint_match=true
broker_leaf_chain_valid=true
broker_hostname_match=true
private_material_digest_match=true
mqtt_operation_attempted_during_prepare=false
```

G4 必须重新绑定新的 source SHA、Artifact SHA、candidate digest、PKI descriptor digest 和独立 ACTIVATE D2。

## 7. 故障矩阵最低覆盖

- CA PEM 语法无效；
- CA/leaf 签名链不匹配；
- leaf SAN 缺失或 hostname 不匹配；
- leaf 过期、尚未生效或有效期超出策略；
- leaf EKU 缺少 serverAuth；
- CA basic constraints 错误；
- Broker 配置摘要错配；
- MQTT 用户名、密码、client ID 或 topic root 与描述符错配；
- 私密材料零匹配、多匹配、权限过宽；
- public package 含私钥、密码或原始命令；
- candidate canonicalization 版本错配；
- LOCKED 描述符携带非空私密摘要但状态不一致；
- 任何 execution/network/write 授权意外开启。

## 8. 当前门状态

```text
D1_APPROVED=true
SOURCE_DEVELOPMENT_AUTHORIZED=true
HOST_MODEL_AUTHORIZED=true
COMPILE_ONLY_AUTHORIZED=true
PRIVATE_PKI_GENERATION_AUTHORIZED=false
BOARD_OPERATION_AUTHORIZED=false
NETWORK_OPERATION_AUTHORIZED=false
PREPARE_AUTHORIZED=false
VERIFY_AUTHORIZED=false
ACTIVATE_AUTHORIZED=false
CLEANUP_AUTHORIZED=false
READY_MERGE_RELEASE_AUTHORIZED=false
```

私密 PKI 生成、Artifact 冻结和实板执行将在相应源码与审查边界完成后分别进入新的确认门。