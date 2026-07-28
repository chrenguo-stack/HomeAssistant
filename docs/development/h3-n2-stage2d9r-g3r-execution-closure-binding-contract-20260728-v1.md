# H3/N2 Stage 2D-9R G3R：执行闭包绑定合同 V1

## 1. 决策

已接受决策：

`D1-H3N2-STAGE2D9R-G3R-EXECUTION-CLOSURE-BINDING-20260728-01`

本后继层以 Draft PR #194 精确 HEAD
`b69371b13b6af139b4607a2150f25f440bb251c7` 为基础，不修改 PR #194、其
Artifact、既有 immutable/recovery payload 或既有证据。

执行请求与授权不再把整个仓库 `main` HEAD 作为阻断性绑定。仓库 HEAD 继续写入
证据，但其角色固定为：

```text
repository_head_role = AUDIT_ONLY
repository_head_enforced = false
```

新的阻断性绑定为：

```text
execution_closure_role = BLOCKING
execution_closure_policy_version = 1
```

## 2. 执行闭包

执行闭包必须逐文件覆盖实际物理执行所需的全部运行时字节：

1. 最终 Python wrapper；
2. shell launcher；
3. wrapper 直接或间接加载的全部 Python/脚本依赖；
4. immutable firmware payload TAR、固件镜像和分区数据；
5. locked recovery payload TAR、恢复描述和测试分区恢复计划；
6. 执行包内其他运行时数据文件。

每个成员记录文件名和 SHA-256，并计算确定性的
`execution_closure_sha256`。运行时必须重新读取所有成员并复算摘要。成员缺失、增加、
替换或摘要不一致均必须在授权 claim 前失败。

执行闭包不能替代现有 `execution_package_sha256`。两者同时阻断：

- `execution_closure_sha256` 证明关键运行时闭包未变；
- `execution_package_sha256` 证明完整执行包字节集合未变；
- wrapper、launcher、固件、恢复 payload 和工具链摘要继续单独校验。

## 3. 仓库漂移处理

仓库 HEAD 变化时：

1. 记录实际 `repository_head_sha`；
2. 记录 `non_execution_drift_files`；
3. 不把该 SHA 与某个冻结 `main` SHA 做相等比较；
4. 继续严格校验执行闭包、完整执行包、payload、工具链、请求、板卡身份和一次性授权。

因此，README 等未进入执行包的文件变化不会单独使请求失效。任何进入执行闭包或执行包
的文件变化仍会改变摘要，必须重新打包、审核并签发新的精确授权。

本合同不允许通过把代码变化错误标记为“文档漂移”来绕过校验。运行时以实际执行包内
文件和摘要为准，不相信路径说明或人工分类。

## 4. 既有证据处置

PR #194 的以下事实保持不变：

- Artifact `8688476229`，SHA-256
  `89e25e287c33de0d88c714c748329c5d4cdbe12f83343fdd18eff8debf351a04`；
- immutable TAR SHA-256
  `3a3e96c267fd53723e7cbe6cbce959a90d2bf3f08adedcf97255395f91adc4ea`；
- recovery TAR SHA-256
  `08cff687947c2f9b9cbd2df09f16b14b95beeacf2de5683055d6572fafd6cf8f`；
- H3 host-only 授权从未创建、claim 或消费；
- `...PHYSICAL-20260728-03` 仍为 `authorized=false` 草稿。

旧草稿请求永久标记为：

`SUPERSEDED_BY_EXECUTION_CLOSURE_POLICY_BEFORE_AUTHORIZATION`

不得复用、续期、重新解释或直接签发授权。

## 5. 新后继身份

未来 host-only 授权：

`H4-H3N2-STAGE2D9R-G3R-EXECUTION-CLOSURE-BINDING-20260728-01`

未来物理请求：

`D2-H3N2-STAGE2D9R-G3R-PAYLOAD-HANDOFF-REPAIRED-PHYSICAL-20260728-04`

H4 只能验证公开包、执行闭包和审计字段，并输出仍为 `authorized=false` 的物理请求。
物理 D2 必须另行获得精确、一次性、限时授权。

## 6. 保留的安全边界

以下边界不因解除 `main` 阻断绑定而改变：

- 授权必须一次性、限时、禁止重放和自动重试；
- exact execution package、closure、wrapper、launcher、payload 和工具链摘要必须匹配；
- 板卡身份、串口身份、基线状态和请求 binding 必须匹配；
- payload 交接继续使用原始 TAR 与两个独立空提取目录；
- locked recovery 仅允许测试分区 `read → erase_region → read`；
- 禁止 recovery `write_flash` 和整片恢复擦除；
- 当前 Draft PR、CI 和 Artifact 不得连接板卡、枚举 USB/串口、调用 esptool、读写
  Flash/NVS、启动 Broker、执行 PREPARE/VERIFY/ACTIVATE/CLEANUP；
- 不授权 Ready、merge、release、tag 或 deployment。
