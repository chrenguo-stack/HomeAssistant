# N3-W T1 S0 R2 只读取证结论（脱敏归档）— 2026-10-10

## 执行范围与证据来源

- 当前路线：保留 Armbian、系统盘、网络、SSH、Docker Engine，仅规划在明确归属后重新部署温室专用软件。
- 保持停止 PR #540 的 R4/B1I1 回退开发；PR #541 仍为 Draft。
- 本记录仅是 S0 R2 已采集实测证据的**脱敏结论**。不包含 Mac Terminal 执行指令、完整容器 ID、实际宿主路径、凭据、原始 Docker JSON 或任何秘密内容。
- 原始取证报告保存在私有用户对话：`N3W_T1_SOFTWARE_OWNERSHIP_R2_20261010_082915.txt`。
- 私有文件 SHA256：`4b66d326787cd188ba3edf5f259854250428ef3d90504fab37395c26455250f5`。
- 本轮没有执行任何 T1 删除、重启、配置改变、板卡访问或烧录。

## 已证明的 S0 R2 元数据

| 范围 | 结果 |
|---|---|
| 现存 Docker 容器 | 6；全部取得且逐项配对真实 Full ID/name |
| JSON 容器检查 | 6/6 解析成功 |
| Mount 记录 | 28 = 26 bind + 2 volume，全部有 Source/Destination/RW |
| Docker volumes | 46，全部提取 mountpoint 与现存容器引用列表 |
| systemd 单元 | 6，全部取得 FragmentPath 和状态 |
| 失败 | 未见 `COMMAND_FAILED` / `UNIT_FAILED` |
| 收尾 | 出现 S0 R2 完整结束标记；私有日志未单独记录外层 SSH 返回码 |

### 关键归属发现

1. `greenhouse-manager` 与 `greenhouse-manager-p4-shadow` 为不同完整容器 ID。它们的三条只读密钥来源相同，三条业务 RW 挂载来源各自不同。两者均为温室重建候选，**不构成删除授权**。
2. `n3wfc4-broker-1` 与已停止的 `recipes-broker-1` 属于不同 Compose project 标签，但六个 Mount Source **完全相同**，包括 Broker 数据、配置、TLS/CA 与唯一被二者共用的 Docker 日志卷；两者还指向同一 Compose 文件。不可据容器名称证明 recipes 为独立业务，也不可把 Broker 文件或共享卷列入独占可删集合。
3. `fc4-homeassistant` 与 `homeassistant` 具有独立 Compose project、不同的 `/config` 宿主挂载。只证明两者配置目录在本次 Docker 映射中不重合，**不证明真实业务/MQTT 依赖完全独立**。前者待核归属，后者默认保留。
4. 46 个 Docker 卷中只有 1 个被两 Broker 现存容器共同引用，45 个当前不被这 6 个现存容器引用。**无现存引用不等于卷是可删垃圾**，全部暂时保留。
5. 两个旧 P4 deploy service 的 ActiveState 为 failed、文件位于运行时 systemd 目录；Broker 激活/入口保护为 active + enabled；证书生命周期 timer 为 active + enabled，service 为 inactive/static。未作任何 systemd 修改。

## 私有清理候选的阶段分类

- `N3W_EXCLUSIVE_CANDIDATE_ONLY`：greenhouse-manager 容器及自己的 RW 业务源、旧 P4 shadow 容器及自己的 RW 业务源；Broker **容器本身**是旧温室容器候选，但其数据来源有交叉引用，不得立即删除。
- `SHARED_OR_UNKNOWN_PRESERVE`：两个 Broker 共同引用的所有数据和 TLS/CA、Docker 日志卷；recipes-broker-1；fc4-homeassistant 的业务归属；45 个暂未找到现存引用的 Docker 卷；任何未证明无其他消费者的路径。
- `PRESERVE`：独立 homeassistant 容器及配置、Armbian/主机基础设施；当前 Broker 安全入口保护持续保留至后续明确替代。
- `SYSTEMD_REPLACE_CANDIDATE_ONLY`：六个已定位单元按新旧运行职责逐项审查；严禁批量禁用，尤其不能提前关闭 ingress guard。

## 停止点与遗留确认

`S0_R2_METADATA_BINDING=PASS`。此前 KF-101 的 Docker 格式化检查缺口已被 JSON 白名单提取绕过，但 R1 原失败根因仍为 TBD，不能宣称已修复根因。

`EXACT_DELETE_AUTHORIZED_SET=EMPTY`、`DELETE_READY=false`、`BOARD_ACCESS=false`、`STOP=true`。

下一阶段 S1 须独立确认 Broker 与 recipes 的共享配置/业务依赖、两套 HA 的实际消费者关系、系统服务的文件引用关系，才能将私有完整清单推进到可核准的删除范围。S0 R2 PASS **不授权直接清理**。

## 研发协作规则

后续 Mac Terminal / SSH 操作指令直接贴在对话中，不再新增到 GitHub。GitHub 仅保存必要的状态、设计、源码、测试结果和脱敏归档。
