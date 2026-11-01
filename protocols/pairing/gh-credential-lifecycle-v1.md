# gh-credential-lifecycle-v1 凭据生命周期账本

状态：Draft / M2.3a  
关联：Issue #17、`gh-pairing-v1`、`gh-dynsec-profile-v1`

## 1. 目的

manager 必须能够在进程或主机重启后判断节点凭据处于稳定、轮换中、撤销或需要人工恢复状态，但生命周期数据库不得成为秘密存储。

## 2. 持久字段

| 字段 | 约束 |
|---|---|
| hardware_id | 主键 |
| node_id | 唯一 |
| active_generation | 正整数 |
| pending_generation | 空或严格大于 active_generation |
| state | active / rotating / revoked / recovery_required |
| reason | 非秘密错误码或操作原因 |
| updated_at | UTC RFC3339 |

禁止保存 MQTT 密码、pairing_pop、临时会话密钥、CA 私钥或完整控制载荷。

## 3. 状态转换

| 当前 | 操作 | 下一状态 |
|---|---|---|
| 无记录 | activate | active |
| active | begin_rotation(N+1) | rotating |
| rotating | commit_rotation | active，active=N+1 |
| rotating | roll_back_rotation | active，active=N |
| 任意已知状态 | revoke | revoked |
| 任意已知状态 | require_recovery | recovery_required |

revoked 和 recovery_required 不允许被普通轮换调用隐式恢复。重新配对或灾难恢复必须走独立、需要用户确认的流程。

## 4. 一致性边界

- begin_rotation 必须先于 Broker 候选密码写入；
- Broker 验证成功后才能 commit_rotation；
- 候选验证失败且 Broker 已恢复旧密码后才能 roll_back_rotation；
- 若 Broker 回滚失败，账本必须进入 recovery_required，禁止报告 active；
- 撤销应先停用 Broker client，再持久化 revoked；中途失败必须记录恢复原因。

M2.3a 只实现秘密无关的账本原语和重启恢复测试，不连接 T1 或真实 Broker。
