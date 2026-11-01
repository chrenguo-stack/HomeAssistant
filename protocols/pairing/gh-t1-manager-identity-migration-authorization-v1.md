# T1 Manager Identity Migration Authorization V1

状态：M2.4g-6c Draft

## 1. 目的

本协议在 M2.4g-6b 私有准备包通过后，提供一个短时、单次、全指纹绑定的 manager 迁移操作员授权。授权只表明操作员允许后续事务继续设计或执行；授权模块本身不修改 Compose、secret、容器、Broker、Home Assistant 或节点。

## 2. 阶段边界

成功创建授权后仍必须保持：

```text
apply_enabled=false
ready_for_manager_migration_apply=false
current_services_modified=false
manager_identity_migrated=false
node_credentials_delivered=false
preserve_anonymous=true
anonymous_closure_enabled=false
```

授权不是 live apply，也不得被解释为 H3 或 N2 完成。

## 3. 只读重新验证

每次 request、create 和 verify 均必须重新验证：

1. 6b preparation manifest、records、runtime binding 和 transaction plan；
2. manager environment、password 和 Compose fragment 的 SHA-256；
3. postactivation manifest 与 inactive Stage manifest 绑定；
4. 当前 `greenhouse-manager` 容器 ID、镜像、启动时间、运行状态和 restart count；
5. 当前容器仍未配置 manager MQTT 用户名或密码文件；
6. Compose project、working directory、配置文件路径和完整元数据；
7. `.env` 若存在仍为 mode `0600` 且未漂移；
8. active manager password 尚不存在。

实时 Docker 命令只允许：

```text
docker inspect greenhouse-manager
```

任一漂移必须阻止 request、create 和 verify。

## 4. 操作员确认

request 输出精确确认字符串：

```text
AUTHORIZE-M2-MANAGER-MIGRATION:<preparation manifest 前16位>:<manager runtime 指纹>:<compose binding 指纹>
```

create 必须逐字匹配该字符串。不得接受模糊确认、旧确认或部分确认。

## 5. 授权材料

授权文件必须：

- 位于名称以 `greenhouse-m2-manager-authorizations` 开头的 mode `0700` 私有目录；
- 自身为 mode `0600` 普通文件；
- 包含随机高熵 token；
- token 只保存在私有文件中，不得出现在普通 stdout；
- authorization ID 由 token 的 SHA-256 派生；
- TTL 为 60 至 1800 秒；
- `single_use=true`；
- `consumed=false`；
- 与 preparation、runtime、Compose、manager material、postactivation 和 Stage 的 SHA-256 全绑定。

## 6. 创建时二次检查

create 在校验确认字符串后，必须再次运行完整只读 preflight，并要求 request 文档逐字段不变。若两次检查之间发生容器重启、Compose 变化、secret 写入或其他漂移，不得创建授权。

## 7. 验证合同

verify 必须检查：

- schema 与所有绑定字段；
- token 格式与 authorization ID；
- 创建和到期时间；
- 当前时间位于有效期内；
- `consumed=false`；
- 当前实时 preflight 仍通过。

成功 verify 只输出脱敏状态，不输出 token、完整路径、用户名、密码或完整 Client ID。

## 8. 禁止事项

本模块不得：

- claim 或 consume 授权；
- 写入 active secret root；
- 修改 Compose 或 `.env`；
- restart、recreate、stop 或 remove 容器；
- 修改 Mosquitto 或 Home Assistant；
- 下发节点凭据；
- 关闭匿名访问。

## 9. 下一门

M2.4g-6d 应实现隔离的 manager transaction adapters 与故障注入演练，覆盖 fresh rollback、secret 原子写入、Compose overlay、manager-only recreate、认证/订阅/发布验证和完整回退。真实 T1 执行入口仍须在更后的独立 live packet 中提供。
