# H3/N2 Stage 2D-9R G3R 私密执行材料修正计划

## 1. 触发原因

`D2-H3N2-STAGE2D9R-G3R-20260725-01` 在声明和消费前的源码与私密材料可执行性复核中 fail closed。

冻结 PKI 生成器生成随机 64 位十六进制 MQTT 密码，用它生成 Mosquitto 密码数据库和候选摘要，但生成结束前只保留密码数据库哈希与公开密码摘要，未在私密托管中保留原始密码预映像。冻结命令材料仅保留解锁令牌，也未冻结 VERIFY 所需的持久化密钥。

因此，虽然证书、私钥、密码数据库、CA 摘要、候选摘要和 U1-04 私密内容绑定全部有效，但无法从已保留材料重建与冻结候选摘要完全一致的 `GH2D9R_PREPARE_V1`。尝试替换密码、重设密码数据库、使用替代候选或求取哈希预映像均被禁止。

D2-01 未创建授权记录、未声明、未创建 consumed marker、未连接实板，按 `invalidated_before_claim` 退役。

## 2. 修正目标

建立新的 successor 私密执行材料链，同时保留 PR #176、旧 Artifact、U1-04 和 D2-01 的历史不变性：

1. 在私密 PKI successor 包中保留模式 `0600` 的随机 MQTT 密码预映像文件；
2. 在私密命令 successor 包中保留模式 `0600` 的随机持久化密钥文件；
3. 私密描述符只记录相对路径、模式和 SHA-256，不内嵌秘密值；
4. U1 深度绑定必须验证：
   - 密码预映像 SHA-256 等于公开配置中的密码摘要；
   - 密码预映像与 Mosquitto `$7$` 密码数据库条目匹配；
   - 密码预映像、CA PEM 和公开字段重算出的候选摘要完全一致；
   - 解锁令牌和持久化密钥均为非零 32 字节值；
   - PREPARE 与 VERIFY 可离线确定性渲染并通过协议解析；
5. 禁止在日志、Git、公开 Artifact 或审核包中输出原始密码、解锁令牌、持久化密钥、私钥、密码数据库内容或私密路径；
6. successor 材料必须使用新的 custody root、请求 ID、run suffix、package digest 和 consumed marker，禁止覆盖或复用旧材料；
7. successor U1 完成后重新冻结公开候选摘要、最终 build binding、不可变固件 Artifact、恢复绑定和 D2 审核包；
8. 新 D2 仍必须是两小时、one-shot、无重放、无自动重试的独立精确授权。

## 3. 开发顺序

```text
记录 D2-01 preclaim 退役
→ successor 私密材料生成器与离线合同
→ successor 私密内容深度绑定器与故障矩阵
→ 全部 source/host CI 通过
→ 新 U1 审核包和精确授权
→ 生成 successor 私密材料
→ 公共导出与最终 source binding
→ 两次独立可复现编译并冻结新 immutable Artifact
→ host-only Artifact 与私密 custody 绑定复核
→ 新 D2 审核包和精确授权
→ 唯一实板执行
```

## 4. 当前禁止事项

在 successor U1 和新 D2 分别通过前，继续禁止：

- 读取或输出旧私密秘密值；
- 连接测试板或打开串口；
- 擦除、Flash、回读或物理 NVS 写入；
- 启动 Broker、建立网络连接、执行 PREPARE 或 VERIFY；
- ACTIVATE、CLEANUP、生产环境、M401A、T1、Home Assistant、Mosquitto 服务或 greenhouse-manager 操作；
- eFuse、Secure Boot、Flash Encryption；
- Ready、merge、release、tag 或 deployment；
- 重放 V69、Stage 2D-8、U1-03、U1-04、D2-01 或任何旧执行包。

## 5. 完成标准

只有同时满足以下条件，才可生成 successor U1 审核包：

- 原始 MQTT 密码预映像和持久化密钥均进入私密 package digest；
- 离线密码数据库验证、候选重算、命令渲染/解析和脱敏测试全部通过；
- 失败注入覆盖缺失、替换、模式错误、摘要漂移、密码数据库不匹配、候选不匹配、命令不一致和秘密泄露；
- 所有写操作默认关闭；
- PR 保持 Draft，且没有实板、网络或生产操作。
