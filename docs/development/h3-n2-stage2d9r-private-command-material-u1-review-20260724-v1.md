# H3/N2 Stage 2D-9R 私密命令材料 U1 审核 V1

## 1. 目的

Stage 2D-9R 不得继续使用全零 `unlock_digest`，也不得把原始 unlock token 写入 Git、Artifact、公开描述符或固件日志。

本审核定义一个后续一次性 U1，仅允许离线生成一个随机 32 字节 unlock token，并公开其 SHA-256 摘要作为最终不可变固件的编译绑定。

拟用授权 ID：

```text
U1-H3N2-STAGE2D9R-COMMAND-MATERIAL-20260724-01
```

当前尚未授权：

```text
U1_AUTHORIZATION_GRANTED=false
PRIVATE_COMMAND_MATERIAL_GENERATION_AUTHORIZED=false
```

## 2. 冻结源码合同

```text
generator=tools/h3_n2_stage2d9r_private_command_material_generator_20260724_v1.py
generator_sha256=60628bf274fdcca05e8644b30510f6abde2129a57e3e49ca5a12db30d7129563
gate=tools/h3_n2_stage2d9r_private_command_material_gate_20260724_v1.py
gate_sha256=512fb70c14d3ad983055fde4e85cb3814445df3ad7b5555695cc6c54575b4a6e
contract_test_sha256=5a7ed752b8e9e54f0f8c9e5f00f63360fa2a441ca38073dd67028506b57e6462
default_mode=read_only_toolchain_probe
execute_mode=explicit_--execute_only
custody_root_selection_rule=HOME_LOCAL_STATE_STAGE2D9R_PRIVATE_COMMAND_MATERIAL_V1
test_run_suffix=tlsvalid01
implementation_binding=3d3b67cac008adf30e90a51e891d0dd53b36df69
```

## 3. 主机只读探测闭环

```text
probe_result=PASS_READ_ONLY
probe_artifact_id=8571761445
probe_artifact_source_sha=0e7faaaed40433e4b7e0b985f4684b3d126f6948
probe_artifact_zip_sha256=914379b7640cf60591211d709f16197d6bff40ed7ab942bfb51468e59fa4407a
python_executable_sha256=4e28e811a89aeac6eed668ae641c7f85f5831e42e8dc6cd9a85a3bcc032ec46a
python_version=3.11.9 (v3.11.9:de54cf5be3, Apr 2 2024, 07:12:50) [Clang 13.0.0 (clang-1300.0.29.30)]
custody_root_digest_sha256=ef5f79be168fff686cabcc91fdc4109918d75d3311da1209dd8d0e381804006e
custody_root_exists=false
private_paths_included=false
secret_values_included=false
board_operation=false
network_operation=false
broker_started=false
```

终端粘贴内容只在最后一个说明性 `stage` 字段的前缀之后混入了重复 shell prompt。所有授权绑定字段均在此之前完整输出，启动脚本在 `set -euo pipefail` 下正常返回，且 `stage` 字段不作为授权安全绑定，因此不要求重放只读探测。

公开闭环记录：

`docs/acceptance/h3-n2-stage2d9r-private-command-material-toolchain-probe-l1-v1.json`

## 4. 授权后的唯一允许操作

一次有效 U1 最多允许：

1. 在生成前声明并锁定一次性授权；
2. 在用户 HOME 下唯一私密保管目录中生成一个 32 字节随机 unlock token；
3. 以 `0600` 保存原始 token；
4. 计算 `SHA256(bytes.fromhex(unlock_token))`；
5. 生成不含原始 token 的私密保管描述符；
6. 生成仅含 unlock digest、源码 SHA 和 implementation binding 的脱敏公共描述符；
7. 校验目录与文件权限、摘要绑定和公私密边界；
8. 将授权 marker 最终置为 `CONSUMED` 并停止。

## 5. 明确禁止

该 U1 不授权：

```text
重新生成或读取 PKI 私钥
读取或输出 MQTT 原始密码
启动 Mosquitto 或任何 Broker
网络、Wi-Fi 或 MQTT 连接
实板、USB、串口或芯片识别
Flash 或物理 NVS 读写擦除
PREPARE_CANDIDATE
VERIFY
ACTIVATE_PROFILE
CLEANUP_TEST_STATE
eFuse
Secure Boot
Flash Encryption
M401A
T1
Home Assistant
Mosquitto 服务
greenhouse-manager
生产凭据或生产主题
Ready / merge / release / tag / deployment
```

## 6. 精确绑定要求

最终 U1 必须绑定：

- PR #176 仍为 open、Draft、未合并；
- `main` 的精确 SHA；
- 最终 PR/source SHA；
- 精确 `implementation_binding=3d3b67cac008adf30e90a51e891d0dd53b36df69`；
- generator、gate 和 contract test SHA-256；
- Mac 上 Python executable SHA-256 与版本；
- 私密保管根目录选择规则及其路径摘要；
- 目标保管目录不存在；
- `test_run_suffix=tlsvalid01`；
- `ca_pem_sha256=cfcb6638ed61731270f3bf8e9e262c1512fbca8ff34d4b08b62186453233e963`；
- `candidate_digest_sha256=f22144e37372b883b7a38d07eff2980a865108cf7c8fed9bfdb9f198a030b5c5`；
- 当前 HEAD 所有绑定 CI 均为 `completed/success`；
- 有效期不超过两小时；
- 一次性、禁止重放、禁止自动重试；
- 规范化授权记录 SHA-256；
- 唯一 consumed marker。

任何绑定变化、授权过期、保管目录已存在、marker 已存在或生成失败，都必须停止并退休该授权。

## 7. 成功输出

成功结果只允许公开：

```text
unlock_digest_sha256
private_command_material_package_sha256
private_descriptor_sha256
public_descriptor_sha256
authorization_consumed_marker_sha256
source_sha
implementation_binding
authorization_consumed=true
private_paths_included=false
secret_values_included=false
board_operation=false
network_operation=false
broker_started=false
prepare_executed=false
verify_executed=false
```

原始 unlock token、私密路径、授权记录和 consumed marker 内容不得进入公开输出或 Git。

## 8. 后续关系

该 U1 只解决最终固件的非零 unlock digest 绑定。U1 完成后仍需：

```text
commit redacted public command-material descriptor
→ freeze final source using implementation binding + unlock digest + CA digest
→ produce byte-identical immutable firmware/recovery Artifact
→ host-only Artifact verification
→ separate exact D2
```

该 U1 不等于 D2，也不授权任何实板动作。
