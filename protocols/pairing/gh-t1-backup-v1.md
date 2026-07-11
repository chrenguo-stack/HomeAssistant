# gh-t1-backup-v1 T1 本地回退包与隔离恢复演练

状态：Draft / M2.3d  
关联：Issue #17、`gh-t1-shadow-migration-v1`

## 1. 用途与边界

本回退包用于真实 Broker shadow migration 前的同机快速回退。它包含 Mosquitto 配置/数据和 greenhouse-manager 数据，因此按敏感资料处理。

当前格式依靠宿主机目录 0700、归档 0600 保护，只允许留在受控 T1 本机；它不是可携带或云端备份格式。离机备份必须在后续阶段增加用户持有密钥的认证加密。

## 2. 创建

`greenhouse-manager-t1-backup create --output <private-directory>`

- 只通过 `docker cp` 读取三个固定目录；
- 不停止、重启或修改现有容器；
- 不输出文件内容；
- manifest 只记录镜像身份、相对路径、大小、SHA-256、数值 UID/GID 和权限；
- 拒绝组/其他用户可访问的输出目录；
- 拒绝符号链接来源。

## 3. 校验

`verify` 必须检查：

- 归档权限；
- schema 与文件清单完全一致；
- 路径无绝对路径和 `..`；
- 不含链接或特殊文件；
- 每个文件的大小与 SHA-256 一致。
- 每个文件的数值 UID/GID 和权限与 manifest 一致。

## 4. 隔离恢复演练

`drill` 将文件解压到 0700 临时目录，恢复原数值 UID/GID 和权限，检查 SQLite 完整性，并使用备份中记录的精确 Mosquitto image ID 创建 `--network none` 临时容器。只有临时 Broker 能以原文件身份启动且数据库完整才算通过。无论成功失败均删除临时容器和目录，不覆盖真实卷。

## 5. 一致性说明

本阶段生成运行中服务的 crash-consistent 同机回退副本，足以保护首次加载 shadow 插件前的现状。进入凭据正式签发后，必须增加协调快照或短暂停机窗口，并完成认证加密的离机恢复包。
