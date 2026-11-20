# N3-W T1 U13B P3 U8 恢复材料验收

实机当前停在 U7。Home Assistant 和温室管理服务处于停止状态，MQTT Broker 仍运行。加密备份已通过独立只读补验，并与停止后的源数据一致。 [U7 实机停点](./N3W_T1_U13B_P3_U7_READONLY_PREFLIGHT_20261118.md#u7-实机停点确认)

| 绑定项 | 值 |
| --- | --- |
| U7 事务 SHA-256 | `2f45f6eee5fa59d0dafe53cedc23c11d62de35e949fb645ea8fd74b3d8d861a2` |
| U7 独立补验回执 SHA-256 | `27739cf29a883c4ee58d8cc6094099f4fd4e36a056dd94acfeb28d29bb203e73` |
| 加密备份元数据 SHA-256 | `b0eb4545d5058f1fbb056f9032eef81ff755d24fe36a914f804392a20fcaf033` |

## 执行范围

- 正式执行先只读核对本笔 U7 事务、原 U7 失败账本和归档补验。验证目标和旧镜像、加密备份认证及其与静止源数据的一致性、USB 挂载身份、恢复余量和应用服务停机状态。任一项不符即停止在授权领取前。
- 在主机事务锁下核对 U7 原文、归档、备份元数据和服务状态并重新核算容量。复用冻结的 `record_recovery_admission` 计算恢复内容清单，先写 USB 元数据并校验，再写主机事务。实机到 `U8_RECOVERY_ADMISSION_COMPLETE` 即停。
- U8 仅写本阶段账本和事务元数据。Home Assistant 和温室管理服务仍停止，MQTT Broker 仍由原容器运行。
- 同一文件系统 UUID 和准确的恢复材料是跨会话依据。USB 事务镜像按本次枚举写入的观测值核验，主机事务保留来源身份，后续只读核对可接受设备枚举号变化。 [KF-159 记录](./KNOWN_FAILURES_AND_REGRESSION_GUARDS.md)

入口为 `tools/execution_packages/n3w/r7a/u13b_p3_u1_u4_recovery/recovery_admission.py`。可以用 `--mode preflight` 独立只读检查，正式执行也会自行完成预检。`--mode execute` 需要候选之上的独立授权提交 `recovery_admission_grant.json`，绑定候选、U7 摘要、补验回执、目标归档、有效期和 U8 停点。`--mode status` 用于事后只读核对。授权消费后不可重放。

实机执行待明确批准。预期回执 `P3_U8_RECOVERY_ADMISSION_PASS / EXIT_CODE=0`，含清单摘要且 `u9_plus=false`。
