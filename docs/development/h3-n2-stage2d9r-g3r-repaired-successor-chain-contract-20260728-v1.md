# H3/N2 Stage 2D-9R G3R repaired successor chain 合同 V1

## 1. 决策与基线

本合同实现：

`D1-H3N2-STAGE2D9R-G3R-REPAIRED-SUCCESSOR-CHAIN-20260728-01`

分层基点固定为 PR #185 HEAD：

`662bd9027595a7dcfaaaedb977691b13b3fec74b`

串口握手修复源码绑定固定为：

`0a2c96b7615d9f222cf72fcf899b6caf3a7c875f`

该值只证明 ready repeater、连续串口捕获、分阶段超时和脱敏 transcript 的修复源码边界，**不是**未来物理执行包的最终绑定。

已接受 `main` 的两次零净差异纠正提交，当前冻结值改为：

`c16da1a2d4d8300198b0603359eea349a034e2ea`

PR #176 的 `mergeable=false` 被视为历史底层 PR 的非执行性合并状态变化。PR #176 必须继续保持 Draft、未合并且不修改。

## 2. 旧 D2 永久退役

旧一次性 D2：

`D2-H3N2-STAGE2D9R-G3R-SUCCESSOR-20260727-01`

终态保持：

`CONSUMED_FAILED / LOCKED_RECOVERY_COMPLETED`

PREPARE 和 VERIFY 计数均为 0。旧授权、旧私密命令、旧 candidate digest、旧 immutable、旧 recovery 和旧执行包均不可重放、替换、拼接或局部复用。

## 3. 双重绑定

新的链必须同时保留两个不同层级的绑定：

1. **repair source binding**：证明串口握手修复源码；
2. **final execution binding**：未来由 repaired successor 的最终源码 SHA、全新私密包公开摘要、新 candidate、PREPARE/VERIFY 命令摘要、两次可重现 immutable、locked recovery、repaired host controller 和工具链共同计算。

任何审核包、U1 记录、immutable manifest、recovery manifest 或 D2 请求若只包含 repair source binding，必须 fail closed。

## 4. 全新私密材料

新 run suffix 固定为：

`tlsvalid03`

未来 U1 只能在新的、唯一的 mode-0700 custody root 中生成以下 mode-0600 文件：

- `mqtt-password.hex`；
- `mosquitto.password`；
- `persistence-key.hex`；
- `unlock-token.hex`；
- `prepare-command.txt`；
- `verify-command.txt`；
- `root-ca.key.pem`；
- `root-ca.cert.pem`；
- `broker.key.pem`；
- `broker.cert.pem`；
- `broker.fullchain.pem`；
- `mosquitto.stage2d9r.conf`；
- `mosquitto.stage2d9r.acl`。

所有随机值、证书、命令、摘要、package digest、marker 名称和 custody root 都必须与 `tlsvalid02` 及更早链不同。公开仓库、CI 日志和公开 Artifact 只允许出现摘要、布尔状态、相对文件名和脱敏元数据。

## 5. U1 分层

### 5.1 Source/public freeze

本层只允许源码、测试、编译和公开审核 Artifact。不得生成秘密值。

### 5.2 Private material U1

未来独立精确 U1 最多允许一次：

- 验证新 custody root 不存在且位于用户私有目录；
- 生成全新私密材料；
- 用 MQTT password preimage 离线验证 Mosquitto `$7$` 条目；
- 重算 candidate digest；
- 离线确定性渲染并解析 PREPARE/VERIFY；
- 验证 unlock token 与 persistence key 均为非零 32 字节；
- 写入一个新的 consumed marker；
- 输出不含秘密值和私密绝对路径的公开结果。

U1 不得连接板卡、枚举串口、运行 esptool、启动 Broker 或执行 PREPARE/VERIFY。

## 6. Immutable 冻结

私密材料 U1 通过并完成公开摘要导出后，必须进行两次相互独立的干净编译：

- 相同最终源码 SHA；
- ESPHome `2026.4.3`；
- 相同公开 candidate 输入；
- 两次 payload 和 merged image 字节完全一致；
- 冻结 application、bootloader、partition table、merged image、build environment 和 final execution binding；
- canonical immutable Artifact 不得包含任何秘密值或私密路径。

旧 immutable Artifact、旧 merged image 和旧 build binding 只能作为拒绝复用的历史摘要。

## 7. Locked recovery

Recovery 仅允许处理测试分区：

- label：`gh2d8_p2d9`；
- namespace：`gh2d8_s2d9`；
- address：`0x400000`；
- size：`0x10000`；
- 最多一次 pre-read、一次 region erase、一次 post-read；
- post-read 必须全 `0xFF` 并匹配冻结 erased SHA-256；
- 禁止整片擦除、固件写入、PREPARE、VERIFY、ACTIVATE、CLEANUP、手动 BOOT 和额外复位。

Recovery 必须绑定新 immutable、final execution binding、目标 baseline 和未来精确 D2。只有 D2 已 claim 且越过破坏性边界后，合同指定的失败才可进入最多一次 locked recovery。Recovery 成功后仍终止为 `CONSUMED_FAILED / LOCKED_RECOVERY_COMPLETED`，不得返回正常执行路径。

## 8. Baseline、preflight 与物理 D2

后续必须保持三个独立门：

1. **baseline read-only gate**：独立 one-shot，只读唯一板卡、串口身份、Flash 几何和测试分区；
2. **host-only final preflight**：不连接板卡，只读公开 Artifact 与私密 custody 元数据，生成 `authorized=false` 请求；
3. **physical D2**：新的两小时内有效、one-shot、无重放、无自动重试精确授权。

物理 D2 最多允许一次 erase、一次 immutable flash、一次 flash verify、自动 hard reset、一次 PREPARE、固件自动重启后一次只读 VERIFY，以及满足条件时最多一次 locked recovery。Stage 2D-9R 仍禁止 ACTIVATE 和 CLEANUP。

## 9. 串口修复必须进入最终执行器

未来物理执行器必须显式安装 repaired handshake controller，并静态与运行时确认：

- 连续串口捕获先于隔离 Broker 启动；
- PREPARE ready 后才发送一次 PREPARE；
- 自动重启后重新选择并绑定同一板卡，再建立 VERIFY 捕获；
- 四类错误码不得退化为通用超时：
  - `PREPARE_READY_MARKER_TIMEOUT`；
  - `PREPARE_RESULT_TIMEOUT`；
  - `VERIFY_READY_MARKER_TIMEOUT`；
  - `VERIFY_RESULT_TIMEOUT`；
- 所有终态和超时路径保存 mode-0600 脱敏 transcript；
- frozen V1 executor 继续独占命令解析、授权、重放门和 NVS 写入。

## 10. 当前 D1 允许与禁止

当前允许：新分层 Draft PR、合同、source-only generator、validator、静态/主机模型测试、编译工作流和公开 review Artifact。

当前禁止：秘密生成、私密托管写入、授权记录、claim/consume、板卡、USB/串口枚举、串口打开、esptool、Flash/NVS、网络、Broker、PREPARE、VERIFY、ACTIVATE、CLEANUP、Ready、merge、release、tag 和 deployment。

任一 SHA、PR、CI 或 Artifact 状态在冻结前漂移，必须停止并请求新决策。
