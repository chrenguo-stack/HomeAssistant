# H0/H1 PR #260 第二台 T1 V13R4R2 脱敏成功归档与 T0 稳定性观察

## 结论

V13R4R2 生产切换状态为 `PASS / COMPLETE`。一次性授权已经消费，禁止普通重放。2026-08-06T02:17:21Z 完成的 T0 只读稳定性观察为 `PASS`。

## GitHub 冻结绑定

- 仓库：`chrenguo-stack/HomeAssistant`
- 接受的 `main`：`ba6255cb3cb4067efd72b23f81f1a799c2c0026e`
- PR #260：Open、Draft、未合并
- PR #260 HEAD：`d628b896314efd0aff58da151e3669eb7fe21d44`
- PR #260 与 C06 PR #261—#269 未被本次工作修改

## 成功证据摘要

- V13R4R2 包 SHA-256：`6bc6f6a909bfbf7b20d192a439b6d5d694f7a6ec05169afc100945c1f0d5ac09`
- 已消费授权记录 SHA-256：`4845e1418653d1396bd298f72a6427bf628942d0150e6b06990263312fee0388`
- 本地成功闭环 SHA-256：`69fcd8beef5879afc0f3947b33e867eb37db9d8f7e331b2941bfdc39248ffbf1`
- ZIP、授权文件和完整运行日志不进入公开归档

## T0 只读稳定性观察

- 两台 T1 的 Home Assistant、Manager、Broker 均在运行，重启计数全部为 0。
- 目标 Broker 保持双网络结构：普通发布网络仅 Broker，internal 私有网络仅 Manager 与 Broker。
- Manager 保持 private-only；发布/私有网络网关优先级分别为 1/0。
- 宿主 MQTT 监听精确为 `127.0.0.1:1883`，无 LAN 1883，无 8883。
- 宿主 loopback、Home Assistant loopback、Manager 私有网络三条 TCP 路径均实时可达。
- MQTT entry 数量为 1；私有存储中的目标验证通过；实体/设备计数为 20/1。
- 切换完成时活动状态计数为 20；T0 快照没有读取或输出私有 API token，因此没有重新断言实时活动状态计数。
- 源 T1 到目标 LAN MQTT 的 3 次连接均被拒绝。

## 安全边界

本次观察只执行读取、TCP 建连检查和源 LAN 负探测。没有 MQTT 发布、生产写入、容器重启、节点或板卡操作，也没有修改 Docker daemon、sysctl、防火墙、匿名 MQTT 或节点凭据。

归档不包含内部地址、entry ID、flow ID、身份值、密钥、凭据、秘密值或秘密摘要。

## 授权

`D1-H0H1-PR260-SECOND-T1-V13R4R2-SANITIZED-SUCCESS-EVIDENCE-ARCHIVE-DRAFT-PR-AND-READ-ONLY-STABILITY-OBSERVATION-AUTHORIZATION-20260806-01`
