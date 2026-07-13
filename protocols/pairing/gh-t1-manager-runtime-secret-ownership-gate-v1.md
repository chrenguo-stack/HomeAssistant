# gh-t1-manager-runtime-secret-ownership-gate-v1

状态：M2.4g-6r Draft

## 目标

解决 greenhouse-manager 以非 root 用户运行时无法读取 root-owned、mode 0600 MQTT 密码文件的问题，同时不降低 secret 权限、不改用明文环境变量、不把 manager 改为 root。

## 运行身份绑定

6b 准备阶段必须绑定：

- `manager_runtime_uid`；
- `manager_runtime_gid`；
- `manager_runtime_user_source`；
- `manager_runtime_image_id`；
- `manager_runtime_user_spec`。

身份来源必须同时覆盖当前容器 `Config.User`、当前镜像 `Config.User` 和使用同一镜像执行的隔离候选 `id -u` / `id -g`。隔离候选必须使用 `--network none`、只读 rootfs、`cap-drop ALL`、`no-new-privileges` 和有限 PID。三个来源不一致、身份无法解析或有效 UID 为 0 时必须失败关闭。不得长期硬编码 `999:999`。

## Secret 所有权

活动密码目标必须满足：

- 普通文件且非符号链接；
- mode 精确为 0600；
- UID/GID 精确等于已绑定的 manager 运行 UID/GID；
- 只读挂载到 `/run/secrets/gh_manager_mqtt_password`；
- `GH_MQTT_PASSWORD` 为空；
- `GH_MQTT_PASSWORD_FILE` 指向该只读容器内路径。

认证环境和 Compose overlay 继续使用私有 mode 0600 文件。不得通过 0640/0644、group/other 读权限、普通密码环境变量或 root manager 绕过所有权约束。

## 授权前候选探针

6i 在创建任何真实 6j 授权前，必须使用绑定镜像和绑定 UID/GID运行一次候选配置探针：

- `--network none`；
- `--read-only`；
- `--cap-drop ALL`；
- `--security-opt no-new-privileges`；
- `--pids-limit 32`；
- 候选密码副本 mode 0600 且归属绑定 UID/GID；
- 密码只读 bind mount；
- `greenhouse-manager --check-config` 只加载配置和读取 secret，不创建 MQTT 服务、不 CONNECT、不 PUBLISH。

探针只保存布尔结果和 schema，不保存 UID/GID、镜像 ID、用户名、Client ID、密码、主机路径或命令输出。候选密码副本无论成功失败都必须删除。

### 旧运行镜像兼容

当当前真实 manager 镜像早于新增 `greenhouse-manager --check-config` 包装入口时，探针必须仍针对同一个已绑定的真实镜像 ID，使用该镜像内已安装的 `greenhouse_manager.config.Settings.from_env()` 固定模块入口完成等价验证。固定程序不得拼接用户名、Client ID、密码或主机路径；仍必须由 `--network none`、只读 rootfs、cap-drop 和 no-new-privileges 提供外部边界。不得因为旧镜像缺少包装 CLI 而切换到未绑定镜像、跳过配置加载或只执行文件 `test -r`。

兼容只覆盖“已支持 `GH_MQTT_PASSWORD_FILE`、但缺少新 CLI 包装入口”的镜像。固定模块探针必须先输出脱敏的密码文件能力布尔值；当绑定镜像本身不支持 `GH_MQTT_PASSWORD_FILE` 或私有文件读取时，6i 必须以明确的 unsupported-live-image 错误失败关闭，不得回退到内联 `GH_MQTT_PASSWORD`。

### 不支持密码文件的实机镜像

当 T1 当前精确运行镜像缺少密码文件能力时，该镜像不满足 6r 前置条件。项目必须先将 manager 升级到支持密码文件的镜像，且升级阶段仍保持未认证 manager 和 anonymous；该升级属于 T1 当前服务变更，必须由操作者单独精确授权。升级后必须从 6b 开始重新采集镜像、UID/GID 和运行绑定，重跑 6e/6f/6i/6j/6k 并生成 fresh rollback；不得重用任何升级前授权或确认。

## 全链路绑定

1. 6b 将运行 UID/GID、用户来源和镜像写入私有 runtime binding。
2. 6h/6i 重跑容器、镜像和隔离身份验证，拒绝 UID/GID、user spec 或 image drift。
3. 6i 将 preclaim probe SHA-256 写入 execution manifest 和 fresh rollback manifest。
4. 6j 授权 request/create/verify 将 probe SHA-256 纳入单次授权绑定。
5. 6k 重跑 live gate 并保留 probe SHA-256；任何漂移均阻止第二次确认。
6. 6o 在 apply 前重新验证 execution package、runtime ownership、probe 和 rollback binding。
7. apply 后 runtime probe 必须同时验证镜像/user spec、密码 mode 0600、密码 UID/GID 和只读 mount。

## 回滚与故障语义

任何 post-claim 失败继续强制 rollback。rollback 必须删除活动密码、认证环境和 overlay，恢复原 Compose 文件，仅重建 greenhouse-manager，并验证旧匿名路径及既有实体连续性。不得修改或重建 Mosquitto、Home Assistant 或节点。

必须覆盖以下失败：

- 容器、镜像或隔离候选 UID/GID 不一致；
- root 有效用户；
- root-owned 0600 候选对绑定用户不可读；
- secret mode 变为 0640/0644；
- secret 或父目录为 symlink/非私有；
- image/user spec 在 6i、6k 或 6o 前漂移；
- candidate `--check-config` 失败或报告网络尝试；
- 绑定的当前镜像不支持 `GH_MQTT_PASSWORD_FILE`；
- apply 后密码 owner、mount 或认证环境不匹配；
- rollback 后仍残留 manager 认证材料。

## 安全边界

- 本协议与代码合入不生成、claim 或重放任何真实授权；
- 已消费授权永久不可重放；
- 不关闭 anonymous；
- 不下发节点凭据；
- 不修改节点固件；
- 不输出 secret、授权、Compose/.env 私有内容或敏感路径；
- 新一次真实迁移仍需全新的 6e/6f/6i/6j/6k、两次精确确认和 fresh rollback。
