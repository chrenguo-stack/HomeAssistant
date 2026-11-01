# N3W T1 F5 V2 源码设计复核 — 2026-10-19

## 0. Gate

~~~text
TASK=N3W_T1_F5_PRODUCTION_PROCESS_V2_SOURCE_DESIGN_REVIEW_20261019_01
RESULT=CLOSED_PASS_AFTER_DESIGN_REPAIR

REVIEW_MAIN=9c81b889d97ed896b80d27af15069d16af0e0bdb
REVIEW_PR=622
REVIEW_SCOPE=DESIGN_AND_EXISTING_MAIN_SOURCE_ONLY

PRODUCT_SOURCE_IMPLEMENTATION=false
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
MERGE=false
~~~

本轮重新读取 current main、PR #622 设计文档、ADR-0010 以及 current main 中已经实机关闭的
F2/F3/Provision/F4 源码与历史 fresh-T1 证据。

结论：V2 的“标准 fresh Armbian -> 自动部署 -> 一次重启 -> 独立验收”方向成立，
并且比 V1 更适合当前产品。但源码实现前必须修正若干边界。相关设计修正已在本 PR 内完成，
因此本轮没有遗留 source-design blocker。

## 1. Review findings

### A1. Standard Fresh Armbian contract — PASS

现有真实 F2 证据已经证明过一台 fresh T1 的以下基线：

~~~text
Armbian OS 26.05.0 resolute
Ubuntu 26.04
aarch64/arm64
firstboot disabled/inactive/success
SSH password management PASS
NetworkManager active
default route / DNS / NTP PASS
Docker baseline MISSING:FRESH_HOST
product containers/images/volumes absent
product paths/units/listeners absent
old transaction/authorization/staging residue absent
~~~

current main 的 F2 executor 也已经冻结对应 OS/Armbian/board contract。

因此 V2 可以把这组“关键基础信息”定义为 Standard Fresh Armbian，不需要继续兼容任意旧主机状态。

### A2. Docker absent as fresh baseline — PASS

真实 fresh-T1 evidence 已证明 Docker baseline 为 MISSING。
V2 将 Docker absent 作为 normal production entrance 是有证据支撑的有意收窄。

如果未来官方 Armbian 镜像改变并预装 Docker，应修改架构合同和 exact release，而不是运行时增加 ownership 猜测。

### A3. qualification 不能把连接失败当成 target 不合格 — REPAIRED

原 V2 文档只有 PASS/FAIL，容易把 SSH/网络/只读 probe 失败误判成“需要重装”。

已修正为：

~~~text
PASS
FAIL_REFLASH_REQUIRED
STOP_UNAVAILABLE
~~~

其中 STOP_UNAVAILABLE 只表示证据不足，未发生 target mutation，可在修复工位/连接后重新做只读 qualification。

### A4. exact release 必须先于 target qualification — REPAIRED

原架构路线先 qualification 再 exact-release validation，而 source design 又要求先本地验证 release，两者不一致。

已统一为：

~~~text
OFFICIAL_ARMBIAN_INSTALLED
-> EXACT_RELEASE_VALIDATION
-> STANDARD_FRESH_ARMBIAN_QUALIFICATION
~~~

因为 release 决定 exact package versions、容量和后续 binding。

### A5. HOST_BASELINE 当前 source 仍会安装“现场 APT candidate” — SOURCE ADAPTATION REQUIRED / DESIGN CLOSED

current main 的 n3w_t1_fresh_host_baseline.py 当前行为是：

~~~text
apt-get update
-> apt-cache policy candidate
-> apt-get install package=<candidate>
~~~

这对已完成的历史 F3/F4 测试是有效事实，但不能满足 V2 exact release 的长期可重复量产要求。

V2 设计现已冻结：

~~~text
release binds docker.io exact version
release binds docker-compose-v2 exact version
APT candidate must equal release version
version drift stops before install
no silent latest upgrade
~~~

这是后续 source implementation 必须完成的已知改动，不再是设计歧义。

### A6. F3 固定 authorization string 不能作为 V2 production authority — REPAIRED

current main 的 F3 bootstrap 把历史固定 AUTHORIZATION_ID 同时写入 payload manifest 和 target authorization ledger。
该字符串随 artifact 公开存在，不能单独证明“本次 operator 已批准这台 target”。

V2 已明确拆开：

~~~text
immutable F3 payload identity
+
external V2 run context
+
current STARTED marker binding
~~~

动态 run context 必须位于 immutable payload root 外部，避免再次出现 KF-123 类 file-set/context 交叉污染。

固定历史 authorization string 可删除或降级为 action label，但不能单独授权 apply。

### A7. 一次人工批准不等于删除 F4 内部防重放 — REPAIRED

current main 的 F4 已经具有大量真实实机关闭过的安全属性：

- durable transaction；
- distinct one-shot internal authorization IDs；
- atomic claims；
- no-replay；
- rollback / rollback-unproven；
- persistence/certificate/reboot binding；
- post-reboot acceptance。

V2 首版不应该为了“简化”重写或删除这些安全守卫。

冻结模型：

~~~text
ONE HUMAN PRODUCTION APPROVAL
-> V2 orchestrator
-> deterministic internal action IDs from run_id + action
-> existing F4 one-shot guards
~~~

repair-* 命令继续不能进入 normal production path。

### A8. Post-reboot acceptance 应复用现有 F4 verifier — PASS AFTER DESIGN NARROWING

current main 的 n3w_t1_f4_reboot_verify.py 已经实际覆盖：

- boot ID changed；
- F4 transaction unchanged；
- installed control/material binding；
- provisioning verify；
- systemd persistence；
- exact runtime images/containers；
- Broker/Manager/Home Assistant runtime contract；
- TLS；
- Manager runtime stability；
- Home Assistant MQTT integration；
- Home Assistant HTTP readiness；
- Manager/Home Assistant MQTT sockets；
- negative authentication/provisioning probe；
- certificate runtime guard。

因此 V2 post-reboot acceptance 不重新复制这些 target-local checks。

V2 只增加：

1. V2 run marker/release/target binding；
2. Mac 外部 probe；
3. 90 s bounded stability observation；
4. final ACCEPTED marker。

### A9. failure forensic before reflash — PASS WITH ACCEPTED-DEVICE EXCEPTION

冻结的失败路径保持：

~~~text
FAIL
-> FREEZE_EVIDENCE
-> FORENSIC_SNAPSHOT_COMPLETE
-> SESSION_CLOSE
-> TARGET_MARKED_REFLASH_REQUIRED
-> REFLASH_ALLOWED
~~~

但它仅适用于 STARTED 且尚未 durable ACCEPTED 的 run。

如果 device acceptance 已 PASS、target marker 已 durable ACCEPTED，而之后只有 Mac cleanup/public-result/archive 失败：

~~~text
DEVICE_ACCEPTANCE=PASS
OVERALL_PROCESS=FAIL
REFLASH_REQUIRED=false
~~~

不得因为生产工位证据收尾故障而擦掉一台已经验收合格的 T1。

另外 SESSION_CLOSE 可由“正常关闭”或“确认本 run 的 local managed connection 已不存在”满足，目标掉线不能制造永久 reflash deadlock。

### A10. V2 minimal target marker — PASS

STARTED -> ACCEPTED 作为顶层 target state 足够，因为 V2 不提供现场 recovery/resume。

这不禁止 F3/F4 内部保留小型 one-shot action records；这些 record 只防重放和绑定 evidence，
不构成 V1 那种可恢复的顶层 phase state machine。

### A11. Reflash 后的新 run — PASS WITH MAC LEDGER RULE

重装 Armbian 后 machine-id / SSH host key / target binding 会改变，这是 fresh-per-device route 的正常结果。

Mac 生产台账必须 append-only 保存旧 run 的失败/REFLASH_REQUIRED 记录，新安装使用新的 target binding 与新的 run ID。
不得要求新 OS identity 匹配被擦除的旧 host identity，也不得覆盖旧 run。

物理资产关联如果以后需要，应使用独立 operator asset label/工厂台账，不把旧 SSH host key 当成不可变硬件 ID。

## 2. Source implementation boundaries frozen by review

R1/R2/R3 implementation 必须保持：

~~~text
NEW_V2_NORMAL_PATH=true
V1_NORMAL_PATH_REUSE=false
V1_REPAIR_COMMANDS_IN_NORMAL_PATH=false

FRESH_QUALIFICATION=SMALL_EXPLICIT_CHECK_SET
HOST_BASELINE=RELEASE_BOUND_EXACT_PACKAGES
F3_AUTHORITY=EXTERNAL_RUN_CONTEXT_PLUS_STARTED_MARKER
F3_DYNAMIC_CONTEXT_OUTSIDE_IMMUTABLE_PAYLOAD=true
F4_EXISTING_TRANSACTION_GUARDS=KEEP
F4_REPAIR_COMMANDS=NOT_CALLABLE_BY_V2
POST_REBOOT_TARGET_LOCAL=REUSE_F4_REBOOT_VERIFY
FAILURE_FORENSICS=READ_ONLY_BEFORE_REFLASH
ACCEPTED_DEVICE_CLEANUP_FAILURE_REFLASH=false
~~~

## 3. Review disposition

~~~text
DESIGN_BLOCKER_COUNT=0
SOURCE_DESIGN_REVIEW=CLOSED_PASS
SOURCE_IMPLEMENTATION_READY_AFTER_DESIGN_PR_IN_MAIN=true

PR622_STATE=OPEN_DRAFT
PR622_MERGED=false

NEXT_ONE_GATE=N3W_T1_F5_V2_PR622_MERGE_DECISION_20261019_01
AUTO_MERGE=false
AUTO_EXECUTE_SOURCE_IMPLEMENTATION=false
STOP=true
~~~

先把这份 V2 architecture/source-design authority 收敛进 main，再从新的 main 建 source implementation branch。
不再建立类似 V1 的长 stacked PR 链。
