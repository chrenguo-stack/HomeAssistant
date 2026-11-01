# T1 Broker 身份生产事务适配器协议 V1

状态：M2.4g-5s Draft

## 1. 目的

本协议实现生产事务所需的宿主机文件适配器，但仍不提供 live CLI、授权 claim 或执行入口。实现只能在全部私有材料和运行时绑定验证通过后准备完整快照。

## 2. 输入绑定

适配器必须同时验证：

- production transaction adapter contract；
- bundle-bound transaction plan；
- production executor contract；
- private runtime binding manifest；
- activation handoff 中全部六项 mode-0600 材料及其 SHA-256。

任一绑定不一致时，禁止创建快照或修改 Broker。

## 3. 路径约束

生产路径只能从 private runtime binding manifest 解析：

- Mosquitto config bind source；
- Mosquitto data bind source；
- `mosquitto.conf`；
- `dynamic-security.json`。

禁止由 CLI 或调用者直接传入宿主机 config/data 路径。所有路径必须为绝对路径、非符号链接，并位于各自已绑定目录内。

## 4. 快照

首次写入前必须：

1. 拒绝 config/data 树中的符号链接和特殊文件；
2. 完整复制 config 与 data 目录；
3. 记录每个目录和文件的相对路径、类型、mode、uid、gid 与文件 SHA-256；
4. 将 inventory 原子写入 mode-0600 文件；
5. 快照目录必须为 mode 0700。

快照准备阶段不得重启服务或修改当前服务目录。

## 5. 变更顺序

适配器执行的固定顺序为：

1. 原子替换 `mosquitto.conf`，追加规范 Dynamic Security plugin 行；
2. 原子写入仅供首次初始化使用的密码文件；
3. 仅重启 Mosquitto；
4. 等待绑定 data 路径出现 Dynamic Security state；
5. 将 state 文件收紧为 mode 0600 并删除首次初始化密码文件；
6. 通过注入的进程内 Broker driver 提交精确 request；
7. 验证 provisioning 身份；
8. 删除 bootstrap admin；
9. 验证 bootstrap 已拒绝且 provisioning 仍可用；
10. 执行完整 postactivation audit。

匿名兼容必须保持开启，事务内禁止关闭匿名访问。

## 6. 回退

任何进入 mutation 后的故障均必须调用 rollback adapter：

- 删除快照中不存在的新增文件和目录；
- 使用同目录临时文件、file fsync、atomic replace 和 directory fsync 恢复每个文件；
- 恢复目录与文件 mode、uid、gid；
- 验证恢复后的完整 inventory 与快照一致；
- 仅重启 Mosquitto；
- 验证匿名 retained state 可读；
- 验证 Dynamic Security state 不存在。

回退失败属于终止故障，不能报告成功。

## 7. 当前安全边界

本阶段代码存在以下限制：

- 无 CLI 或 live apply 入口；
- 不创建、claim 或消费授权；
- 不包含默认生产 Broker driver；
- 只有显式注入 driver 后才能调用 mutation；
- Home Assistant 官方 MQTT 重配置不属于本事务；
- 实体节点凭据交付不属于本事务；
- 匿名关闭继续被禁止。

准备完成报告仍必须包含：

```text
execution_entrypoint_installed=false
authorization_claimed=false
claim_enabled=false
production_executor_available=false
execution_enabled=false
apply_enabled=false
ready_for_live_activation=false
current_services_modified=false
preserve_anonymous=true
anonymous_closure_enabled=false
```
