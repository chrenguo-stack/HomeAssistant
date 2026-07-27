# H3/N2 Stage 2D-9R G3R successor：Host Artifact 与私密托管预授权探针合同

## 目标

在生成新的实板 D2 审核包之前，先以只读方式确认：

1. 两次独立编译冻结出的 canonical immutable Artifact 未漂移；
2. Artifact 中的 build binding、候选摘要、CA 摘要、Broker 证书摘要、解锁摘要和分区边界一致；
3. 本机 successor 私密托管根仍位于固定选择规则下，目录模式为 `0700`；
4. 13 个私密材料文件及两个描述符的文件名、普通文件属性、非符号链接属性、非空状态和模式 `0600` 未漂移；
5. 私密描述符中的材料元数据可重算为已冻结的 private package SHA-256；
6. 私密描述符、公开描述符、生成 U1 consumed marker、immutable Artifact 之间的公开摘要与生命周期字段闭合；
7. 不读取 MQTT 密码、持久化密钥、解锁令牌、私钥、密码数据库、完整 PREPARE/VERIFY 命令或 Broker 私密配置内容。

## 允许读取

探针只允许读取：

- 审核包内的公开 immutable Artifact；
- `private-custody-descriptor.json` 的元数据；
- `public-descriptor.redacted.json` 的公开内容；
- 已消费生成 U1 marker 的安全元数据；
- 私密材料文件的文件名、类型、符号链接状态、模式和大小。

探针不得读取 13 个私密材料文件的内容。私密描述符中已有的 SHA-256 仅用于元数据重算，不得输出单项私密文件摘要。

## 固定输入

- canonical Artifact ID：`8638796771`
- canonical Artifact run：`30226719405`
- canonical Artifact source：`ac1d2a7a92323988c9cd946a3e018e4f1ba9463b`
- payload TAR SHA-256：`14e882f550ca92d14cf6776e518eb083b7344683b5534487bd28e95d93b29747`
- build binding：`742f663333837366a42da92b984a3b05c643f571`
- private package SHA-256：`7b585fc53b9201fd2c6161e544ac062d4223f509bfc86a10052d97907e4f55bb`
- public descriptor SHA-256：`7021279f141f00cbf7e64fe8a20e89dd8b8ef3b9c4c7625ec28b79f6d65db2b6`
- generation marker SHA-256：`428231f9e0e6a26c39701427b3e32531e18d08b54e341736b1189a78a06848a5`
- generation authorization record SHA-256：`99d5f8cf5a0a12d921497ce04b7dc95161fc77ee79e79ddf50d6cb2535473817`

## 输出边界

成功输出只包含：

- 公开 Artifact 摘要；
- build binding；
- 已公开的候选/CA 摘要；
- consumed marker 摘要和状态；
- private package 总摘要；
- 私密描述符自身 SHA-256；
- 文件数量、模式及布尔验证结果。

输出不得包含：

- 绝对私密路径；
- 单项私密材料文件摘要；
- 原始密码、密钥、令牌或私钥；
- 密码数据库内容；
- PREPARE/VERIFY 命令内容；
- 证书私钥或 Broker 私密配置内容。

## 探针结论的范围

`PASS_READ_ONLY_PREAUTH` 仅证明 Artifact 与私密托管的元数据、公开摘要及 consumed marker 闭合。它不证明当前私密文件内容仍与描述符中的单项 SHA-256 相同，因为本探针明确禁止读取这些内容。

私密内容的逐文件哈希、密码数据库交叉验证、候选重算、密钥/证书匹配和命令重建必须由后续独立、两小时、one-shot、不可重放、不可自动重试的精确 U1 授权。该 U1 完成前不得生成或批准实板 D2。

## 受保护边界

本探针和审核包不得：

- 创建、声明或消费任何授权；
- 修改私密托管根、描述符、marker 或 Artifact；
- 连接板卡、串口、网络或 Broker；
- 擦除、写入或读取 Flash/NVS；
- 执行 PREPARE、VERIFY、ACTIVATE 或 CLEANUP；
- 操作生产服务、M401A、T1、Home Assistant、Mosquitto 或 greenhouse-manager；
- 操作 eFuse、Secure Boot 或 Flash Encryption；
- 将 PR 标记 Ready，或执行 merge、release、tag、deployment。

任一固定 Artifact、源码、审核包、私密托管元数据、公开描述符或 consumed marker 发生漂移，必须 fail closed，重新生成审核包，不得继续进入私密内容 U1 或 D2。
