# T1 Provisioning Control 身份恢复合同 V1

## 背景

V85 只读诊断确认：Dynamic Security 中唯一具有控制能力的既有客户端为
`ghs_greenhouse_provisioning`，其 username、固定 client ID 与 role 绑定均存在，
但现场已无可认证的明文密码材料。现有 Manager password-file 不能作为该控制身份使用，
默认 admin 客户端也不存在。

Mosquitto Dynamic Security 在正常运行期间仅接受通过 MQTT 控制主题提交的管理命令；
现有控制身份明文不可恢复时，不能继续尝试 Home Assistant 密码轮换，也不能重放历史授权。

## 单独授权范围

现场执行必须取得新的明确授权：
`provisioning_control_identity_password_recovery`。

该授权仅允许：

1. 在 T1 私有目录生成新的 32 字节高熵 provisioning 密码；
2. 使用现场相同 Mosquitto 工具链，在隔离临时状态中生成与当前版本兼容的
   `encoded_password`；
3. 只替换既有 provisioning 客户端的 `encoded_password`；
4. 对 Mosquitto 容器执行一次受控重启以载入候选状态；
5. 验证新 username/password/client ID 三元组具有原有控制能力；
6. 失败时自动恢复原始状态并再次重启 Mosquitto。

授权不包含：

- 新建或删除 Dynamic Security client、role、group 或 ACL；
- 修改 provisioning username、固定 client ID 或 role；
- 修改 Manager、Home Assistant 或节点身份；
- 关闭 anonymous；
- 下发节点凭据；
- 读取或写入 Home Assistant `.storage`；
- 升级生产 Manager 或 Mosquitto 镜像；
- 重启 Home Assistant、Manager 或其他受保护服务。

## 准备阶段

执行前必须：

1. 要求 Mosquitto、Home Assistant、Manager 正常运行；
2. 记录容器身份、镜像、启动时间、重启计数和 Broker 配置指纹；
3. 验证 anonymous 仍启用；
4. 验证 Dynamic Security 状态文件为私有、运行账户所有且仅一个硬链接；
5. 精确确认一个 provisioning 客户端：
   - username=`ghs_greenhouse_provisioning`；
   - client ID=`gh-provisioning-greenhouse`；
   - role=`gh-service-greenhouse-provisioning`；
   - 凭据字段=`encoded_password`；
6. 创建不可覆盖的私有 recovery 目录，保存原始状态、候选状态、密码和 journal；
7. 使用同一 Mosquitto 版本在隔离临时文件中生成 encoded password；
8. 构造候选状态，并证明除目标 `encoded_password` 外完整 JSON 等价；
9. 使用隔离 Broker 验证候选状态能够加载，且新三元组可执行只读 `getClient`；
10. 验证错误 client ID 被拒绝且 anonymous 兼容访问仍成立。

准备阶段不得修改现场 Dynamic Security 状态或重启任何服务。

## 应用事务

1. 将 journal 标记为 `mutation_started`；
2. 停止 Mosquitto；
3. 再次核对现场状态指纹与准备阶段完全一致；
4. 使用同文件系统原子替换写入候选状态，并保持原 owner、group、mode；
5. 启动 Mosquitto；
6. 等待 Broker ready；
7. 使用新 provisioning 三元组执行只读 `getClient`；
8. 验证错误 client ID 被拒绝；
9. 验证 anonymous retained telemetry 可读；
10. 验证 Manager、Home Assistant 和节点链路恢复；
11. 验证 Home Assistant、Manager 未重启，Mosquitto 仅发生预期的一次重启；
12. 将 journal 标记为 `committed`。

## 自动回滚

应用后的任一验证失败时：

1. 保留失败证据和新密码；
2. 停止 Mosquitto；
3. 原子恢复原始 Dynamic Security 状态；
4. 启动 Mosquitto；
5. 验证 anonymous、Manager、Home Assistant、节点和 retained state 恢复；
6. journal 标记为 `rolled_back`。

若回滚验证失败，必须设置 `manual_recovery_required=true`，禁止重试执行器。

## 成功判据

- 仅 provisioning `encoded_password` 发生变化；
- 新 provisioning 三元组可执行控制面只读查询；
- 错误 client ID 被拒绝；
- anonymous 保持开启；
- Manager、Home Assistant、节点身份与 ACL 未变化；
- Home Assistant `.storage` 未访问；
- Mosquitto 只发生一次预期重启，其他受保护服务未重启；
- 私有 recovery handoff 已提交；
- 后续可重新执行 Home Assistant password-only 轮换，但仍不得关闭 anonymous。
