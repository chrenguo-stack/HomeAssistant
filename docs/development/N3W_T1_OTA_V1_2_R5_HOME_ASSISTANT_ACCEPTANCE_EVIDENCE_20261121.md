# N3-W T1 OTA V1.2 R5 Home Assistant 验收证据

2026-11-21。依据 [V1.2 第 9、10 节及实施路线](N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.2_20261119.md) 和 [R2 代码对齐设计](https://github.com/chrenguo-stack/HomeAssistant/blob/41c06c1abf6ccaf05b977237a5b7bad3710f8031/docs/development/N3W_T1_OTA_V1_2_R2_SOURCE_ALIGNMENT_DESIGN_20261120.md)。审阅分支为 [PR #815](https://github.com/chrenguo-stack/HomeAssistant/pull/815)，主分支基线为 `4fde1b7c5cc0aa224fa3574b8b4cc638edd93647`。首批候选升级 HA，Manager 和 Broker 镜像沿用当前组合，验收仍检查被影响的收数路径。

## 原始镜像及恢复包证据

- `c654060c01f9108b6368cad276e8723f7f03245b` 的 [HA 目标绑定](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44902402062/job/136841036101) 已通过。测试用临时签名和模拟前代，对 GitHub 工件 `13391983948` 内的 835,309,535 字节原始压缩归档执行验签、私有暂存、投影及 `PREPARE` 准入。归档 SHA-256 为 `eba1da958fc9c759c30d1cb34445c364e895bcd8d5e6c0d8392ab6849ece9973`。该提交的 CI 终态为 22 个工作流通过、6 个按策略跳过。
- 同一提交的 [恢复候选包 14706023563](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44902402062/artifacts/14706023563) 经独立下载回读。ZIP SHA-256 为 `b4cdd6f76bbda13a7dcca47a75d6e9893224d16e4e643fa1da821a94900ec341`，包清单 SHA-256 为 `eb7c4aa6308977b4e3b8d8a65e886095a985d3e98fc03dee98bae500ad3f8ed8`。8 个交付文件与本地从源码树 `1130f228c27ec89f365ff7c6a3b69c1a4b7c05f5` 重建的字节一致。R6 须按所选提交重新绑定包与 CI。

## V1.2 第 9、10 节覆盖

| 场景 | 已有确定性证据 | 仍需核对 |
| --- | --- | --- |
| 单 HA 正常升级、重复请求、其余组件身份不变 | `test_install_requires_exact_existing_u4_admission` 和 `test_prepare_creates_only_u1_transaction` 确认重发仍只有原事务，授权保持未消费。`test_target_import_and_activation_select_the_bound_rollback_path[install_worker]` 走宿主安装入口并验证终态。 | 备用 T1 从普通用户入口验收。Broker OTA 和含 Broker 切换的多组件失败恢复在 HA OTA 完成后单独推进。 |
| 首次停服、旧镜像释放、目标写入、恢复数据发布、启动和提交前后中断 | `test_first_stop_requires_successfully_persisted_restart_binding`、`test_partial_first_stop_can_restore_without_usb_and_never_restarts_twice`、`test_release_and_boot_reconcile_exact_predecessor` 及目标激活参数用例覆盖持久边界。提交落盘失败后重入复核实际运行身份，已提交重入保留新版数据。 | 实际断电、重启时间和介质再次发现由备用 T1 取证。 |
| 材料破坏、校验失败与等效观察 | 目标、旧镜像与备份破坏各有提前拦截用例。`accept_fallback`、`accept_failed`、`accept_unavailable` 区分等效证据成功、业务失败和有界补验失败。 | 尚缺真实介质上的损坏与慢速对照，以及新版 checker 解析器故障的独立等效复核。 |
| 错盘、原盘返回、容量、其他 USB 内容 | `test_verify_existing_usb_media_from_bound_archives` 覆盖 UUID 冲突、错误设备、只读限制及工件漂移。正常准备用例检查同盘用户文件字节；`test_boot_restores_a_released_predecessor_from_bound_media` 覆盖错盘等待、原盘恢复、锁竞争和重复触发。 | 真实盘符变化、历史事务目录、临界空间和慢盘进展需要补证。 |
| 历史和配对、正常迁移与回滚、自然静默与真实故障 | `test_n3w_t1_core_updater_ha_data_evidence.py` 验证样本、原挂载及空历史。`test_n3w_t1_core_updater_ha_monitoring_evidence.py` 验证自然消息关联、拒收旧回执、预验自检和恢复后重新取证。目标激活用例验证成功保留新数据、失败还原旧数据。 | 真实 HA 历史保留策略、真实节点离线和恒定读数、生产认证与路由对照需实机证据。 |
| status 和恢复相互独立，旧记录及后置阶段投影 | 原盘恢复用例同时验证两侧：状态可读时，错误旧镜像仍阻止启动和终态；状态读取失败时，定时入口仍完成回滚。Manager 缺少发布投影时保留宿主阶段。`test_boot_entry_leaves_legacy_and_post_cutover_transactions_alone` 覆盖旧在途记录的接管边界。 | 按同一候选核对 U10–U12 的用户提示、页面断开、重新连接及卸载异常。checker 可信更新及规则版本冻结仍需单独复核。 |
| 停止的旧容器、重复业务实例和未触及的收数路径 | `test_target_acceptance_counts_only_running_service_instances` 覆盖保留已停止旧容器时验收通过，以及两个运行中的 HA 实例阻止验收。首个 HA 候选包含应用停启并验证收数。 | 未影响收数则免自检的跨组件场景随对应候选验证。 |

本轮新增对照和重复请求断言属于模拟证据。R6 仍须复核真实前代组合来源、受控签名和信任根、升级器可信更新路径及最终包。R7–R9 在取得相应授权后补实机结果。合并、生产信任配置和发布按独立授权处理。
