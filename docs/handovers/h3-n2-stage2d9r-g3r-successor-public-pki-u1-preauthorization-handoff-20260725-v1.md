# 温室环境监测系统 H3/N2 Stage 2D-9R G3R successor
## 公开 PKI 导出 U1 授权前开发交接文档 V1.0（2026-07-25）

- **项目仓库**：`chrenguo-stack/HomeAssistant`
- **当前阶段**：H3/N2 Stage 2D-9R G3R successor
- **本轮结束门**：公开 PKI 导出 U1 只读审核探测已通过，精确 U1 尚未签发
- **下一授权 ID**：`U1-H3N2-STAGE2D9R-PUBLIC-PKI-EXPORT-20260725-01`
- **开发 PR**：Draft PR `#180`
- **开发 PR 冻结 HEAD**：`6d28b344d29089704ac73ee636e3688ee42704b8`
- **默认分支 main**：`a3a72d75480362999e70e180f33459198b3951b5`
- **归档分支**：`archive/h3-n2-stage2d9r-g3r-public-pki-u1-preauth-handoff-20260725-v1`
- **文档用途**：新会话恢复、授权前复核、证据链审计、分阶段路线核对和后续开发计划

> 本交接文档提交在独立归档分支，不修改 Draft PR #180 的 HEAD。这样可保存本轮记录，同时保持公开 PKI U1 审核 Artifact 与 `source_sha=6d28b344...` 的精确绑定不发生漂移。

---

## 0. 本轮最终结论

本轮已经完成 successor 私密执行材料链、脱敏公开描述符导出链和公开 PKI 导出工具链的源码、合同、CI、一次性 U1 执行与只读闭环验证。

当前停止点为：

```text
PRIVATE_EXECUTION_MATERIAL_U1=CONSUMED_PASS
PRIVATE_EXECUTION_MATERIAL_SUCCESS_MARKER_PROBE=PASS
PUBLIC_DESCRIPTOR_EXPORT_U1=CONSUMED_PASS
PUBLIC_DESCRIPTOR_EXPORT_CLOSURE_PROBE=PASS
PUBLIC_DESCRIPTOR_IMPORTED_TO_REPOSITORY=true
PUBLIC_PKI_EXPORT_U1_REVIEW_PROBE=PASS
PUBLIC_PKI_EXPORT_U1_AUTHORIZATION_CREATED=false
PUBLIC_PKI_EXPORT_U1_AUTHORIZATION_CLAIMED=false
PUBLIC_PKI_EXPORT_U1_AUTHORIZATION_CONSUMED=false
BOARD_OPERATION=false
NETWORK_OPERATION=false
BROKER_STARTED=false
PREPARE_EXECUTED=false
VERIFY_EXECUTED=false
D2_AUTHORIZED=false
```

下一轮不得直接执行导出器。必须先重新复核 GitHub、Artifact、工具链、两个 consumed marker、公开文件存在状态和固定输出目标，全部一致后，用户才粘贴本文第 11 节的精确 U1 授权文本。

---

## 1. 必须遵守的开发与安全规则

新会话开始后先读取并遵守：

1. 本交接文档；
2. 仓库根目录 `AGENTS.md`；
3. `docs/skills/greenhouse-github-development-efficiency/SKILL.md`；
4. `docs/development/local-ai-task-splitting-rules.md`；
5. 本归档分支中的状态快照：
   `docs/acceptance/h3-n2-stage2d9r-g3r-successor-public-pki-u1-preauthorization-state-20260725-v1.json`；
6. Draft PR #180 的源码、测试、CI 和接受记录；
7. PR #176 的冻结 Stage 2D-9R 基线。

固定纪律：

- 不得重放已消费或已退役的任何 U1、D2、PREPARE、VERIFY 或旧 Artifact；
- 不得在 Git、日志、终端输出或公开包中保存 MQTT 密码预映像、持久化密钥、解锁令牌、私钥、密码数据库内容或完整 PREPARE/VERIFY 命令；
- 不得为了提速绕过 one-shot、generation binding、回滚、私密托管、CI 或实机验收边界；
- PR #180 和 PR #176 均保持 Draft、未合并；未经独立授权不得 Ready、merge、release、tag 或 deployment；
- 未经独立 D2，不得连接测试板、串口、Flash、物理 NVS、隔离 Broker 或真实网络；
- 不得操作 M401A、T1、Home Assistant、Mosquitto、greenhouse-manager 或生产环境；
- 不得操作 eFuse、Secure Boot 或 Flash Encryption。

---

## 2. 当前 GitHub 冻结状态

### 2.1 main

```text
repository=chrenguo-stack/HomeAssistant
main_sha=a3a72d75480362999e70e180f33459198b3951b5
live_main_compare=identical
ahead_by=0
behind_by=0
```

### 2.2 successor Draft PR #180

```text
pull_request=180
title=fix(n2): retain Stage2D9R private execution credential preimages
branch=fix/h3-n2-stage2d9r-g3r-private-execution-material-20260725-v1
head_sha=6d28b344d29089704ac73ee636e3688ee42704b8
base_pull_request=176
base_sha=cf841f3e5a8cf04c5df9875c499b91ad4e4289cb
state=open
draft=true
merged=false
mergeable=true
commit_count=40
changed_file_count=25
additions=4845
deletions=0
```

PR #180 当前 25 个变更路径：

```text
.github/workflows/h3-n2-stage2d9r-private-execution-material-successor-contract-ci.yml
.github/workflows/h3-n2-stage2d9r-successor-private-execution-material-generator-ci.yml
.github/workflows/h3-n2-stage2d9r-successor-private-execution-material-success-marker-probe-package-ci.yml
.github/workflows/h3-n2-stage2d9r-successor-private-execution-material-u1-review-package-ci.yml
.github/workflows/h3-n2-stage2d9r-successor-public-descriptor-export-closure-probe-package-ci.yml
.github/workflows/h3-n2-stage2d9r-successor-public-descriptor-export-u1-review-package-ci.yml
.github/workflows/h3-n2-stage2d9r-successor-public-pki-export-u1-review-package-ci.yml
docs/acceptance/h3-n2-stage2d9r-d2-01-preclaim-invalidation-l1-v1.json
docs/acceptance/h3-n2-stage2d9r-successor-private-execution-material-u1-01-success-l1-v1.json
docs/acceptance/h3-n2-stage2d9r-successor-public-descriptor-export-u1-01-success-l1-v1.json
docs/development/h3-n2-stage2d9r-private-execution-material-successor-plan-20260725-v1.md
tests/h3_n2_stage2d9r_tls_candidate/public_successor_tlsvalid02/export-binding.json
tests/h3_n2_stage2d9r_tls_candidate/public_successor_tlsvalid02/public-descriptor.redacted.json
tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_private_execution_material_successor_contract_20260725_v1.py
tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_private_execution_material_successor_generator_20260725_v1.py
tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_successor_private_execution_material_success_marker_probe_20260725_v1.py
tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_successor_public_descriptor_export_closure_probe_20260725_v1.py
tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_successor_public_descriptor_exporter_20260725_v1.py
tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_successor_public_pki_exporter_20260725_v1.py
tools/h3_n2_stage2d9r_private_execution_material_successor_contract_20260725_v1.py
tools/h3_n2_stage2d9r_private_execution_material_successor_generator_20260725_v1.py
tools/h3_n2_stage2d9r_successor_private_execution_material_success_marker_probe_20260725_v1.py
tools/h3_n2_stage2d9r_successor_public_descriptor_export_closure_probe_20260725_v1.py
tools/h3_n2_stage2d9r_successor_public_descriptor_exporter_20260725_v1.py
tools/h3_n2_stage2d9r_successor_public_pki_exporter_20260725_v1.py
```

### 2.3 冻结基线 Draft PR #176

```text
pull_request=176
title=feat(n2): develop Stage2D9R TLS-valid candidate chain
branch=feature/h3-n2-stage2d9r-g3-tls-valid-candidate-20260723-v1
head_sha=cf841f3e5a8cf04c5df9875c499b91ad4e4289cb
base=main
state=open
draft=true
merged=false
mergeable=true
replay_or_modification_authorized=false
```

PR #176、历史 `tlsvalid01` PKI、旧命令材料、旧 Artifact 和旧 consumed marker 均保持冻结，不得修改或重放。

### 2.4 当前 HEAD 的 CI

`source_sha=6d28b344d29089704ac73ee636e3688ee42704b8` 上以下 9 项工作流均为 `completed/success`：

```text
Public repository safety CI
H3 N2 Stage2D9R TLS Candidate CI
H3 N2 Stage2D9R Private Execution Material Successor Contract CI
H3 N2 Stage2D9R Successor Private Execution Material Generator CI
H3 N2 Stage2D9R Successor Private Execution Material U1 Review Package CI
H3 N2 Stage2D9R Successor Private Execution Material Success Marker Probe Package CI
H3 N2 Stage2D9R Successor Public Descriptor Export U1 Review Package CI
H3 N2 Stage2D9R Successor Public Descriptor Export Closure Probe Package CI
H3 N2 Stage2D9R Successor Public PKI Export U1 Review Package CI
```

本轮修复并闭环的 CI 问题：

1. 公开 PKI 审核包初版错误地把含秘密文件名字符串的源码测试文件复制进审核包，边界扫描按设计失败；修订后审核包不再包含该测试文件，源码测试仍在 CI 工作区执行。
2. successor generator 和旧 U1 review workflow 的 ancestry fetch 深度不足；已提高到足够深度。
3. 已消费的私密执行材料 U1 不应继续生成新 review Artifact；旧 review workflow 改为只验证冻结源码和已消费成功记录，不创建、声明或消费新授权。
4. 已消费成功记录验证中局部变量覆盖导致断言失败；已修复并通过。

---

## 3. D2-01 失效处置

旧请求：

```text
D2-H3N2-STAGE2D9R-G3R-20260725-01
```

处置：

```text
status=invalidated_before_claim
authorization_record_created=false
authorization_claimed=false
authorization_consumed=false
replay_permitted=false
board_operation=false
serial_operation=false
flash_operation=false
physical_nvs_operation=false
network_operation=false
```

失效原因：旧私密链没有保留随机 MQTT 密码预映像和 PREPARE/重启后 VERIFY 所需的持久化密钥，无法重建精确绑定命令。禁止通过暴力恢复、重置密码数据库、替换凭据或手工补写解决。

D2-01 已永久退役，不得再次粘贴、签发或执行。

---

## 4. successor 私密执行材料 U1 闭环

### 4.1 授权

```text
authorization_id=U1-H3N2-STAGE2D9R-PRIVATE-EXECUTION-MATERIAL-20260725-01
authorized_source_sha=0cd9eeb5fd567d47a29bddee83159ac9570aa3dd
authorization_record_sha256=99d5f8cf5a0a12d921497ce04b7dc95161fc77ee79e79ddf50d6cb2535473817
status=CONSUMED
result=PASS
one_shot=true
replay_permitted=false
automatic_retry_permitted=false
```

### 4.2 公开冻结结果

```text
private_package_sha256=7b585fc53b9201fd2c6161e544ac062d4223f509bfc86a10052d97907e4f55bb
public_descriptor_sha256=7021279f141f00cbf7e64fe8a20e89dd8b8ef3b9c4c7625ec28b79f6d65db2b6
candidate_digest_sha256=a0ff758217a1769c1876336c131cb85e64dcb2369758c649f36798cd8083aaf2
unlock_digest_sha256=727db669e17634b6d66fc1d8bd4f4d9e4e4e196401806c9b56c7eed6b8a7d9e9
ca_pem_sha256=9d98b4aa1d87604e8c37aaa50892bf4cd47b8b8a0479acdabe78d41d39b36096
broker_certificate_der_sha256=4ca8731424c87ba61336f4bc4fb743137ed83c127ed1a214198b65e5b33b40f9
broker_spki_sha256=0ae2d32c2ddfb7b4b63c9ee4049291d9725a42a55721b0e78d53fcf5c9e1f72e
```

### 4.3 成功 marker 只读复核

```text
marker_sha256=428231f9e0e6a26c39701427b3e32531e18d08b54e341736b1189a78a06848a5
marker_status=CONSUMED
failure_code=null
marker_modified=false
private_content_read=false
```

禁止再次运行私密执行材料生成启动器，禁止手工修改 successor 私密托管根。

---

## 5. successor 公开描述符导出 U1 闭环

### 5.1 授权结果

```text
authorization_id=U1-H3N2-STAGE2D9R-PUBLIC-DESCRIPTOR-EXPORT-20260725-01
authorized_source_sha=950fdc26a0b876ffcdf9c2e7c21716cb49b1843d
authorization_record_sha256=3c55e5f01071cfebf4f2cb98ab643da09582f1cc94496e4b061d29a6f88e8e73
status=CONSUMED
result=PASS
one_shot=true
replay_permitted=false
automatic_retry_permitted=false
```

### 5.2 导出结果

```text
export_zip_sha256=77fcded756d3914964138909ca2b51c2a20c60be76eed758049ef6c84ce4d8d1
export_binding_sha256=acb161544e2fb3a381f0d93691f2fecddad31780dc19e2eca39bc4ab0424556c
public_descriptor_sha256=7021279f141f00cbf7e64fe8a20e89dd8b8ef3b9c4c7625ec28b79f6d65db2b6
candidate_digest_sha256=a0ff758217a1769c1876336c131cb85e64dcb2369758c649f36798cd8083aaf2
consumed_marker_sha256=a0c6ded9e371764a702b64fad58bd990b27808bae4467015116f9b189c8deceb
```

### 5.3 闭环探测

```text
closure_probe=PASS
export_modified=false
marker_modified=false
private_content_read=false
private_paths_included=false
secret_values_included=false
```

### 5.4 仓库冻结目录

公开 ZIP 已验证为确定性 ZIP，只包含：

```text
SHA256SUMS
export-binding.json
public-descriptor.redacted.json
```

已导入 PR #180：

```text
tests/h3_n2_stage2d9r_tls_candidate/public_successor_tlsvalid02/export-binding.json
tests/h3_n2_stage2d9r_tls_candidate/public_successor_tlsvalid02/public-descriptor.redacted.json
```

禁止再次运行公开描述符导出启动器，禁止覆盖或手工修改其 ZIP 与 consumed marker。

---

## 6. 公开 PKI 导出 U1 当前审核状态

### 6.1 审核 Artifact

```text
u1_request_id=U1-H3N2-STAGE2D9R-PUBLIC-PKI-EXPORT-20260725-01
review_artifact_id=8617450189
review_artifact_name=stage2d9r-successor-public-pki-export-u1-review-v1
review_artifact_source_sha=6d28b344d29089704ac73ee636e3688ee42704b8
review_artifact_github_digest_sha256=e763f5d359cdd63c942c589687343af4972beb3cf623ba299f28d71e35b6de87
review_binding_sha256=a75eb347fea5109f6c4fa37d6a11b42a4cc4023ab136acc3f9c98fe29c8853b7
exporter_sha256=a1bb13049c59d54f4f31586b3f5c784e0a7fba39d17a7b6d5988840b73ee050e
artifact_expired=false
artifact_expires_at=2026-07-30T08:04:46Z
```

### 6.2 用户已完成只读审核探测

```text
STAGE2D9R_SUCCESSOR_PUBLIC_PKI_EXPORT_PROBE=PASS
PUBLIC_PKI_EXPORT_REVIEW_BINDING=PASS
generation_marker_sha256=428231f9e0e6a26c39701427b3e32531e18d08b54e341736b1189a78a06848a5
descriptor_export_marker_sha256=a0c6ded9e371764a702b64fad58bd990b27808bae4467015116f9b189c8deceb
exporter_sha256=a1bb13049c59d54f4f31586b3f5c784e0a7fba39d17a7b6d5988840b73ee050e
python_executable_sha256=4e28e811a89aeac6eed668ae641c7f85f5831e42e8dc6cd9a85a3bcc032ec46a
openssl_executable_sha256=04ad05ce2e7eaf92116dac99a984cc0e589040a103589f93a9fe452832766973
output_target_digest_sha256=892d8a5c84013ec8b7724f11554b2f4698b5d1001efcdf96a7919bd33c3a0618
output_target_exists=false
public_root_exists=true
root_ca_exists=true
broker_certificate_exists=true
broker_fullchain_exists=true
public_descriptor_exists=true
public_content_read=false
private_content_read=false
authorization_claimed=false
authorization_consumed=false
board_operation=false
network_operation=false
```

### 6.3 导出器允许的内容

经精确 U1 授权后，导出器只允许读取并导出以下公开材料：

```text
root-ca.cert.pem
broker.cert.pem
broker.fullchain.pem
public-descriptor.redacted.json
```

最终 ZIP 只能包含：

```text
root-ca.cert.pem
broker.cert.pem
broker.fullchain.pem
public-descriptor.redacted.json
public-pki-export-binding.json
SHA256SUMS
```

导出前后会验证：

- 两个前序 consumed marker；
- 公开文件为普通文件、非符号链接、模式 0600；
- 公共描述符完整绑定；
- 根 CA PEM SHA-256；
- Broker DER 和 SPKI SHA-256；
- 证书链、TLS server 用途和 `stage2d9r.local` hostname；
- fullchain 恰好两个证书块且顺序为 Broker 叶证书、根 CA；
- 固定输出目标不存在；
- ZIP 确定性和内部模式；
- 授权记录、marker 和私密材料不进入 ZIP。

### 6.4 当前未发生事项

```text
authorization_record_created=false
authorization_claimed=false
authorization_consumed=false
public_pki_export_zip_created=false
broker_started=false
network_operation=false
board_operation=false
serial_operation=false
flash_operation=false
physical_nvs_operation=false
prepare_executed=false
verify_executed=false
```

---

## 7. 分阶段技术路线核对

依据《分阶段技术开发路线 V0.5》，总体顺序为：

```text
D0 接口冻结
→ H0/H1 主机基础
→ H2 MQTT 与模拟节点闭环
→ H3 发现、配对和凭据生命周期
→ N0 离线实板基线
→ N1 配网与发现
→ N2 安全绑定与正式 MQTT
→ N3-W / N3-L 分产品线开发
→ N4-L（仅现场需要）
→ S1 产品化、OTA、备份恢复和试点
```

### 7.1 路线节点状态

| 路线节点 | 当前判断 | 说明 |
|---|---|---|
| D0 架构与接口冻结 | 已完成并持续遵守 | Wi-Fi/LoRa 双产品线、统一身份、单跳边界、MQTT/配对/TLS 接口已形成基线。 |
| H0 T1 基线 | 已有验收基础 | T1/M401A 主机运行和不可变候选已有实机证据；黄金镜像量产化仍属于 S1。 |
| H1 产品栈与身份初始化 | 核心基础已完成，产品首启仍待 S1 | Docker、Mosquitto、manager、身份与凭据边界已大量实现；完整黄金镜像首启个性化未闭环。 |
| H2 MQTT V1 与模拟节点闭环 | 核心完成 | manager ingress、规范状态、Discovery 和模拟/实机 M1 路径已有证据。 |
| H3 发现、配对与凭据生命周期 | 核心已完成，完整异常生命周期待 Stage 2E | Stage 2A/2B 与主机实机基线已完成；撤销、主板迁移、主机恢复等完整矩阵仍需 Stage 2E。 |
| N0 离线节点实板基线 | 已有部分实板证据，正式 V0.5 N0 门仍需核对 | RC2 已多次编译、烧录和长期运行，但需按 V0.5 再核对完整离线回归和正式基线冻结条件。 |
| N1 Wi-Fi 配网与 manager 发现 | 核心实现完成，正式实机多主机/退避验收仍需核对 | mDNS、UDP 回退和配对端点已开发；完整 Captive Portal、多主机选择和现场退避需纳入后续验收。 |
| N2 安全绑定与正式 MQTT | 当前主线，尚未完成 | Stage 2C 已完成节点安全通道、NVS 与生命周期合同；Stage 2D 正在完成真实节点、TLS 候选、PREPARE/VERIFY 和正式 MQTT 验收。 |
| N3-L LoRa 星形单跳 | 尚未进入正式开发 | 在 N2/Wi-Fi 直连闭环后优先启动。普通 LoRa 子节点不得转发。 |
| N3-W ESP-NOW 单跳补盲 | 尚未进入正式开发 | 位于 N3-L 之后或按产品优先级并行；不实现 Mesh。 |
| S1 产品化 | 尚未开始正式闭环 | 黄金镜像、首启个性化、OTA、备份恢复、老化、现场试点和售后工具。 |
| N4-L 专用 LoRa 中继 | 未启动、条件式 | 只有现场证明星形单跳不足且增加网关不经济时才启动。 |

### 7.2 H3/N2 Stage 2 内部节点

| 子阶段 | 状态 | 主要结论 |
|---|---|---|
| Stage 2A | 完成并进入 main | manager 一次性配对会话与凭据生命周期核心。 |
| Stage 2B-1/2/3 | 完成并进入 main | 临时安全通道、发现/配对端点、默认关闭的 manager 装配。 |
| Stage 2C-1/2/3 | 完成并进入 main | 节点配对协议、安全传输、异步持久化和 MQTT 生命周期合同。 |
| Stage 2D-1～2D-6 | 源码、合同和 CI 阶段完成 | NVS、加密、双槽事务、候选验证、marker-last 激活和生命周期装配。 |
| Stage 2D-7 | 隔离实机包与可逆测试固件已准备 | 默认关闭，受一次性授权控制。 |
| Stage 2D-8 | 可逆实板链已执行过，存在失败与 recovery 证据 | 旧 D2/V67/V68 均冻结，不得重放。 |
| Stage 2D-9 V69 | no-network PREPARE 历史结果接受，但 TLS 输入无效 | V69 的 `ca_pem` 不是有效 PEM，不能进入 TLS 激活。 |
| Stage 2D-9R | 当前进行中 | 建立新的 TLS-valid `tlsvalid02` 候选、私密执行材料、公开描述符、公开 PKI、不可变 Artifact 和新的 D2。 |
| Stage 2D-10 | 尚未进入真实执行 | 仅在 Stage 2D-9R 新候选 PREPARE/VERIFY 成功并冻结后，才进入隔离 Broker TLS 激活。 |
| Stage 2E | 未开始 | 异常、撤销、恢复出厂、主板迁移、主机恢复和完整故障矩阵。 |

结论：当前不应提前开发 N3-L、N3-W 或 S1；应先完成 N2 的 Stage 2D-9R 和后续 Stage 2D-10/2E 闭环。

---

## 8. 下一轮立即计划

### Gate A：新会话重新复核

必须重新查询：

1. `main` 是否仍为 `a3a72d75480362999e70e180f33459198b3951b5`；
2. PR #180 是否仍为 `open/draft/unmerged/mergeable`；
3. PR #180 HEAD 是否仍为 `6d28b344d29089704ac73ee636e3688ee42704b8`；
4. PR #180 base 是否仍为 PR #176 的 `cf841f3e...`；
5. PR #176 是否保持冻结状态；
6. 当前 HEAD 的 9 项 CI 是否全部 `completed/success`；
7. Artifact `8617450189` 是否仍未过期，digest、head SHA 是否一致；
8. review binding、exporter、Python、OpenSSL 摘要是否一致；
9. 用户已提供的只读探测结果是否完整；
10. 两个 consumed marker 和公开文件存在状态是否未变化；
11. 固定公开 PKI 输出目标是否仍不存在。

任何一项漂移：

```text
STOP
AUTHORIZATION_RECORD_CREATED=false
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
REGENERATE_REVIEW_PACKAGE_REQUIRED=true
REQUEST_NEW_EXACT_U1=true
```

### Gate B：精确公开 PKI 导出 U1

Gate A 全部通过后，用户粘贴第 11 节完整授权文本。随后：

1. 创建有效期严格两小时的本地授权记录；
2. 创建不含公开证书内容、私密材料和私密路径的授权执行包；
3. 用户只执行一次；
4. 成功时生成固定公开 PKI ZIP；
5. 失败时按声明点决定未消费停止或永久 `CONSUMED_FAILED`；
6. 禁止自动重试或手工补写。

### Gate C：公开 PKI 导出闭环

成功后：

1. 记录公开 ZIP SHA-256、export binding SHA-256 和本 U1 consumed marker SHA-256；
2. 生成只读 closure probe；
3. 用户执行一次并上传公开 PKI ZIP；
4. 独立核验 ZIP 文件清单、模式、证书链、hostname、DER/SPKI、描述符和确定性重建；
5. 将公开 CA/Broker 证书材料导入 PR #180 的 `public_successor_tlsvalid02` 冻结目录；
6. 不导入授权记录、marker、私钥、密码、命令或私密路径。

### Gate D：新不可变固件候选

公开 PKI 冻结后：

1. 将 `tlsvalid02` 新 CA、candidate digest 和 unlock digest 绑定到专用 Stage 2D-9R 固件；
2. 保持生产 `f1_0_rc2.yml` 和现有产品 packages 不变；
3. 执行 host 合同、故障矩阵、最小 ESP32-C6 编译和完整 RC2 产品板 compile-only；
4. 使用相同源码、工具链和输入完成至少两次独立构建；
5. 要求 application、merged image、manifest 和 Artifact payload 摘要完全一致；
6. 生成新的不可变 Artifact 与 recovery Artifact；
7. 生成新的 D2 审核包和只读工具链探测；
8. PR 继续保持 Draft。

### Gate E：新的 Stage 2D-9R D2

只有 Gate D 完整冻结后，才能提出新的 D2。D2 预计只允许：

```text
一次擦除指定测试分区
一次写入不可变 tlsvalid02 固件
Flash 校验
自动 hard reset
一次 GH2D9R_PREPARE_V1
固件自动重启
一次只读 GH2D9R_VERIFY_V1
破坏性边界失败后最多一次 locked recovery
```

D2 不包含：

```text
ACTIVATE_PROFILE
CLEANUP_TEST_STATE
真实 MQTT/Broker TLS 会话
生产操作
Ready/merge/release/tag/deployment
```

### Gate F：Stage 2D-10 与 Stage 2E

- 新候选 PREPARE/VERIFY 成功并冻结后，回到 Stage 2D-10 G4，单独设计隔离 Broker TLS 激活门；
- TLS 激活、telemetry round trip 和注册确认成功后，进入 Stage 2E；
- Stage 2E 完成撤销、恢复出厂、主板迁移、主机恢复、Broker/manager 重启、网络重配和故障矩阵；
- 完成后才评估 Wi-Fi 直连小规模试点与 N3-L/N3-W。

---

## 9. 后续阶段目标和退出条件

### 9.1 当前短期目标：完成 Stage 2D-9R

退出条件：

- successor 公开 PKI 导出 U1 成功闭环；
- 公开证书材料冻结到仓库；
- `tlsvalid02` 固件两次独立构建完全一致；
- 新 immutable/recovery Artifact 冻结；
- 新 D2 review package 完整；
- 新 D2 实板 PREPARE/VERIFY 通过或失败后 recovery 闭环；
- 全程没有秘密泄漏、授权重放或生产操作。

### 9.2 中期目标：完成 N2 正式 MQTT 验收

对应 V0.5 N2 验收重点：

- 真实 CA 与 hostname 严格校验；
- NODE_ID、长期凭据和注册状态持久化；
- 断电重启不重复创建设备；
- 注册失败不显示添加成功；
- 网络重配保留 NODE_ID；
- 恢复出厂清除绑定；
- 路径和状态切换不产生重复 Home Assistant 实体；
- 本地传感器、LCD 五页和离线监测不受网络状态阻塞。

### 9.3 后续优先级

```text
1. Stage 2D-9R：TLS-valid PREPARE 候选闭环
2. Stage 2D-10：隔离 Broker TLS 激活和受控 round trip
3. Stage 2E：异常、撤销、恢复、迁移矩阵
4. Wi-Fi 直连小规模试点
5. N3-L：LoRa 星形单跳
6. N3-W：ESP-NOW 单跳补盲
7. S1：黄金镜像、首启、OTA、备份恢复、老化和售后
8. N4-L：仅现场证明必要时启动
```

---

## 10. 新一轮对话启动文稿

新对话首条消息使用：

```text
阅读《h3-n2-stage2d9r-g3r-successor-public-pki-u1-preauthorization-handoff-20260725-v1.md》，继续推进 H3/N2 Stage 2D-9R G3R successor。

本轮第一个且唯一的决策门是 U1-H3N2-STAGE2D9R-PUBLIC-PKI-EXPORT-20260725-01。

先重新复核：
- main=a3a72d75480362999e70e180f33459198b3951b5；
- Draft PR #180 为 open/draft/unmerged/mergeable，HEAD=6d28b344d29089704ac73ee636e3688ee42704b8；
- PR #180 base 为 PR #176 frozen HEAD=cf841f3e5a8cf04c5df9875c499b91ad4e4289cb；
- 当前 HEAD 的 9 项 CI 全部 completed/success；
- 公共 PKI U1 review Artifact ID=8617450189、GitHub digest=e763f5d359cdd63c942c589687343af4972beb3cf623ba299f28d71e35b6de87、review binding=a75eb347fea5109f6c4fa37d6a11b42a4cc4023ab136acc3f9c98fe29c8853b7；
- exporter、Python、OpenSSL、两个 consumed marker、公开文件存在状态和固定输出目标状态均与交接文档一致。

任一状态漂移时立即停止，不得创建、声明或消费授权，必须生成新的审核包和精确 U1。

复核全部一致后通知我粘贴交接文档第 11 节的完整授权文本。授权前不得创建授权记录或执行包，不得读取证书内容，不得连接测试板、串口、Flash、物理 NVS、网络或 Broker，不得执行 PREPARE、VERIFY、ACTIVATE 或 CLEANUP。

PR #180 和 PR #176 必须继续保持 Draft；不得 Ready、merge、release、tag 或 deployment。不得操作 M401A、T1、Home Assistant、Mosquitto、greenhouse-manager、eFuse、Secure Boot、Flash Encryption 或生产环境。

需要我授权或本地执行时通知我；其余安全的源码、测试、CI 和文档工作可以持续推进。上下文过长时及时归档并输出新的交接文档。
```

---

## 11. 下一轮待粘贴的精确 U1 授权文本

仅在新会话完成第 10 节全部复核并明确通知可以粘贴后，逐字粘贴以下全文：

```text
我授权 U1-H3N2-STAGE2D9R-PUBLIC-PKI-EXPORT-20260725-01，仅允许为 H3/N2 Stage 2D-9R G3R successor 执行一次、单次且不可重放的公开 PKI 材料导出。

本授权精确绑定：

repository=chrenguo-stack/HomeAssistant
pull_request=180
pull_request_state=open,draft,unmerged,mergeable
base_pull_request=176
base_source_sha=cf841f3e5a8cf04c5df9875c499b91ad4e4289cb
main_sha=a3a72d75480362999e70e180f33459198b3951b5
source_sha=6d28b344d29089704ac73ee636e3688ee42704b8
current_head_ci=all_completed_success

review_artifact_id=8617450189
review_artifact_github_digest_sha256=e763f5d359cdd63c942c589687343af4972beb3cf623ba299f28d71e35b6de87
review_binding_sha256=a75eb347fea5109f6c4fa37d6a11b42a4cc4023ab136acc3f9c98fe29c8853b7

authorization_schema=gh.h3.n2.stage2d9r-successor-public-pki-export-u1-authorization/1
operation=EXPORT_SUCCESSOR_PUBLIC_PKI
run_suffix=tlsvalid02

generation_authorization_id=U1-H3N2-STAGE2D9R-PRIVATE-EXECUTION-MATERIAL-20260725-01
generation_marker_sha256=428231f9e0e6a26c39701427b3e32531e18d08b54e341736b1189a78a06848a5
generation_status=CONSUMED
generation_replay_permitted=false

descriptor_export_authorization_id=U1-H3N2-STAGE2D9R-PUBLIC-DESCRIPTOR-EXPORT-20260725-01
descriptor_export_marker_sha256=a0c6ded9e371764a702b64fad58bd990b27808bae4467015116f9b189c8deceb
descriptor_export_zip_sha256=77fcded756d3914964138909ca2b51c2a20c60be76eed758049ef6c84ce4d8d1
descriptor_export_status=CONSUMED
descriptor_export_replay_permitted=false

public_descriptor_sha256=7021279f141f00cbf7e64fe8a20e89dd8b8ef3b9c4c7625ec28b79f6d65db2b6
candidate_digest_sha256=a0ff758217a1769c1876336c131cb85e64dcb2369758c649f36798cd8083aaf2
ca_pem_sha256=9d98b4aa1d87604e8c37aaa50892bf4cd47b8b8a0479acdabe78d41d39b36096
broker_certificate_der_sha256=4ca8731424c87ba61336f4bc4fb743137ed83c127ed1a214198b65e5b33b40f9
broker_spki_sha256=0ae2d32c2ddfb7b4b63c9ee4049291d9725a42a55721b0e78d53fcf5c9e1f72e

exporter_sha256=a1bb13049c59d54f4f31586b3f5c784e0a7fba39d17a7b6d5988840b73ee050e
python_executable_sha256=4e28e811a89aeac6eed668ae641c7f85f5831e42e8dc6cd9a85a3bcc032ec46a
openssl_executable_sha256=04ad05ce2e7eaf92116dac99a984cc0e589040a103589f93a9fe452832766973

output_target_selection_rule=HOME_DOWNLOADS_FIXED_SUCCESSOR_PUBLIC_PKI_EXPORT_U1_01
output_target_digest_sha256=892d8a5c84013ec8b7724f11554b2f4698b5d1001efcdf96a7919bd33c3a0618
output_target_exists=false
output_filename=Stage2D9R_G3R_Successor_Public_PKI_Export_U1_01_20260725.zip

授权记录的 issued_at 使用实际创建时的 UTC 时间，expires_at 必须严格等于 issued_at 加两小时。

authorized=true
one_shot=true
replay_permitted=false
automatic_retry_permitted=false

本授权仅允许执行以下离线操作：

1. 只读验证 successor 私密执行材料生成 U1 的 consumed marker；
2. 只读验证公开描述符导出 U1 的 consumed marker；
3. 只读读取 successor 托管根中的以下公开文件：
   - root-ca.cert.pem
   - broker.cert.pem
   - broker.fullchain.pem
   - public-descriptor.redacted.json
4. 验证上述四个公开文件均为普通文件、不是符号链接且文件模式为 0600；
5. 验证公开描述符 SHA-256、schema、stage、state、run suffix、Broker hostname、端口、TLS server name、候选摘要、CA 摘要、Broker 证书 DER 摘要和 Broker SPKI 摘要；
6. 验证公开描述符中的全部授权字段为 false，且不包含 MQTT 密码、持久化密钥、解锁令牌、私钥、密码数据库、PREPARE/VERIFY 完整命令、托管根或私密路径字段；
7. 验证根 CA PEM 的 SHA-256；
8. 使用精确绑定的 OpenSSL 只读解析根 CA 与 Broker 证书；
9. 验证 Broker 证书 DER SHA-256 和 SPKI SHA-256；
10. 验证 Broker 证书由精确根 CA 签发、用途适用于 TLS server，且 hostname 严格匹配 stage2d9r.local；
11. 验证 broker.fullchain.pem 中只能包含两个证书块，顺序必须严格为 Broker 叶证书后接根 CA 证书；
12. 计算根 CA DER、Broker PEM、Broker 完整证书链及其他公开材料的 SHA-256；
13. 在固定 Downloads 输出目标创建一个确定性 ZIP；
14. ZIP 中必须包括且仅限：
    - root-ca.cert.pem
    - broker.cert.pem
    - broker.fullchain.pem
    - public-descriptor.redacted.json
    - public-pki-export-binding.json
    - SHA256SUMS
15. ZIP 内所有文件模式必须为 0600；
16. public-pki-export-binding.json 只能包含公开摘要、公开身份、授权记录摘要及全部 false 的安全边界字段；
17. ZIP 中不得包含本次授权记录或 consumed marker；
18. 创建并最终更新本次公开 PKI 导出 U1 自身的 one-shot consumed marker；
19. 固定输出 ZIP 和 consumed marker 必须使用模式 0600；
20. 输出只允许包含公开 SHA-256、状态、布尔验证结果、时间戳和公开错误码。

禁止读取或导出以下内容：

- private-custody-descriptor.json；
- mqtt-password.hex；
- persistence-key.hex；
- unlock-token.hex；
- root-ca.key.pem；
- broker.key.pem；
- mosquitto.password；
- mosquitto.stage2d9r.conf；
- mosquitto.stage2d9r.acl；
- prepare-command.txt；
- verify-command.txt；
- 任何其他秘密值、私钥、密码数据库内容、完整命令内容或私密文件内容。

禁止在终端输出完整证书内容、私密托管路径、授权记录内容、原始秘密值或任何私密材料。

本授权不允许修改 successor 托管根内的任何现有材料，不允许覆盖现有输出目标，不允许使用其他输出目录、文件名、导出器、Python 可执行文件或 OpenSSL 可执行文件。

本授权不允许连接测试板或第二块设备，不允许打开串口，不允许擦除、写入或读取 Flash，不允许物理 NVS 操作，不允许打开网络或套接字，不允许启动 Broker，不允许执行 PREPARE、VERIFY、ACTIVATE 或 CLEANUP。

禁止使用生产 Broker、生产 MQTT 凭据、生产主题、Home Assistant、greenhouse-manager、M401A、T1 或任何生产服务。禁止操作 eFuse、Secure Boot 或 Flash Encryption。禁止 Ready、merge、release、tag 或 deployment。

禁止修改或重放 PR #176、旧 PKI、旧命令材料、U1-03、U1-04、D2-01、successor 私密材料生成 U1、公开描述符导出 U1、V69、Stage 2D-8、旧 Artifact 或旧 consumed marker。

在声明或消费本 U1 前，如任一 PR 状态、base、main、HEAD、CI、审核 Artifact、审核绑定、generation marker、descriptor export marker、descriptor export ZIP、public descriptor、exporter、Python、OpenSSL、公开文件存在状态、输出目标选择规则、输出目标状态或输出目标摘要发生变化，必须立即停止，不得声明或消费本授权，并重新请求新的精确 U1。

声明并消费本 U1 后，如任一步骤失败，必须立即停止后续步骤，将本授权永久记录为 CONSUMED_FAILED；不得自动重试、手工补写、覆盖输出、重放或使用替代导出器、替代工具链、替代输出目标、替代证书或替代公开描述符。

本授权不构成任何 D2、实板、Broker、PREPARE、VERIFY、ACTIVATE、CLEANUP、Ready、merge、release、tag 或 deployment 授权。
```

---

## 12. 明确禁止重放与修改的历史链

以下全部永久冻结或退役：

```text
U1-03
U1-04
D2-H3N2-STAGE2D9R-G3R-20260725-01
V67 D2 chain
V68 physical attempt and recovery chain
V69 D2 and execution materials
Stage 2D-8 authorizations and artifacts
PR #176 frozen source and tlsvalid01 materials
旧 PKI
旧 command material
旧 immutable/recovery artifacts
旧 consumed markers
```

本轮已消费、同样不得重放：

```text
U1-H3N2-STAGE2D9R-PRIVATE-EXECUTION-MATERIAL-20260725-01
U1-H3N2-STAGE2D9R-PUBLIC-DESCRIPTOR-EXPORT-20260725-01
```

---

## 13. 归档提交状态

本轮开发成果已经全部提交在 Draft PR #180；本交接文档和状态快照单独提交在归档分支，避免改变 PR #180 HEAD 和审核 Artifact 绑定。

归档文件：

```text
docs/handovers/h3-n2-stage2d9r-g3r-successor-public-pki-u1-preauthorization-handoff-20260725-v1.md
docs/acceptance/h3-n2-stage2d9r-g3r-successor-public-pki-u1-preauthorization-state-20260725-v1.json
```

归档分支不得作为公开 PKI U1 的 `source_sha`。下一 U1 仍只绑定 PR #180 的：

```text
6d28b344d29089704ac73ee636e3688ee42704b8
```

本轮对话至此结束。下一轮从第 10 节启动文稿开始，不得在本轮继续签发授权。
