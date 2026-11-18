# N3-W T1 P3 U6 只读预检

## 当前实机停点

本笔 P3 已在提交 `974b2fadba200a769b18ddbb6d1a2beb33decab7` 上实机到达 `U5_INSTALL_REQUESTED_REVALIDATING`。主机和 USB 的 U5 事务 SHA-256 为 `53141824bb5bd89f0911e217900ad50acee44cf6ef0ead891e867042a89dfe12`，持久回执 SHA-256 为 `cfef0e884513b93defb184bee46b46bb17268ab789a3b9abdbf3656604ea9577`。U5 安装意图授权已消费，产品的 U9 授权仍未登记。 [U5 实机归档](./N3W_T1_U13B_P3_U5_READONLY_PREFLIGHT_20261118.md#u5-实机执行回执)

## 预检入口

`tools/execution_packages/n3w/r7a/u13b_p3_u1_u4_recovery/u6_preflight.py` 提供 `source-check` 和 `preflight` 两种模式，均绑定精确提交并依赖原 P3 提交 `cddadc5bff1a00d4392de33680a5b0ad0acace1e`。实机执行通过操作者 Mac 上已固定主机密钥的 SSH，私有结果落在 `p3-u6-readonly-result.json`，终端输出用于归档。

预检核对以下内容：

- 本笔 U5 的已消费账本、持久回执、主机事务和 USB 的五份事务元数据。
- 目标归档大小和摘要、USB 绑定和挂载、恢复和数据备份目录的残留。
- HA 旧运行镜像及持久配置绑定、目标镜像尚未载入、三个容器和服务所有者的状态、OTA 接口的 U5 状态。
- 使用本笔冻结的 P3 预算和产品容量公式重新测算 USB 余量。U6 实际执行时还需在写入前重复验证。

`P3_U6_READONLY_PREFLIGHT_PASS` 表示实机条件已核对并且事务仍在 U5。预检只查询状态，既不导出镜像，也不写入事务或领取授权。

## 后续 U6 边界

取得并归档本笔只读回执后，续跑入口绑定该证据，复用冻结的 `HaUsbU6PredecessorController` 和 P3 发布参数。历史 R26 实机通过能验证产品动作和超时取证方式。对应的历史执行包绑定了另一笔事务和授权。 [R26 实机归档](./N3W_T1_U6_R26_LIVE_PREDECESSOR_RECOVERY_CLOSURE_20261114.md)

另行授权后，U6 的通过条件为主机和 USB 同步到 `U6_PREDECESSOR_RECOVERY_PREPARING`，并持久记录已校验的旧镜像恢复归档、运行连续性及阶段停点。SSH 等待超时以远端持久账本和只读状态为准。U7 的停服务和数据备份另行处理。
