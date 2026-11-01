# N3-W T1 显式设备 Provisioning 命令与 Boot 解耦设计冻结（2026-10-13）

TASK=
`N3W_T1_EXPLICIT_DEVICE_PROVISIONING_COMMAND_AND_BOOT_DECOUPLING_DESIGN_FREEZE`

## 0. Gate 状态

~~~text
DESIGN_FREEZE=PASS
PRODUCT_SOURCE_MUTATION=false
T1_ACCESS=false
T1_MUTATION=false
R3_CLEANUP=false
LIVE_RUNTIME_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
MERGE=false
AUTHORIZATION_08_GRANTED=false
~~~

本 Gate 只冻结量产生命周期与命令合同，不实现真实 CLI、systemd、machine-id、SSH host key 或 T1 live 操作。

正式长期架构 authority 同步更新：
`docs/adr/0009-t1-golden-master-firstboot-production-lifecycle.md`

## 1. 核心问题

此前架构仍把“第一次 boot”与“开始产品实例化”绑定得过紧。

本轮冻结的新原则：

~~~text
BOOT != PROVISION

BOOT_STARTS_NEW_PROVISIONING=false
EXPLICIT_PROVISION_COMMAND_REQUIRED=true
PROVISION_COMMAND_REBOOT_REQUIRED=false
~~~

普通开机只进入基础主机/诊断环境。
开始一个全新产品实例化只能来自显式命令。

## 2. 新量产主路径

~~~text
GOLDEN_MASTER_BUILD
→ MASTER_VALIDATED
→ FINAL_SEAL
→ SHUTDOWN
→ OFFLINE_DISK_IMAGE_CAPTURE
→ GOLDEN_IMAGE_VERIFIED
→ CLONE_WRITE
→ CLONE_READBACK_VERIFIED
→ CLONE_BOOTED_UNPROVISIONED
→ CLONE_RUNTIME_AUDIT
→ EXPLICIT_PROVISION_COMMAND
→ INITIALIZING
→ DEVICE_READY
→ FACTORY_AUDIT
→ FACTORY_ACCEPTED
→ PRODUCT_ACTIVATION
→ USER_ONBOARDING / ACTIVE
~~~

关键变化：

- 黄金镜像默认永远是 UNPROVISIONED；
- clone 第一次启动也不会自动生成产品实例；
- clone 可以在 UNPROVISIONED 状态下启动并检查；
- 操作者无需关机重启即可开始 provisioning；
- provisioning 完成不自动等价于产品服务正式激活。

## 3. 三类独立 authority

### 3.1 Release authority

~~~text
BUILD
→ VALIDATED
→ FINAL_SEAL
→ CAPTURED
→ GOLDEN_IMAGE_VERIFIED
~~~

回答：“这是不是被批准的公共黄金镜像？”

### 3.2 Clone write authority

~~~text
WRITTEN
→ READBACK_VERIFIED
→ BOOTED_UNPROVISIONED
~~~

回答：“这台目标 T1 最初是不是从 exact 黄金镜像正确写入的？”

最强 write verification 仍然是首次启动前的离线 read-back：

~~~text
SHA256(read-back exact image-length bytes)
==
GOLDEN_IMAGE_SHA256
~~~

如果在 read-back PASS 后向目标盘写入 clone evidence marker，这个 marker 必须被记录为
bit-exact verification 之后的第一个受控差异。

### 3.3 Product instance authority

~~~text
UNPROVISIONED
→ INITIALIZING
→ DEVICE_READY
→ FACTORY_ACCEPTED
→ ACTIVE
~~~

回答：“这块公共克隆是否已经被转换成一台具体的产品实例？”

这三个 authority 不允许相互替代。

## 4. 显式 Provisioning 命令

概念上的正式入口冻结为：

~~~text
sudo n3w-t1-provision start --confirm "START DEVICE PROVISIONING: YES"
~~~

正式源码实现可以调整 executable packaging，但不能改变以下语义。

### 4.1 status

~~~text
n3w-t1-provision status
~~~

只读输出至少区分：

~~~text
UNPROVISIONED
INITIALIZING
DEVICE_READY
CONFLICT / FAIL_CLOSED
~~~

不得因为查询状态而创建 identity、transaction 或业务状态。

### 4.2 start

`start` 是正常产品路径中唯一允许创建全新 provisioning transaction 的入口。

执行时：

1. 先完成全部 fail-closed preflight；
2. 原子 claim 新 transaction；
3. 状态进入 INITIALIZING；
4. 在当前 boot 中立即执行，不要求 reboot；
5. 成功后写 completion marker，进入 DEVICE_READY；
6. 不自动进入产品正式 activation。

### 4.3 无普通 stop/unprovision

一旦 INITIALIZING 已开始：

- 不允许用普通命令把状态退回 UNPROVISIONED；
- 不允许删除 transaction/completion marker 重新获得初始化资格；
- 失败只允许 resume/reconcile 或重新刷合格黄金镜像；
- future factory reset 是另一套独立合同。

## 5. start 的硬前置条件

新 provisioning command 至少必须证明：

~~~text
SEALED_RELEASE_MATCH=true
PUBLIC_SOURCE_BINDING=PASS
IMAGE_BINDING=PASS
CLONE_WRITE_EVIDENCE=PASS
NO_EXISTING_PRODUCT_IDENTITY=true
NO_UNKNOWN_TRANSACTION=true
NO_PRODUCT_SERVICE_ACTIVE=true
HOST_IDENTITY_PRECONDITION=PASS_OR_CONTROLLED_ESTABLISHMENT
~~~

其中：

- CLONE_WRITE_EVIDENCE 必须绑定当前 release；
- 不要求把 raw disk SHA 在运行中的 T1 上重新计算；
- read-back hash 可以由生产工装/外部 evidence authority 保存；
- 若设备内保存 marker，必须保存 release/evidence 摘要，不保存秘密；
- 未能唯一证明当前 clone 来源时 fail-closed。

## 6. Boot 行为重新冻结

### 6.1 UNPROVISIONED

~~~text
boot
→ do not create provisioning transaction
→ do not generate product identity/secrets
→ do not start production services
→ allow bounded read-only clone/runtime audit
~~~

机器可以保持开机等待操作者执行显式命令。

### 6.2 INITIALIZING

如果一个 provisioning transaction 已经由显式命令合法创建：

~~~text
boot
→ detect valid INITIALIZING transaction
→ verify release + host binding
→ auto resume
~~~

此处允许自动 resume，因为“开始初始化”的人工决策已经发生。

### 6.3 DEVICE_READY

~~~text
boot
→ verify-only
→ validate current live host identity
→ do not regenerate identity
→ do not reopen provisioning start
~~~

completed fast-path 必须核对：

~~~text
current live host_instance_id
==
transaction.host_instance_id
==
completion.host_instance_id
~~~

这吸收并保留此前 R1 A4 remaining blocker。

## 7. Provisioning transaction

显式命令成功 claim 后，最小顺序：

~~~text
CLAIM
→ OS_IDENTITY
→ PRODUCT_IDENTITY
→ CRYPTO_MATERIAL
→ SERVICE_CREDENTIALS
→ DYNSEC
→ EMPTY_PRODUCT_STATE
→ INSTANCE_CONFIG
→ COMMIT
→ VERIFY
→ DEVICE_READY marker last
~~~

必须继续满足：

- single initializer；
- exact release/schema/host binding；
- transaction-owned staging；
- owner/mode/symlink fail-closed；
- atomic + fsync durable records；
- 已完成组件重启后复用；
- unknown/mixed/tampered formal state fail-closed；
- completion marker 最后写。

R1 已实现的 durable transaction/security work继续复用，不推翻。

## 8. Boot-time resume helper

未来 systemd helper 的职责被冻结为：

~~~text
START_NEW_PROVISIONING=false
RESUME_EXISTING_INITIALIZING=true
VERIFY_DEVICE_READY=true
~~~

因此它不再承担“automatic firstboot starter”语义。

未来实现可以采用：

~~~text
n3w-t1-provision-resume.service
~~~

或等价名称。

具体 unit name/source path 留给 source Gate 冻结。

## 9. 产品服务 activation 与 Provisioning 分离

`n3w-t1-provision start` 到 DEVICE_READY 为止。

它不能自动把 Broker、Manager、Home Assistant 进入正常产品运行。

长期顺序：

~~~text
DEVICE_READY
→ factory audit
→ FACTORY_ACCEPTED
→ explicit/authorized activation
→ ingress guard verified
→ Broker
→ authenticated readiness
→ Manager + Home Assistant
~~~

因此：

~~~text
UNPROVISIONED: production services OFF
INITIALIZING: production services OFF
DEVICE_READY: production services not automatically ACTIVE
FACTORY_ACCEPTED: activation eligible
~~~

## 10. 母盘 Final Seal 与离线采集

显式 provisioning 命令解决的是产品实例化误触发，不能自动解决操作系统自身的 first-boot 行为。

尤其需要独立验证：

- /etc/machine-id；
- D-Bus machine-id；
- SSH host-key regeneration；
- NetworkManager persistent identity；
- DHCP/client identity；
- random seed；
- journald machine state。

因此当前冻结：

~~~text
FINAL_SEAL
→ final seal audit PASS
→ shutdown
→ offline capture
~~~

在目标 Armbian exact behavior 尚未证明前：

~~~text
REBOOT_AFTER_FINAL_SEAL_BEFORE_CAPTURE=false
~~~

如果母盘在 FINAL_SEAL 后又被启动：

- 不会因为产品代码自动 provisioning；
- 但不能假设 OS identity 仍保持 sealed；
- 必须重新做 OS/seal audit，必要时重新 Seal 后才能采集。

## 11. 克隆后无需 power-cycle 的生产流程

正式工厂流程可为：

~~~text
write golden image
→ offline read-back PASS
→ power on target
→ clone/runtime audit
→ operator runs provision start
→ provisioning executes immediately
→ DEVICE_READY
→ factory audit
→ activate
~~~

从 CLONE_BOOTED_UNPROVISIONED 到 DEVICE_READY 中间不需要关机、断电或人为再次重启。

仅在异常断电时，resume helper 才在 reboot 后自动继续。

## 12. 命名与兼容策略

当前 R1 已存在：

~~~text
device_firstboot.py
run_device_firstboot()
~~~

本轮不立即改源码名称，避免把架构调整和大范围重命名混在一起。

正式语义从本 Gate 起统一解释为：

~~~text
device_firstboot.py = transitional implementation name
product architecture term = explicit device provisioning
~~~

后续 source repair 可以保留内部兼容 wrapper，并新增 provisioning CLI/orchestration。

不得因为名称兼容而重新引入“普通 boot 自动开始新初始化”的语义。

## 13. 对 R1 当前状态的处理

R1 已完成的价值继续保留：

~~~text
SB1 public/instance staging split = KEEP
SB2 commit/cleanup ownership split = KEEP
SB3 postcheck split = KEEP
durable transaction hardening = KEEP
A1 legacy R8 commit compatibility = KEEP CLOSED
A2 authority owner/mode = KEEP CLOSED
A3 atomic write = KEEP CLOSED
~~~

此前 remaining A4 completed live host binding 不取消，吸收到新 provisioning contract：

~~~text
DEVICE_READY verify-only boot path
must verify current live host identity
~~~

R1 不再以“自动 firstboot lifecycle 完整实现”为目标，因为该上游触发模型已经被本设计正式替换。

## 14. Source repair 所需最小变化方向

后续 source Gate 才执行，当前不改产品源码。

需要的最小 source package：

~~~text
1. explicit provisioning CLI/status/start contract
2. transaction start authority separated from resume authority
3. completed DEVICE_READY current-host verification
4. read-only UNPROVISIONED status/audit path
5. service activation guard recognizes UNPROVISIONED/INITIALIZING/DEVICE_READY
6. clone/release evidence preflight interface
7. legacy run_device_firstboot compatibility wrapper as needed
~~~

不在同一 source Gate 做：

- real master Seal live apply；
- raw disk capture；
- target Armbian machine-id mutation；
- SSH host-key live manipulation；
- factory A/B physical clone；
- production service live activation；
- streaming image import。

## 15. CI / fault injection requirements

未来 source repair 至少加入：

~~~text
plain boot with no transaction
→ no identity generated
→ no transaction generated

explicit start
→ creates transaction exactly once
→ immediately executes without reboot

duplicate start while INITIALIZING
→ no second transaction / fail or resume safely

power loss after explicit start
→ reboot auto resumes

DEVICE_READY reboot
→ verify current host
→ no regeneration

completed disk copied to host B
→ current host binding mismatch
→ fail closed

UNPROVISIONED / INITIALIZING
→ production activation forbidden

provision completion
→ does not automatically activate production services
~~~

## 16. Design blocker disposition

~~~text
AUTO_FIRSTBOOT_TRIGGER_MODEL=RETIRED_DESIGN
BOOT_PROVISION_COUPLING=CLOSED_DESIGN
EXPLICIT_PROVISION_COMMAND=CLOSED_DESIGN
NO_REBOOT_PROVISION_START=CLOSED_DESIGN
RESUME_ONLY_ON_BOOT=CLOSED_DESIGN
PROVISION_ACTIVATION_SEPARATION=CLOSED_DESIGN

TARGET_ARMBIAN_OS_IDENTITY_BEHAVIOR=OPEN_EVIDENCE
SOURCE_IMPLEMENTATION=PENDING
LIVE_ACCEPTANCE=PENDING
~~~

## 17. STOP

~~~text
DESIGN_FREEZE=PASS
PRODUCT_SOURCE_MUTATION=false
T1_ACCESS=false
R3_CLEANUP=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
MERGE=false
AUTHORIZATION_08_GRANTED=false
~~~

推荐下一门：

~~~text
NEXT_ONE_GATE=
N3W_T1_EXPLICIT_DEVICE_PROVISIONING_COMMAND_AND_BOOT_DECOUPLING_SOURCE_REPAIR_DESIGN

SOURCE_MUTATION=false
T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
MERGE=false
~~~

该 Gate 只把当前 R1 exact source 映射为 CLI/start authority、resume authority、
DEVICE_READY verify-only、activation guard 所需的精确文件/函数/测试改动，再 STOP；不直接改源码。
