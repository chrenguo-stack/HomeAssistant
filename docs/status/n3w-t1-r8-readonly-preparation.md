# N3-W T1 OTA V1.2 R8 只读准备

2026-11-22（新加坡时间）。范围限备用 T1，固定验收 Home Assistant `2026.10.0 → 2026.10.4`。当前停在只读准备，实机取证由操作人在 Mac 执行。

## 已核对的来源

- `main` 为 `4fde1b7c5cc0aa224fa3574b8b4cc638edd93647`。[PR #815](https://github.com/chrenguo-stack/HomeAssistant/pull/815) 仍为草稿，候选 `741a1463e7de065401749e47e59d30b295d5d6e8` 返回 25 项已完成且成功的工作流。依据 [R7 交接](https://github.com/chrenguo-stack/HomeAssistant/blob/82f738dd37a5ad99f66e9e69679027fa843d0ca0/docs/development/N3W_T1_OTA_V1_2_R7_BASELINE_PASS_TO_R8_NEW_CHAT_HANDOFF_V1.0_20261122.md) 和 `main` 的 [V1.2 方案及 R8 路线](https://github.com/chrenguo-stack/HomeAssistant/blob/4fde1b7c5cc0aa224fa3574b8b4cc638edd93647/docs/development/N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.2_20261119.md)。
- [R7 恢复包 14715501376](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44924757335/artifacts/14715501376) 和 [候选恢复包 14717720726](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44930275032/artifacts/14717720726) 已下载并核验 ZIP、清单所列 11 个文件和包内 `ha-recovery.pyz`。11 个文件的字节一致，两份清单分别绑定 `84da7cd68e2f` 和 `741a1463e7de`。候选清单 SHA-256 `55d188d61dec4f55540b20a32155e00fa11d3f7582581da9b9817b652859cdcb`。
- [出厂镜像 13070404405](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/41275979177/artifacts/13070404405) 和 [目标镜像 13391983948](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/41976542377/artifacts/13391983948) 的任务均成功，工件的 ID、源码、摘要及有效性与交接一致。本会话下载接口每件上限为 512 MiB，两个工件仍待在 Mac 回读。目标与前代标签、平台和压缩归档摘要见 [冻结清单](https://github.com/chrenguo-stack/HomeAssistant/blob/741a1463e7de065401749e47e59d30b295d5d6e8/infra/n3w-t1/upgrades/homeassistant-2026.10.4.json)。
- R7 回执的运行 Manager `fresh-44e7d7472714` 对应源码没有 `_publish_ota_monitoring_self_test`。冻结候选的 `check-candidate-activation` 明确检查运行 Manager 的此能力。若新鲜观测仍为该镜像，须先资格确认并在独立授权下建立兼容 Manager 基线，然后在两条 R8 实机用例中固定 Manager 和 Broker。 [候选运行检查](https://github.com/chrenguo-stack/HomeAssistant/blob/741a1463e7de065401749e47e59d30b295d5d6e8/tools/n3w_t1_core_updater_ha_recovery_startup.py#L215) · [同候选 ARM64 Manager 的构建来源](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44930275030/artifacts/14716899788)

## 备用 T1 只读取证

从 Mac 通过已单独核对的 R7 备用机 SSH 目标运行 [`r8_prepare_mac.py`](../../tools/execution_packages/n3w/t1_ota_spare_readonly/r8_prepare_mac.py)。`--ssh` 使用原 R7 观察器，在宿主内存中读取运行身份、启动方式、健康、存储及事务，并补充 USB 文件系统与可见挂载命名空间计数。分区未挂载时，介质资格和可用空间继续待验。`--verify-images` 单独在 Mac 校验两个 ZIP 及各自的 HA 镜像归档，接受用工件 ID 命名的本地 ZIP 缓存。工具已做已知 ZIP、错误摘要拒绝、模拟 SSH 调用和 USB 输出验证。真实 Mac、备用 T1 和两个大工件的命令回执待取。

## 需要准备的两个独立恢复点

1. **前代 `2026.10.0`。** 使用出厂工件内精确 ARM64 HA 镜像，寻找同一备用 T1、在新版首次写入前取得的数据备份。用版本、镜像 ID、备份时间、事务或快照来源、加密归档及清单摘要绑定。在隔离的副本上做认证、解密回读和 SQLite 一致性验证，保留所需伴随文件和原元数据。旧 P3 的数据备份若绑定 `2026.10.4` 前代，只能作为该版本材料的线索。工厂构建及历史运行回执均不提供可恢复的数据副本。找不到匹配数据时，另行决定是否使用隔离构建的 `2026.10.0` 测试数据，其证据仅覆盖该数据集。禁止让旧版打开当前 HA 数据目录。
2. **当前 `2026.10.4`。** 核对实际运行镜像 ID、启动配置及受保护挂载，将 HA `/config`、Recorder 数据库及伴随文件、配置和注册表纳入一致性备份。若部署路径还要改变 Manager，保护其状态和回放数据，保存当前 Manager 镜像和绑定；保存所需的宿主配置、事务摘要和密钥可用性证明。备份置于有足够空间的独立受控介质，静止时制作认证加密归档，并以隔离副本校验清单、解密和数据库可读。密钥、备份内容及现场位置留在私有现场。现有 USB 文件及历史事务保留。未找到足够新的已验证副本时，单独确认停写与备份授权。
3. **回到当前版本。** 保存经验证的 `2026.10.4` 镜像/启动绑定及必要的正常挂载配置。恢复前代失败时，停止可能接触过前代数据的写入者，恢复独立保存的 `2026.10.4` 数据和标准 Compose 启动绑定。静止核对清单后再启动，验明 HA/Manager 的实际版本和运行身份、业务收数、受保护的历史或配置样本，以及 Broker 在验收期间的连续性。计算两个方向的峰值空间。若需更新 Manager，回退材料须能恢复此次更新前的组合。

R8 的正常升级、真实故障后自动回滚及关键边界断电续办均待实机。当前没有 R8 写入授权，未操作备用 T1 或介质。
