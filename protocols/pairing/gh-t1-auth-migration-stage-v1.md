# gh-t1-auth-migration-stage-v1

## 1. 目的

M2.4d 定义真实 T1 认证迁移的“私有、非激活暂存”阶段。

该阶段只能在 M2.4c 最终就绪报告全部门禁通过后执行。暂存工具读取：

- 已验证的回退包；
- 已验证的认证迁移包；
- 真实运行容器的只读就绪状态；
- 每个 Compose deployment 的实际配置文件和可选 `.env`。

工具只在新的私有暂存目录中创建副本，不得写入任何运行目录或秘密激活目录。

## 2. 前置门禁

必须同时满足：

```text
schema = gh.m2.t1-auth-migration-readiness/1
read_only = true
apply_enabled = false
current_services_modified = false
source_binding = true
ready = true
```

`gates` 中所有项目必须为 `true`。

迁移包还必须与选定回退包精确绑定：

- 回退包文件名；
- SHA-256；
- 回退包 schema；
- Mosquitto 镜像 ID。

任何不一致必须在创建暂存目录之前阻断。

## 3. 暂存内容

暂存目录包含：

```text
stage-manifest.json
activation-plan.json
README.txt
source/<原始迁移包>
payload/<迁移包完整解包内容>
baseline/deployments/<编号>/config-*
baseline/deployments/<编号>/environment.env（仅原文件存在时）
```

每个真实 Compose deployment 独立记录：

- project；
- container；
- live working directory；
- 原配置文件路径、模式和 SHA-256；
- 暂存副本路径、大小和 SHA-256；
- 可选 `.env` 的原路径、模式和 SHA-256。

配置文件可能包含内嵌秘密，因此所有基线副本均按敏感文件处理。

## 4. 权限

暂存输出父目录、暂存根目录和全部子目录必须为：

```text
0700
```

全部文件必须为：

```text
0600
```

暂存工具必须拒绝将输出创建在以下活动路径内：

- 任一真实 Compose working directory；
- `/opt/greenhouse-secrets/mqtt` 或显式指定的真实秘密根目录。

暂存文件不得包含符号链接、设备文件、目录穿越路径或非普通文件。

## 5. 安全标志

`stage-manifest.json` 必须包含：

```json
{
  "schema": "gh.m2.t1-auth-migration-stage/1",
  "classification": "secret-local-inactive-stage",
  "portable_off_host": false,
  "activation_enabled": false,
  "current_services_modified": false,
  "active_paths_modified": false,
  "fresh_backup_required_before_apply": true
}
```

`activation-plan.json` 只能描述未来步骤，不能包含可自动执行命令，且必须保持：

```text
activation_enabled = false
requires_explicit_gate = true
preserve_anonymous = true
anonymous_closure_enabled = false
```

## 6. 完整性校验

生成完成后必须重新验证：

- 暂存根和所有子目录权限；
- 文件清单与实际文件集合完全一致；
- 每个文件为普通非符号链接文件；
- 每个文件模式为 `0600`；
- 每个文件大小与 SHA-256；
- 原迁移包暂存副本与原包 SHA-256 一致；
- Compose 和 `.env` 源文件在复制期间没有发生变化。

## 7. 成功报告

成功报告 schema：

```text
gh.m2.t1-auth-migration-stage-report/1
```

报告只能包含：

- 暂存目录名称；
- 源迁移包名称；
- deployment 数量；
- 文件数量；
- 三个 false 安全标志。

报告不得包含用户名对应密码、bootstrap 密码、Home Assistant 密码、节点密码或 `.env` 内容。

## 8. 明确禁止

本阶段不得：

- 写入 `/opt/greenhouse-secrets/mqtt`；
- 修改真实 Compose 文件或 `.env`；
- 调用 `docker compose up/down`；
- 创建、停止、重启或重建任何运行容器；
- 配置真实 Mosquitto Dynamic Security；
- 修改 manager、Home Assistant 或节点凭据；
- 关闭 `allow_anonymous true`；
- 将暂存目录复制离开 T1、上传或提交到 Git。

暂存完成不等于授权真实迁移。任何真实 apply 阶段仍必须在执行前立即生成新的回退包，并通过独立显式门禁。
