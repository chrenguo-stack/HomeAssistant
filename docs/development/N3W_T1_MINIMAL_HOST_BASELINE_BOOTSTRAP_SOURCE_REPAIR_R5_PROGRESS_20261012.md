# N3-W T1 minimal-host fresh bootstrap R5 progress（2026-10-12）

R5 不操作真实 T1。目标是在 GitHub CI 里模拟一台“只有基础系统”的干净 T1，把首次安装完整跑一遍。

本轮新增 host-only 完整安装测试，使用真实的：

- System Identity 创建代码；
- Manager / N3-W 空状态创建代码；
- Broker TLS 和三套服务凭据创建代码；
- DynSec 三服务身份规划与审计代码；
- R3 fresh installer 总编排。

CI 模型从 0 个产品对象开始，并验证：

1. 干净环境可以完整安装；
2. 有旧产品残留时，在任何写入前停止；
3. 上次留下 partial candidate 时禁止重跑覆盖；
4. 密码和 DynSec 管理员 secret 不出现在 stdout 或最终 report；
5. node credential 始终为 0；
6. Broker / Manager / Home Assistant 最终仍是 stopped；
7. 故障注入后，只删除本次 transaction 新建内容，不碰无关宿主文件。

R5 是 host-only 模型验证。真正使用 exact ARM64 Manager / Home Assistant / Broker 镜像的完整验证仍留在 R6。

```text
R4_STATUS=CLOSED_PASS
R5_SOURCE_COMMITTED=true
R5_CI=PENDING
T1_ACCESS=false
LIVE_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false

NEXT_ONE_GATE=
N3W_T1_MINIMAL_HOST_BASELINE_BOOTSTRAP_SOURCE_REPAIR_R6_20261012_01

R6_SCOPE=EXACT_ARM64_THREE_IMAGE_FULL_FRESH_CI_AND_ARTIFACT
```
