# Stage 2D-9 G3 单次 PREPARE 执行与证据协议

**版本：** V1.0  
**日期：** 2026-07-22  
**默认状态：** `LOCKED`  
**适用范围：** 专用测试板、隔离 writable test NVS、一次性 `PREPARE_CANDIDATE`

## 1. 执行前提

只有以下内容全部冻结并通过时，才可以进入新的 D2：

1. 源码 commit、V67 Artifact ZIP、G3 merged、locked recovery、seed、manifest 哈希；
2. 专用板与完整产品板 compile-only；
3. 双 clean build 字节一致；
4. Host 事务、manifest、命令协议和失败矩阵；
5. 测试板私有绑定与主机 esptool 环境；
6. runner、launcher、命令组和停止条件哈希；
7. 一次性 unlock preimage、持久化密钥、authorization digest 和 candidate digest 私有绑定；
8. 明确的有效期、一次执行、禁止重放和最多一次 locked recovery。

## 2. 执行阶段

```text
A. host/Artifact/target/USB/chip/Flash 只读预检
B. 读取 0x400000—0x40FFFF，必须与冻结 seed 相同
C. 消费 runner 一次性授权
D. erase/write/verify G3 merged
E. 再次读取测试分区，必须与 seed 相同
F. 启动 G3，等待 PREPARE command-ready
G. 私密发送一条 GH2D9_PREPARE_V1，不在日志中打印命令
H. 要求 PREPARE=pass、active=0、candidate=1、authorization_consumed=true、MQTT=false
I. 观察自动重启，等待 VERIFY command-ready
J. 私密发送一条 GH2D9_VERIFY_V1
K. 要求 VERIFY=pass、candidate=PREPARED、digest_match=true、active_unchanged=true
L. 读取测试分区保存私有证据，必须已不同于 seed
M. 停止；不得 ACTIVATE 或 CLEANUP
```

## 3. 私密字段处理

以下值不得输出到终端、公共日志或 Git：

- unlock preimage；
- persistence key；
- authorization digest；
- candidate command 完整文本；
- candidate profile 内部密码字段；
- 私有板卡标识和串口路径。

runner 必须在保存串口证据前，对上述精确值做替换，并扫描确认没有泄漏。runner 结束时清空进程内字符串，私有授权文件权限为 `0600`，目录权限为 `0700`。

## 4. 成功判据

```text
ACTIVE_GENERATION=0
ACTIVE_PROFILE_UNCHANGED=true
CANDIDATE_GENERATION=1
CANDIDATE_STATE=PREPARED
CANDIDATE_DIGEST_MATCH=true
PREPARE_AUTHORIZATION_CONSUMED=true
ACTIVE_SESSION=false
CANDIDATE_SESSION=false
PROBE_SESSION=false
MQTT_OPERATION_ATTEMPTED=false
RECOVERY_PERFORMED=false
```

启动前测试分区应等于 seed；成功后测试分区应不同于 seed。后者只证明发生了持久化，不作为 candidate 明文或 digest 的替代证据；candidate 正确性由固件 read-only recovery 和 digest 复核证明。

## 5. 失败与 recovery

- 在破坏性边界前失败：停止，不执行 recovery；授权按治理规则退役，不重放。
- 进入破坏性边界后失败：不得重试 PREPARE，最多执行一次 locked recovery。
- recovery 必须 erase 后写入 locked recovery merged，包含原始 seed，使目标 namespace 回到 absent。
- recovery 无论成功或失败都停止，后续需要新的故障分析和新的 D2。

## 6. 证据分层

公共 L1：结果、冻结哈希、阶段、布尔判据、计数、私有归档 SHA-256、禁止项 false。  
私有 L2：授权 JSON、完整 esptool 日志、已脱敏串口日志、启动前后分区、执行摘要。  
秘密 L3：unlock preimage、persistence key、完整私密命令；只存在于单次执行包和运行期内存，不归档到公共证据。

## 7. 固定禁止项

不得执行 `ACTIVATE_PROFILE`、`CLEANUP_TEST_STATE`、Wi-Fi、MQTT、Broker、eFuse、Secure Boot、Flash Encryption、M401A、T1、Home Assistant、Mosquitto、greenhouse-manager、生产环境操作、Ready、merge 或 release。
