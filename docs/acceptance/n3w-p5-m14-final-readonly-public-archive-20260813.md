# N3-W / P5 / M14 最终只读结果公共脱敏归档

## 结论

M14 已按以下分类关闭：

`M14_PASS_WITH_RECORDED_READONLY_VALIDATION_RECOVERY_DEVIATIONS`

本归档是公开仓库可保存的脱敏摘要，不包含完整运行证据、生产凭据、密钥材料、私有路径、主机地址、端口映射、容器实例身份或授权秘密。

## 仓库绑定

- 仓库：`chrenguo-stack/HomeAssistant`
- main：`9207678a3f351cbc4d9c61153aaa86fb64880fef`
- tree：`4e63251dfa992d3f6152122a445d022e9315e8d4`
- M14 合同 PR：`#313`，已合并

## 已验证事实

- 有效最终窗口采集恰好两份只读 Home Assistant registry 快照，间隔 35 秒。
- 两份 device/entity registry 原始 SHA-256 完全一致，并与 M14 锚点一致。
- 同一 NODE_ID 对应 1 个设备和 6 个实体；无重复 unique ID、无外部设备绑定。
- 设备及实体身份、创建/修改时间线在有效窗口内保持不变。
- Manager、Broker、Home Assistant 服务基线，Relay/no-candidate 路径和会话保持稳定。
- 有效窗口内持久化游标同步前进 7，满足至少 3 个自然接收帧要求。
- 验证过程未建立 MQTT 客户端连接，未修改服务或设备。

## 恢复历史

最终分类保留了此前只读验证恢复过程：三次快照前采集器/材料绑定不完整、一次 70 秒观察窗口超限，以及随后一次满足 35 秒边界的有效恢复。所有不完整尝试均未产生服务或设备变更，且没有在同一授权下重试或补采第三份快照。

## 声明边界

- 本结论证明当前证据链中的 M14 身份连续性，不制造不存在的 pre-M01 独立 registry 哈希对。
- M07 transcript 不作为独立 Home Assistant 身份证明。
- M13 的 `M13_PASS_WITH_RECORDED_EXECUTION_DEVIATION` 及禁止重放边界继续保留。
- M14 完成不自动等同于 N3-W 全范围开发完成；仍需独立范围闭环审计。

机器可读事实、完整证据 SHA-256 索引及脱敏声明见：

`docs/acceptance/n3w-p5-m14-final-readonly-public-archive-20260813.json`
