# H3/N2 Stage 2D-9R G3R 私密内容绑定 U1-04 审核说明

## 历史 U1-03 处置

`U1-H3N2-STAGE2D9R-PRIVATE-CONTENT-BINDING-20260724-03` 已在声明后失败并永久消费，状态为 `CONSUMED_FAILED`。失败码为 `BROKER_CERTIFICATE_DIGEST_MISMATCH`，对应 consumed marker SHA-256：

`8aa4a1bcc20f55cf027d1e047286e8289682af7c261d9afb540641427bce15c7`

该授权不得重放、重试或转换为其他操作授权。

## 根因修正

V1 验证器错误地把 Broker 证书 PEM 文件原始字节摘要，与公共描述符中定义的 DER 证书摘要进行比较。修正版使用：

`openssl x509 -in broker.cert.pem -outform DER`

随后计算 SHA-256，并继续执行私钥/证书 SPKI 匹配、证书链、hostname、完整链、密码数据库格式及授权 marker 交叉绑定校验。

修正版还要求在任何新的私密内容读取前，精确绑定 U1-03 的 `CONSUMED_FAILED` marker、授权记录摘要和失败码。

## 新请求

新请求 ID：

`U1-H3N2-STAGE2D9R-PRIVATE-CONTENT-BINDING-20260724-04`

审核包只允许执行工具链与既有公开/保管元数据的预授权探测。审核包不包含授权记录，不包含授权执行启动器，也不授权读取私密命令材料或私密 PKI 内容。

未来只有一份新的、最长两小时、一次性、不可重放且不可自动重试的精确 U1，才可授权一次离线只读私密内容绑定验证。成功或失败均永久消费该新授权。

## 明确禁止

- 输出、复制或导出原始解锁令牌、私钥、MQTT 密码、密码数据库内容、私密路径或授权记录；
- 网络、Wi-Fi、MQTT、Broker/Mosquitto；
- 实板、USB、串口、Flash、物理 NVS；
- PREPARE、VERIFY、ACTIVATE、CLEANUP；
- eFuse、Secure Boot、Flash Encryption；
- M401A、T1、Home Assistant、greenhouse-manager 或生产环境；
- Ready、merge、release、tag 或 deployment。

任一 PR、main、HEAD、CI、Artifact、工具链、审核包、保管根、描述符、历史 marker、候选、不可变 Artifact 或恢复 Artifact 绑定变化时，必须在授权声明前停止并重新请求授权。
