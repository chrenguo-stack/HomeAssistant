# N3-W T1 S1 只读软件归属与单 HA 目标分类（2026-10-10）

## 范围与来源

- 当前路线：保留 Armbian，不继续旧 R4/B1I1；仅按精确归属重建 N3-W 软件。
- 用户冻结的最终产品目标：**一套 Home Assistant，不是两套**。
- 本文是脱敏结论，不包含任何执行指令、SSH 目标、容器完整 ID、实际主机路径或秘密值。
- 私有证据：`N3W_T1_S1_OWNERSHIP_20261010_084214.txt`；SHA256 `d0c278ae0ffb38b2caf5992203b3ef9513f4a8ab9599967f6e15ddb8071a5c32`。
- S1 输出有正常结束标记与禁止修改标记；报告未捕获独立的远端 SSH 最终退出码。

## S1 已证明

```text
R2_EXACT_CONTAINER_SET_UNCHANGED=true
CONTAINER_NAME_ID_BINDING=PASS_6_OF_6
HA_CONFIG_PATH_OVERLAP=false
BROKER_ALL_MOUNTS_IDENTICAL=true
BROKER_COMPOSE_FILE_IDENTICAL=true
SYSTEMD_UNIT_OWNERSHIP=PASS_6
LIVE_MUTATION=false
DATA_DELETE=false
BOARD_ACCESS=false
```

### Home Assistant

- `homeassistant` 属于独立 Compose project，host network，独立配置目录；存在 `configuration.yaml`、`.storage/core.config_entries`、`automations.yaml`、HA 数据库。
- `fc4-homeassistant` 属于 `n3wfc4` Compose project，private network，不与上述配置目录重叠；存在 `configuration.yaml`、`.storage/core.config_entries`、HA 数据库，但 `automations.yaml` 不存在。
- 当前宿主 TCP 8123 监听的进程名称为 Python，**尚未通过 PID 绑定到具体 HA 容器**。两套 HA 均有持久化状态，不能把其中一套描述成空容器。
- 默认选择：优先评估将独立 `homeassistant` 作为正式单实例；`fc4-homeassistant` 为历史重复清理候选，待确认接入、实际使用和迁移边界，**尚未授权删除**。

### Broker 与 systemd

- `n3wfc4-broker-1` 和已停止的 `recipes-broker-1` 使用同一 Compose 文件、完全相同的六个挂载与同一 8883 host publication 设置；不能把 recipes Broker 的数据看作独立或无关数据。
- Broker activation 和 ingress guard 均 active/enabled，证书生命周期 timer active/enabled、对应 service inactive/static。两只旧 P4 部署 unit 为 failed/static 且在运行时 systemd 目录。
- 网络安全入口 guard 在新 Broker 明确替代之前必须保留。

## 分类与后续界限

```text
S1_METADATA_CLASSIFICATION=PASS
S1_HA_LIVE_PORT_OWNER=UNKNOWN
S1_HA_MQTT_INTEGRATION_OWNER=UNKNOWN
S1_RECIPES_INDEPENDENT_BUSINESS=NOT_PROVEN
TARGET_HOME_ASSISTANT_COUNT=1
S2=EXACT_PRIVATE_CLEAN_MANIFEST_WITH_TARGETED_READONLY_DEPENDENCY_PROOF
EXACT_DELETE_AUTHORIZED_SET=EMPTY
DELETE_READY=false
S0_KF101_ROOT_CAUSE=TBD
STOP=true
```

下一步只通过**对话中直接提供的最小只读操作**补齐真实 8123 监听与各 HA 容器的进程绑定、两套 HA 的相关集成类型（仅输出计数/布尔值，不输出配置内容或凭据），然后完成私有精确清理范围审核。任何旧状态、卷、容器的删除均必须在清单明确后一次性取得范围确认。GitHub 只存脱敏结论，不再作为终端指令发布入口。
