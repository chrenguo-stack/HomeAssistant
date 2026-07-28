# H3/N2 Stage 2D-9R G3R：main 漂移后继重绑定合同 V1

## 1. 已接受事实

- 决策：`D1-H3N2-STAGE2D9R-G3R-MAIN-DRIFT-SUCCESSOR-REBIND-20260728-01`。
- 基层：Draft PR #193，精确 HEAD `bdfcda55ff248838f0d703abf6d2414f3f73eff7`。
- 原冻结 main：`0229002cc5037f83bc77426f439bdb9e6d63318c`。
- 新接受 main：`64c6b093c3ba6a8476c9392c8d106394b2542fb5`。
- 两者之间仅有一个提交，且只修改 `README.md`。

## 2. 已消耗 H2

`H2-H3N2-STAGE2D9R-G3R-PAYLOAD-HANDOFF-HOST-FINAL-PREFLIGHT-20260728-01`
已经 `CONSUMED_PASS`，永久禁止重放和自动重试。其结果 canonical SHA-256 为
`4dd2fe9574244b85f65461b02412ec99fb254da6402f2b3b48f55b23198e02e0`。
本层只验证并继承该公开证据，不重新访问 `tlsvalid03` 私密托管。

## 3. 失效请求

物理请求 `...PHYSICAL-20260728-02` 在授权创建前因 main 漂移永久标记为
`STALE_MAIN_DRIFT_BEFORE_AUTHORIZATION`。它未创建、claim 或消耗授权，也未发生
物理执行；但该请求本身不得复用、续期或重新解释。

## 4. 新后继链

本层冻结：

1. 只读验证 PR #193 Artifact、已消耗 H2 结果和失效请求；
2. 保留 immutable/recovery TAR 原始字节和 payload 交接修复；
3. 新增仅重绑定 main、请求身份和最终 wrapper/launcher 的执行包；
4. 后续 host-only 授权：
   `H3-H3N2-STAGE2D9R-G3R-MAIN-DRIFT-SUCCESSOR-REBIND-20260728-01`；
5. 后续新物理请求：
   `D2-H3N2-STAGE2D9R-G3R-PAYLOAD-HANDOFF-REPAIRED-PHYSICAL-20260728-03`。

H3 host-only 执行成功后只能输出 `authorized=false` 的新物理请求。物理 D2 仍需
独立、精确、一次性的后续授权。

## 5. 不可突破边界

当前 Draft PR、CI 和 Artifact 均不得连接或枚举板卡/USB/串口，不得调用
esptool，不得读写 Flash/NVS，不得启动网络或 Broker，不得执行 PREPARE、VERIFY、
ACTIVATE、CLEANUP，也不得 Ready、merge、release、tag 或 deployment。

锁定恢复仍仅允许测试分区 `read → erase_region → read`；禁止恢复 `write_flash`
和整片擦除。任何 PR/SHA/main/CI/Artifact 漂移均使后续授权前检查失败并停止。
