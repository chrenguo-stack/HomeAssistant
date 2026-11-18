# N3-W T1 P3 U7 只读预检

当前实机停在 U6。旧版 Home Assistant 镜像恢复包已验证并落盘，此阶段准备的是 U7 的只读入口。 [U6 实机归档](./N3W_T1_U13B_P3_U6_READONLY_PREFLIGHT_20261118.md#u6-实机执行回执)

| 绑定项 | 值 |
| --- | --- |
| U6 执行候选 | `c8e77c76af5ea05445baf6f3d977903a91e860d3` |
| U6 事务 SHA-256 | `c63c215a3b68041c523a74b682725fc6ca42538a458e8357bf79fe27b20f27b8` |
| U6 实机回执 SHA-256 | `8c08a06a1bfaa3a4c27dc9a064f3a0b0904f4d326fa04fd3e36bb0b4a7bf8b9a` |
| 旧镜像归档 SHA-256 | `31108a725e6b6530c68834218d9e41579055d7fe2718b3f42902b71237dc8e5f` |
| 目标镜像归档 SHA-256 | `be30c4778bf537258d9e3825524c79532f20e8eb7a82136f560110d8f44b418d` |

## 预检范围

- 从 P3 原始账本复核冻结产品源码，核对已消费的 U6 授权、持久成功回执以及仍处于 U6 的主机事务。
- 复核当前服务和容器、原镜像绑定、OTA 状态、USB 会话和事务镜像。对目标和旧镜像归档重算摘要。
- 核查 Home Assistant 正在使用的可写数据挂载，检查数据树、加密密钥文件的元数据、备份工具和 USB 可用空间。密钥内容不读取、不输出。实际 SQLite 完整性检查留在应用服务停止后的备份流程。
- 确认 USB 的备份目录没有残留数据。结束前再核对事务、USB 元数据、归档身份及运行连续性。

执行入口为 `tools/execution_packages/n3w/r7a/u13b_p3_u1_u4_recovery/check_ha_backup.py`。先在精确提交上执行 `--mode source-check`，再从 Mac 执行 `--mode preflight`。后者只通过 SSH 观测 T1，回执写入 Mac 的证据目录。预期返回 `P3_U7_READONLY_PREFLIGHT_PASS / EXIT_CODE=0`，且 `transaction_phase=U6_PREDECESSOR_RECOVERY_PREPARING`、`u7_transition=false`。实机预检回执待获取。

## 后续 U7 停点

本笔 U7 候选将绑定新预检回执，复用 P3 冻结的 `HaUsbU7BackupController` 和 `ProtectedHaDataBackupProvider`。历史 R32 仅供复核 U7 执行顺序和通过条件，历史事务和授权不能用于本笔。 [历史 R32 执行器](../../tools/execution_packages/n3w/r7a/u7_repaired_ha_quiesce_data_backup_r32/executor.py)

另行批准后，U7 停止 Home Assistant 和温室管理服务，使备份数据保持一致。MQTT Broker 继续运行。U7 成功条件为加密备份已校验，主机和 USB 事务同步到 `U7_HA_QUIESCED_DATA_BACKUP_PREPARING`，并记录两项应用服务已停止。按冻结产品流程，U7 成功停点保持这两项服务停止。备份失败后的恢复由产品控制器处理，并以实机状态为准。后续 U8 和镜像切换均在本笔 U7 停点之后。

## U7 实机只读回执

预检提交 `d6c00259083af2bcb050949b35c25899b65eec53` 从 Mac 执行，返回 `P3_U7_READONLY_PREFLIGHT_PASS / EXIT_CODE=0`。回执 SHA-256 为 `fe70384df1773fc98db3668a148c355bc5373f46c00bb3520b367bdb936674a3`，已依据终端 JSON 复算。完整回执留在 Mac。 [预检源码 CI](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44274576998)

事务仍为 `U6_PREDECESSOR_RECOVERY_PREPARING`，U6 事务和回执摘要一致，USB 元数据与两个镜像归档一致。Home Assistant 数据挂载及备份条件通过，三个服务的运行连续性通过。USB 可用 28,134,289,408 字节，备份所需余量为 2,684,354,560 字节。

## U7 执行候选

- `ha_backup.py` 复用冻结的 P3 控制器。正式执行时重新跑实机预检，领取授权前在事务锁下重新核对 U6 摘要、挂载、归档状态和容量。停止应用服务前再次核对同一笔事务和两个归档。
- 授权编号 `N3W_T1_U13B_P3_U7_HA_DATA_BACKUP_20261118_01`。执行必须通过候选之上的独立授权提交 `ha_backup_grant.json`，绑定候选提交、预检回执、U6 事务、目标归档、U7 停点和有效期。授权仅消费一次。
- 仅在产品完成加密备份校验、主机和 USB 元数据一致、Home Assistant 和温室管理服务停止且 MQTT Broker 连续运行后，写入 U7 持久成功回执。实机授权和正式执行待确认。
- 启动后若 SSH 断开或超时，使用同一执行器的 `--mode status` 只读验证远端账本、事务、USB 和备份，耗尽授权后不可重放。备份失败时由产品控制器尝试恢复原应用服务，回执区分恢复尝试及产品验证结果。

## U7 实机执行停止与只读补验

操作者从候选 `879f951e543a585a0c35aa0b1677557b741f62f9` 和授权提交 `cb7f0fb5757b2d744dd272895e4923242ead2191` 执行了一次。原执行返回 `STOP_POSTCLAIM / EXIT_CODE=2`，回执 SHA-256 为 `f467552cac646061585bb9a8b84e2100222bab425ab96f23a6b902eaed74587b`，已依据终端 JSON 复算。授权已消费，禁止重放。 [授权提交](https://github.com/chrenguo-stack/HomeAssistant/commit/cb7f0fb5757b2d744dd272895e4923242ead2191)

停止在 `verify_u7_and_stop`，原因 `u7_application_owner_not_inactive`，未尝试恢复应用服务，回执记录 `u8_plus=false`。按源代码执行顺序，产品已返回备份验证完成，执行器已通过其前置事务、USB 镜像和归档检查，最后拒绝了应用单元状态。当前现场仍需从 Mac 只读补验。

P3 执行器原先只接受 `inactive`。冻结产品的停止合同及历史 KF-158/R32 也接受经证实完全停止的 `failed`。补验要求单元主进程已退出、重启次数为零、两项应用容器均已退出且身份不变、Broker 单元和容器保持原身份。使用同一笔 U7 失败回执、主机和 USB 的 U7 状态及旧镜像验证回执作为绑定，再核对目标和旧镜像的摘要，以冻结产品代码验证备份的哈希、认证值、解密清单及与当前静止数据的对应关系。 [KF-158 记录](./KNOWN_FAILURES_AND_REGRESSION_GUARDS.md)

`ha_backup.py --mode status` 在这一笔失败回执匹配且独立补验通过时返回 `P3_U7_POSTCLAIM_EVIDENCE_VERIFIED`，并记录原执行成功回执不存在。该入口只读，原失败回执保持原样，实机补验结果待获取。
