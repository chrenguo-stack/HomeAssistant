# N3W T1 F5 V2 长耗时生产进度与 reboot 前 operator arming 源码修复 — 2026-10-21

## 1. 现场失败

本修复来自真实 T1 的 F5 V2 repaired-release production run：

~~~text
PRODUCTION_RUN_ID=c715fdee2bbd55c4ed7e3d8d0dd2e1cd2d147651e5ba8390ab4e696dc9a43519
STATUS=FAIL
MARKER_STATE=STARTED
TERMINAL_STAGE=SSH_EPOCH_2
ERROR_CLASS=POST_REBOOT_ACCEPTANCE_FAIL_REFLASH_REQUIRED
T1_PRODUCTION_READY=false
REFLASH_REQUIRED=true
~~~

操作者已经完成唯一一次 production approval。随后 HOST_BASELINE / F3 / F4 长时间运行且终端缺少持续阶段反馈，操作者离开电脑。受控 reboot 完成后，executor 进入第二个 SSH connection epoch 并等待 root 密码，但当时无人输入。当前 SSH transport 的交互式 master 建立 timeout 为 180 秒且 NumberOfPasswordPrompts=1，因此无人输入可直接使 SSH_EPOCH_2 失败。

失败后独立只读 SSHTransport 诊断 PASS：

~~~text
HOST_KEY_BINDING=PASS
PASSWORD_AUTH_PATH=PASS
PASSWORD_PERSISTED=false
NEW_LOGIN_KEY=false
TARGET_MUTATION=false
~~~

因此本轮不支持 persistent target SSH defect、host-key drift 或 production 修改 root 密码。失败 run 保持 terminal，不能 replay。

## 2. 根因

~~~text
ROOT_CAUSE=POST_REBOOT_OPERATOR_PASSWORD_PROMPT_UNATTENDED_UNTIL_AUTH_TIMEOUT
ROOT_CAUSE_STATUS=CLOSED_HIGH_CONFIDENCE
~~~

流程缺口是：长耗时生产路径允许终端长时间安静，但 planned reboot 后又立即要求第二次人工 SSH 密码。当前流程没有在 reboot 前建立 operator-presence arming 边界，因此要求操作者事实上持续守在屏幕前，否则一个已经越过 STARTED 的 run 会因为错过密码窗口进入 reflash-required 终局。

## 3. 修复目标

本次修复只处理两个问题：

1. 让主要长耗时生产阶段有机器可读的进度输出；
2. 让 reboot-control package 的准备/安装/验证可继续无人值守，但在一次性 reboot claim 被消费和真正 reboot actuation 之前，增加无超时的本地 operator arming 等待点。

不改变：

- one production approval；
- exact release / source binding；
- STARTED / ACCEPTED marker 语义；
- F3、Provision、F4 业务逻辑；
- reboot authority；
- post-reboot acceptance；
- one password per SSH epoch；
- host-key checking；
- failed run no-replay / reflash-required 规则；
- Board/firmware 路径。

## 4. 新的操作语义

长耗时阶段会打印：

~~~text
PRODUCTION_PROGRESS={"stage":"HOST_BASELINE","status":"STARTED",...}
PRODUCTION_PROGRESS={"stage":"HOST_BASELINE","status":"PASS",...}
PRODUCTION_PROGRESS={"stage":"F3_DEPLOY","status":"STARTED",...}
PRODUCTION_PROGRESS={"stage":"F3_DEPLOY","status":"PASS",...}
...
~~~

到 planned reboot 前必须先停在：

~~~text
PRODUCTION_PROGRESS={"stage":"REBOOT_CONTROL","status":"WAITING_FOR_OPERATOR",...}
REBOOT_ARMING_SUMMARY=...
REBOOT_ARMING>
~~~

arming 输入采用 run-bound exact literal：

~~~text
ARM N3W T1 F5 V2 CONTROLLED REBOOT <run_id>
~~~

该提示：

- 不是第二次 production approval；
- 没有倒计时；
- 输入不匹配时继续等待，不把误输入直接转成生产失败；
- reboot-control material 可以先完成 staging/install/verify；exact arming 必须位于这些准备工作之后、一次性 reboot claim 和 reboot actuation 之前；
- 明确告诉操作者 planned reboot 后还会要求一次 root SSH 密码。

arming 完成后：

~~~text
PRODUCTION_PROGRESS={"stage":"REBOOT_CONTROL","status":"ARMED",...}
...
PRODUCTION_PROGRESS={"stage":"SSH_EPOCH_2","status":"PASSWORD_REQUIRED",...}
~~~

因此管理员可以在 HOST_BASELINE/F3/F4 长耗时阶段离开屏幕，返回后再在 reboot arming 点恢复操作，不需要猜测第二次密码提示何时出现。

## 5. 源码范围

~~~text
tools/n3w_t1_production_v2_executor.py
tests/tools/test_n3w_t1_production_v2_executor.py
docs/development/N3W_T1_PRODUCTION_SSH_CONNECTION_REUSE_V1_DESIGN_20261014.md
docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
docs/development/N3W_CURRENT_STATE_INDEX.md
docs/development/N3W_T1_F5_V2_OPERATOR_PRESENCE_AND_PROGRESS_SOURCE_REPAIR_20261021.md
~~~

不修改：

~~~text
tools/n3w_t1_production_v2.py
tools/n3w_t1_ssh_transport.py
F3/F4 product primitives
firmware
board logic
~~~

## 6. 回归要求

至少证明：

- reboot arming 没有 timeout；
- exact arming 前不 staging reboot-control package；
- exact arming 前不执行 systemctl reboot；
- 错误 arming 文本只继续等待；
- one production approval 仍然只有一次；
- HOST_BASELINE/F3/Provision/F4/reboot/post-reboot password/acceptance 关键阶段有可见进度；
- post-reboot SSH 仍保持独立第二 connection epoch；
- password 不持久化；
- host-key checking 不降低；
- failed run 自动 retry 仍禁止。

## 7. 当前边界

~~~text
SOURCE_BRANCH=fix/n3w-t1-f5-v2-reboot-arming-progress-20261021
BASE_MAIN=4292481f07b6ed89fe3d275be9fa4a51d7b26e6a

T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
REFLASH=false
REAL_PRODUCTION_RETRY=false
MERGE=false

FAILED_RUN=c715fdee2bbd55c4ed7e3d8d0dd2e1cd2d147651e5ba8390ab4e696dc9a43519
FAILED_RUN_REPLAY=false
FAILED_TARGET_REFLASH_REQUIRED=true
T1_PRODUCTION_READY=false
KF_122=OPEN
KF_124=SOURCE_REPAIR_IMPLEMENTED_CI_PENDING
~~~

修复源码、测试和 CI 关闭前，不重刷 T1，也不开始新的 real-T1 production run。
