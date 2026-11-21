# N3-W T1 Broker OTA V1.0 — B6 Target Image / Manifest 与隔离 A→B 模拟

DATE=2026-11-21  
STATUS=SOURCE_IMPLEMENTATION_PHASE_1  
STACKED_BASE_PR=819  
STACKED_BASE_HEAD=eb6a5bebb08798ae0f85d46fc6665ee8c59eab1a  
B5_EXECUTABLE_HEAD=e650f5db373d5cd65fd601c676f3f605998ba132  
PRODUCT_AUTHORITY=T1_Core_Stack_OTA_V1.2  
T1_ACCESS=false  
PRODUCTION_MUTATION=false  
MERGE=false  

## 1. B6 目标

B5 已完成 Broker 宿主恢复引擎 exact package。B6 只补齐目标镜像和真实隔离兼容性证据，不建立第二套事务状态机。

B6 继续固定：

- mutation profile = IMAGE_ONLY_V1；
- Generic V2 / T1_Core_Updater 是唯一升级执行引擎；
- Broker writable Recovery Point 继续保护 /var/lib/n3wfc4-broker；
- TLS/CA、固定 mosquitto.conf、DynSec schema、Manager/HA 配置均不迁移；
- 真实 T1 不访问、不安装、不启动、不停止服务。

## 2. successor 版本选择

当前 predecessor 是 Mosquitto 2.1.2-alpine，生产本地镜像为：

local/n3w-mosquitto:2.1.2-3184566d

B6 选择同一 2.1 系列的 2.1.4-alpine 作为 successor 版本。

依据：

1. Mosquitto 官方 2026-11-17 发布 2.1.3，定义为 critical security release；
2. 随后的 2.1.4 保留安全修复，并修复 2.1.3 引入的 legacy sha512 password rejection 回归；
3. 因此不把存在已知回归的 2.1.3 作为产品候选，直接选择 2.1.4；
4. 版本选择不等于镜像工件冻结。B6 必须再解析 linux/arm64 exact manifest digest、生成 portable archive identity，并把 GitHub Artifact ID/digest 与 target manifest 精确绑定。

官方依据：
- https://mosquitto.org/blog/2026/11/version-2-1-4-2-0-23-released/
- https://mosquitto.org/blog/2026/11/version-2-1-3-released/

## 3. 两阶段 exact binding

Phase 1（本提交）：

- 解析 docker.io/library/eclipse-mosquitto:2.1.4-alpine 的 linux/arm64 manifest；
- 按 manifest digest pull，不依赖 tag 作为最终身份；
- 生成 broker-arm64.tar.gz；
- 用现有 n3w_t1_portable_image_identity.py 计算 archive/config/rootfs identity；
- docker load 后再次验证；
- 上传 GitHub Artifact，再下载并复验 exact bytes；
- 同时执行真实 2.1.2 → 2.1.4 隔离状态兼容与 Recovery Point 回退模拟。

Phase 2：

- 读取 Phase 1 run/artifact 的 exact metadata；
- 新增 infra/n3w-t1/upgrades/broker-2.1.4.json；
- 在 workflow 中固定 run ID、artifact ID/digest、archive SHA256/size、upstream index/manifest digest、local image；
- target 冻结后不再重新拉取 tag，只下载已冻结 GitHub Artifact 做 exact binding verification。

## 4. 隔离真实 Mosquitto A→B 模拟

CI 使用临时目录、临时测试证书和非生产测试密码：

1. 用 predecessor 2.1.2 的 mosquitto_ctrl dynsec init 创建测试 DynSec；
2. 按仓库 production mosquitto.conf 启动 A；
3. 写入 retained predecessor 数据并正常停止，使 mosquitto.db 落盘；
4. 使用正式 Broker Recovery Point 原语创建静止快照；
5. 在同一 state/config/TLS 上启动 2.1.4 B，证明旧 DynSec 认证和旧 retained 数据可读；
6. B 写入新的 retained 数据，证明 target 发生持久化写入；
7. 停止 B，通过正式 Recovery Point 原语恢复；
8. 重新启动 2.1.2 A，证明 predecessor retained 数据仍在、target-only retained 数据消失；
9. 同时运行 B3/B4/B5 的 Generic V2 单元/合同测试，继续覆盖 target-write DynSec 模拟、自动接管、stopped predecessor、tamper/capacity、stale committed rollback、retirement 等路径。

该模拟是隔离 CI，不等于真实 T1 验收。

## 5. 完成边界

Phase 1 成功只表示 exact artifact 已生成并取得真实 A→B 兼容性证据。必须完成 Phase 2 target manifest exact binding 后，才可称 Broker target frozen。

B6 完成后仍不得进入真实 T1。B7 还需独立源码复核，重点复核 B3 source scan→copy opened-fd metadata race 与 source-root metadata invariant。

T1_ACCESS=false  
T1_MUTATION=false  
BROKER_LIVE_APPLY=false  
MERGE=false  
RELEASE=false


## 6. B7 提前源码复核：B3 两个 hardening 点

在 Phase 1 CI 运行期间，对 B3 Recovery Point 做独立复核，确认两处需要局部收紧：

1. scan→copy opened-fd metadata race：旧实现的 inventory 先通过路径 stat/hash 建立，稍后重新 open source fd 时只检查 regular-file，未重新绑定 size/mode/uid/gid。现改为 source fd 打开后、复制后均以 fstat 与 inventory 行精确比较；发生漂移时在 snapshot commit 前 fail closed。
2. source-root metadata invariant：root mode/uid/gid 已进入 source_tree hash，但旧 restore 会在当前 root 元数据与快照不一致时先替换文件，最后才因 tree hash 不符失败。现改为 restore 任何文件 mutation 前先精确比较当前 root 与 manifest root；漂移直接停止，避免 partial recovery。

新增回归测试分别模拟：

- inventory 完成后、source fd open 前把 mosquitto.db 从 0600 改为 0640；
- snapshot 后把 source root 从 0700 改为仍能通过旧宽松校验的 0750，并确认 restore 拒绝后 target-written 文件保持未被替换。


## 7. Phase 1 Attempt 01 Failure 与局部修复

Attempt 01 exact head = c42c178339974b275d5133b102f28cd6816d995d。

结果：

- source = SUCCESS；
- exact-artifact = SUCCESS；
- isolated-a-to-b = FAILURE。

失败发生在 predecessor 2.1.2 已成功启动之后。根因与 KNOWN_FAILURES 的 KF-102 相同：`mosquitto_ctrl dynsec init` 创建的 `admin` 是 Dynamic Security 管理员，不具备普通 application topic 的 `publishClientSend` 权限，而 Attempt 01 fixture 错误地使用 admin 对 `n3w/b6/#` 做 readiness/application publish。

这不是 2.1.4 镜像、portable identity、Recovery Point 或 Generic V2 失败。

修复规则：

- admin 只用于 `dynsec listClients` readiness 和 `$CONTROL/dynamic-security/v1` 管理命令；
- 在 predecessor 2.1.2 中创建独立 throwaway application role/client；
- application role 仅允许 `n3w/b6/#` 的 publishClientSend、subscribePattern、publishClientReceive；
- 所有 retained application publish/subscription 使用该 application client；
- 不扩大 admin 权限，不开启 anonymous，不修改 production mosquitto.conf；
- contract test 明确禁止 admin 被重新用于 `n3w/b6/#` application retained publish。

Attempt 01 的 exact-artifact 虽然成功，但后续源码 head 已变化，因此不作为最终 frozen target artifact；新 head 必须重新产生 exact artifact 和隔离模拟证据。


## 8. Phase 1 Attempt 02 Failure 与局部修复

Attempt 02 exact head = cc8c1e015b5e1d940cf51fa9ba35e2076e783ffd。

结果：

- source = SUCCESS；
- exact-artifact = SUCCESS；
- Broker Recovery Support Exact CI = SUCCESS；
- isolated-a-to-b = FAILURE；
- Public repository safety = FAILURE。

Attempt 02 仍在 predecessor 2.1.2 fixture 初始化阶段失败，尚未进入 target 2.1.4 与 Recovery Point A→B 核心路径。新增的 raw $CONTROL publish 方式没有形成稳定的管理命令闭环；同时 workflow heredoc 中的非空敏感字段字面量触发 repository safety gate。

Attempt 02 修复为：

- 不再手工拼 raw $CONTROL JSON；
- 全部 DynSec fixture 变更使用 Mosquitto 2.1.2 官方 mosquitto_ctrl 命令：createRole、addRoleACL、createClient、addClientRole；
- admin 继续只承担 DynSec 管理；
- application client 继续只承担 n3w/b6/# 的业务发布/订阅；
- ADMIN 与 APP_PASSWORD 均在 CI runner 内通过 openssl rand 动态生成，不在仓库保存静态密码；
- createClient 的新 client password 通过 stdin 提供，不把动态密码写入 tracked YAML。

Mosquitto 2.1.2 官方 Dynamic Security 文档确认：
- createClient 会交互读取新 client password；
- addClientRole 语法为 username / rolename / priority；
- addRoleACL 支持 publishClientSend、publishClientReceive、subscribePattern 及 allow/deny/priority。

Attempt 02 的 exact-artifact 同样不作为最终 frozen target，因为修复后 source head 再次变化。


## 9. Phase 1 Attempt 03 Failure 与局部修复

Attempt 03 exact head = 92786adc2e0b8e0df8e9f7607ebbb9e7987bc32b。

结果：

- Public repository safety = SUCCESS；
- Broker Recovery Support Exact CI = SUCCESS；
- source = SUCCESS；
- exact-artifact = SUCCESS；
- isolated-a-to-b = FAILURE。

日志证明 createRole 与 3 条 addRoleACL 均已执行，随后进入 createClient 的交互式新密码输入。失败仍发生在 predecessor 2.1.2 fixture 初始化阶段，尚未进入 2.1.4 target。

对 Mosquitto v2.1.2 exact source apps/mosquitto_ctrl/dynsec_client.c 复核确认：

- createClient 原生支持 -p <password>，可关闭交互式 password prompt；
- addClientRole 支持 username + rolename + optional priority，现有 100 参数合法。

因此 Attempt 03 不再把失败归因为 addClientRole 语法，而是收敛为容器化 CI 中不必要的交互式 password capture 路径。修复改为：

- dynsec createClient "$APP_USER" -p "$APP_PASSWORD"；
- 保留 dynsec addClientRole "$APP_USER" "$APP_ROLE" 100；
- 追加 getRole/getClient 确认 role/client inventory 可读取；
- 输出 BROKER_B6_DYNSEC_APPLICATION_FIXTURE=PASS 阶段标记；
- 禁止再使用 docker exec -i 的交互密码输入路径。

该修复仍只修改隔离 CI fixture，不改变生产 Broker、Generic V2 或 Recovery Point 源码。


## 10. Phase 1 Attempt 04 Failure：增加无语义变更的阶段可观测性

Attempt 04 exact head = bd7f7f247ae8634bad77cf1695da4e2b23f7dc5e。

结果：source/exact-artifact/Public repository safety/Broker Recovery Support Exact 均 SUCCESS，isolated-a-to-b FAILURE。

本轮已出现 BROKER_B6_DYNSEC_APPLICATION_FIXTURE=PASS，证明 createRole、三条 ACL、createClient、addClientRole、getRole、getClient 已完整通过。失败发生在此后、BROKER_B6_REAL_RECOVERY_POINT_CREATE 之前。

现有日志无法唯一判定 remaining boundary 是 probe publish、predecessor retained publish、graceful stop、DynSec file、mosquitto.db 或 pre-target hash capture。为避免继续猜测，本提交只增加逐边界 PASS 标记，并同时为 target start/version/read/write/stop、state changed、restore hash、rollback predecessor read 增加标记。

该提交不改变 fixture 条件、ACL、Broker 配置、Recovery Point 或产品升级逻辑，仅提升 CI 失败定位能力。


## 11. Phase 1 Attempt 05 Failure：Broker state fixture 权限修复

Attempt 05 exact head = 5f20140e8d833b736943ac17ea3e1472284865ad。

阶段标记确认：DynSec application fixture、application probe、predecessor retained publish、predecessor graceful stop 均 PASS；随后在 dynamic-security.json presence check 前失败。

fixture 在初始化后明确执行 `chown -R 1883:1883` 且把 Broker data root 设为 0700，因此普通 GitHub runner 用户不能遍历 `$WORK/data`。Recovery Point 本身已经用 sudo 运行，但紧邻的 `test -s` 与 `sha256sum` 仍以普通 runner 身份执行，形成测试夹具权限不一致。

修复只把 Broker state 文件 presence/hash 检查改为 sudo，包括 pre-target capture、target state-change check 与 restore hash check；不改变生产目录权限、不放宽 0700、不修改 Broker/Recovery Point 产品代码。
