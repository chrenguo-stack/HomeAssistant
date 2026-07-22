# GH H3/N2 Stage 2D-9 G3 PREPARE_CANDIDATE 协议

**版本：** 2  
**日期：** 2026-07-22  
**基线：** `main=2a5272546f25b1b29cf1d6682cf1fc14f1c1be83`

## 1. 唯一目标

Stage 2D-9 只验证一次隔离、generation-bound 的 `PREPARE_CANDIDATE`：

```text
EMPTY(active=0,candidate=0)
  -> write candidate profile generation=1
  -> durable PREPARED commit
  -> automatic reboot
  -> read-only recovery and private VERIFY
  -> verify active remains generation=0
  -> stop
```

本阶段不验证激活、清理或 Broker 会话。

## 2. 允许的门

```text
LOCKED
FLASH_ONLY
READ_ONLY
PREPARE_CANDIDATE
```

`ACTIVATE_PROFILE` 与 `CLEANUP_TEST_STATE` 不属于本阶段有效门，任何 manifest、命令或固件入口出现这两项授权都必须 fail closed。

## 3. PREPARE 精确授权绑定

未来实板授权必须至少绑定：

- 不可变源码 SHA；
- 不可变 Artifact SHA-256；
- 专用测试板私有绑定；
- 独立 writable test NVS 分区与唯一 namespace；
- active generation `0`；
- candidate generation `1`；
- candidate profile digest；
- 编译进执行固件的 one-time unlock preimage SHA-256；
- 完整执行脚本、命令组和停止条件 SHA-256；
- 一次性授权 ID、有效期、`replay_permitted=false`。

unlock preimage、测试持久化密钥和授权 JSON 只进入私有一次性执行包，均不得提交 Git。公共源码与公共 compile-only 目标只包含全零 unlock digest，命令面保持关闭。

授权消费点必须位于所有只读预检完成之后、第一次候选持久化写入之前。

## 4. 私有串口命令

执行器只接受两个固定 schema，每个启动周期最多接受一条非空命令：

```text
GH2D9_PREPARE_V1 <run_suffix> <unlock_token_hex> <persistence_key_hex> <authorization_digest> <candidate_digest>
GH2D9_VERIFY_V1  <run_suffix> <unlock_token_hex> <persistence_key_hex> <authorization_digest> <candidate_digest>
```

固定约束：

- 6 个字段，单空格分隔，整行不超过 384 字节；
- `run_suffix` 只能为 8—24 个小写字母或数字；
- 四个摘要/密钥字段均为 64 位小写十六进制；
- unlock token、持久化密钥和授权摘要不得为全零；
- unlock token 的 SHA-256 必须与编译绑定一致；
- candidate digest 必须与确定性 candidate profile 完全一致；
- 命令错误、摘要错误、重复命令或额外命令均 fail closed；
- 串口输出不得回显任何秘密字段。

`PREPARE` 成功后固件自动重启；重启后只接受 `VERIFY`。VERIFY 仅执行只读恢复与 digest 复核，不执行第二次 PREPARE。

## 5. 持久化事务

测试分区冻结为：

```text
partition=gh2d8_p2d9
offset=0x400000
size=0x10000
namespace=gh2d8_s2d9
```

名称继续采用冻结隔离驱动接受的 `gh2d8_` 前缀，但分区和 namespace 均与 Stage 2D-8 G2 的 `gh2d8_nvs/gh2d8_state` 不同。这样无需修改已验收的 Stage 2D-8 驱动源码，同时保持 Stage 2D-9 存储物理隔离。

该分区只服务 Stage 2D-9 专用测试板，不得复用生产 NVS。允许的事务顺序：

1. 写入 generation=1 的 candidate profile；
2. 校验 candidate digest；
3. 写入 durable `PREPARED` marker；
4. 关闭 writable handle；
5. 自动重启；
6. 使用私有 VERIFY 命令加载仅驻留 RAM 的测试持久化密钥；
7. 只读恢复并复核。

在 durable `PREPARED` marker 之前发生失败，恢复结果必须为 `EMPTY`；marker 已提交后发生中断，恢复结果必须为完整 `PREPARED`。不得出现半有效 candidate。

## 6. 成功条件

```text
ACTIVE_GENERATION=0
ACTIVE_PROFILE_UNCHANGED=true
CANDIDATE_GENERATION=1
CANDIDATE_STATE=PREPARED
CANDIDATE_DIGEST_MATCH=true
PREPARE_AUTHORIZATION_CONSUMED=true
ACTIVE_SESSION=false
CANDIDATE_SESSION=false
ACTIVATE_AUTHORIZATION_PRESENT=false
CLEANUP_AUTHORIZATION_PRESENT=false
REBOOT_RECOVERY=PREPARED_PRESERVED
MQTT_OPERATION_ATTEMPTED=false
```

## 7. 禁止事项

- `ACTIVATE_PROFILE`；
- `CLEANUP_TEST_STATE`；
- 连接 Wi-Fi、MQTT 或任何 Broker；
- 加载生产凭据或测试私钥到公共证据；
- 访问、读取或写入 eFuse；
- 启用 Secure Boot 或 Flash Encryption；
- 修改正式 `f1_0_rc2.yml` 或产品 packages；
- 操作 M401A、T1、Home Assistant、Mosquitto、greenhouse-manager；
- Ready、merge、release；
- 重放 Stage 2D-8 的任何 D2。

## 8. Recovery

破坏性边界后的规定失败最多允许一次 locked recovery。Recovery 只能恢复到无网络、无密钥、无 PREPARE/ACTIVATE/CLEANUP 入口的锁定固件；不得在 recovery 中继续或重试 PREPARE。
