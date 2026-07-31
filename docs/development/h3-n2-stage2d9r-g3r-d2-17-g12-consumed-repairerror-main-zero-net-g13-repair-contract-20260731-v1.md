# G12 consumed RepairError、main 零净漂移与 G13 host-only 修复合同

## 冻结输入

- G12 物理决策 PR：`#247`，exact HEAD `68ac3669ec589502cb77f4f361fb705993706415`。
- G12 terminal：`06ff50937f1e1c894daa07f305ea62d48dc45939e6c79fabaa98b15393537e24`。
- G12 authorization marker：`26eee6a2da260b3430d0d1aed9b9c7ebbd8d05e1ff2fe162c92fa7d52e1cb5fa`。
- main 原始 SHA：`64c6b093c3ba6a8476c9392c8d106394b2542fb5`。
- main 当前 SHA：`6525e8a81c140853e2b0de0eba78ad1227ca7305`。

## G12 终态

G12 已进入 `CONSUMED_FAILED`，禁止重放、重试、复用授权或修改既有 runtime。虽然外层 terminal 报告 `authorization_claimed=false`，但 `CONSUMED_FAILED` marker 在状态机语义上必然表示 claim 已先发生，因此公开处置将其校正为 claimed/consumed=`true/true`。

精确缺陷为：G12 wrapper 只接受不存在的目录，而冻结 inherited executor 使用 `TemporaryDirectory` 后传入已经存在、为空、权限为 `0700` 的工作目录。叶子错误为 `G12_BASELINE_WORK_DIRECTORY_ALREADY_EXISTS`；外层仅保留为 `RepairError`。

## main 零净历史漂移

main 相对 `64c6b093...` 多两个审计 commit，但文件比较为零项变化。保留历史，不强制改写 ref；当前 main `6525e8a...` 作为新的公开基线。main 零净漂移绑定：

`12a7f715cef504ba8d92ee17e1e40e4b51a20a4b6a4b1bb4f12d3e20ab0899ce`

## G13 修复

G13 仅增加 host-only 兼容层：

- 接受不存在的专用目录；
- 接受已存在、为空、真实目录且权限为 `0700` 的 inherited temporary directory；
- 拒绝 symlink、非目录、非空目录和权限漂移；
- 检测并绕过 exact G12 wrapper，调用冻结 original baseline；
- repair 失败转换为 inherited `ExecutionError` 并保留精确字符串子码；
- 从 `CLAIMED`、`CONSUMED_PASS`、`CONSUMED_FAILED` marker 正确推导 claim/consume。

G12 处置绑定：

`bbc16258410a53363349c7b71323f0b7fcb33548f561dfa3b0dc71be5fcb7bc3`

G13 pending 绑定：

`6b55377ca34d2c71e9653ef1708ce4ad8a2c06ef5b936b7c2ce1e715561ae596`

## 安全边界

本 PR 不创建私密包、runtime 或 authorization，不连接板卡，不枚举 USB/串口，不调用 esptool，不读写 Flash/NVS，不启动 Broker，不执行 PREPARE、VERIFY、recovery、ACTIVATE 或 CLEANUP。Ready、merge、release、tag 和 deployment 均禁止。

下一显式门：

`D1-H3N2-STAGE2D9R-G3R-D2-17-G13-PRIVATE-PACKAGE-AND-TARGET-MAC-STATIC-CHECK-AUTHORIZATION-CREATION-20260731-01`
