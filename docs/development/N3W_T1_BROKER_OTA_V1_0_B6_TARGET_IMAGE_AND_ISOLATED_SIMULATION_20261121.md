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
