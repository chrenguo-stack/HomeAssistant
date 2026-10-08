# PR #522 Gate F independent review and clean-board acceptance plan

STATUS=REVIEW_ONLY
PHYSICAL_USE_READY=false
PRODUCTION_AUTHORITY=false
REVIEW_SOURCE=67a0460231867b8e9b4cb7b7d5b0bd73478f4fc1
REVIEW_SOURCE_TREE=13354818653e27cad8891bd2f3555e4f3feccc2b
REVIEW_PR_HEAD=35ca63b62c224dc95350f09f46671df8742fe583
REVIEW_BASE=d3c158b4376ca0577e4a3a45a18a6c5c6e994e75
MAIN_OBSERVED=d423211b6196c2f2f0f01dff072c4f877fbe58ee
T1_ACCESS=false
BOARD_ACCESS=false
SOURCE_MUTATION=false
MERGE=false

## 1. 独立结论

归档现场证据支持 R2 在 Board B 上完成旧 Broker 失败、Manager discovery、当前 T1 TCP/TLS/MQTT 连接、RAM candidate promotion，以及 Direct telemetry 到达 Manager。不能因此宣布 clean product-state Gate F 或完整换址产品验收通过。

本轮核对源码与仓库现场归档，没有重新连接 T1/板卡，也没有独立读取原始 pcap/flash。所谓实机已证明，是对已归档证据的判断，不是本轮重新执行的物理测试。

R2 地址恢复逻辑暂无必须重写的证据。但发现独立的首次配对 boot-counter 初始化断电窗口。它在 PR base 已存在，不是 R2 引入；仍影响全新产品状态，不能只归为 Board B legacy 问题。建议冻结 relocation 设计，单独做最小初始化修补及回归，再绑定最终固件进行新板验收。

## 2. Board B 根因

同一 node 的 Manager durable high-water 远高于板端修复后的小值 monotonic counter，且 Manager 已收到 ingress 并明确拒绝 stale_boot_session。这与 KF-050 历史随机 boot ID 的迁移问题一致；不是未收到消息。

Manager 拒绝低 session 是正确行为，不清零、不降低、不放宽。读取 flash 可能导致额外启动，因而 flash 最大记录不必等于前一条 packet 的 session；数量级差距及同一身份绑定足以支持这里的分类，但最终证据仍应保留精确绑定。

Board B 退出 final clean-product acceptance；保留现状和证据，legacy migration 独立排期。不能假定现有 recovery-floor helper 可直接处理“已有合法但过小 counter”：当前 helper 对非 missing counter 有严格 exact-floor 前置条件。不要盲目运行。

## 3. 新发现：KF-050 首次配对初始化窗口

精确文件：
- firmware/esphome_rc/components/greenhouse_n3w_product_core/greenhouse_n3w_product_core.h
- firmware/esphome_rc/components/greenhouse_n3w_product_core/n3w_simple_pairing_client.cpp
- firmware/esphome_rc/f1_0_rc2/packages/n3w_product_telemetry.yml

源码链：
1. setup() 第 37 行从是否已有完整 peer/broker 身份计算 fresh_identity_candidate_。
2. persist_bundle_() 第 643/646 行持久化 peer/broker；此过程未持久化 boot_state。
3. boot_state 初始化位于 begin_boot_session_if_needed_()，由 take_telemetry_identity() 第 223 行触发；生产 telemetry interval 为 60 秒。
4. 若在配对持久化后、首次 telemetry identity 分配前重启，身份存在而 counter 缺失。
5. 下一启动 fresh_identity_candidate_=false。
6. 第 464 行拒绝初始化，并 mark_failed()；不会产生合法 telemetry identity。

这不是随机 high-water 污染，而是普通首次配置过程中的断电恢复缺口。正常不断电路径仍可成功，因此只做顺利首次配对再换址会漏掉它。

本轮对实际源码的 persisted_runtime_state_present_() 和 begin_boot_session_if_needed_() 原文方法做了隔离 C++ host 执行；NVS/其余组件用内存替身。结果：
REBOOT_AFTER_PAIRING_BEFORE_FIRST_TELEMETRY=REJECTED counter_present=0 marked_failed=1
UNINTERRUPTED_FIRST_TELEMETRY_THEN_REBOOT=ACCEPTED counter=2

该复现证明所提取方法的分派结果，不是完整 ESPHome component 测试或断电实机验证。配对写入和延迟调用关系由源码审查确认。

最小修补方向：
- 仅在明确证明是全新身份时，在任何正式身份持久化/提交之前，建立并回读验证初始 boot floor；
- 不能用“已有身份但缺 counter”作为自动补零条件；
- 不覆盖已有 counter，不放宽 corrupt/I/O/rollback fail-closed；
- 明确初始化与配对持久化顺序，保证中断后可重入；
- 增加配对写入前后、首次 telemetry 前的重启行为测试；
- 修补可放入 #522 的小修订，或单独前置修补后重新绑定 #522。无须重写 R2 relocation 或扩展 B2。

CLASSIFICATION=INHERITED_PRODUCT_CORRECTNESS_GAP
R2_NEW_REGRESSION=false
CLEAN_PRODUCT_RELEASE_BLOCKER=true
SOURCE_FOLLOWUP_REQUIRED=true
KNOWN_FAILURES_RELATION=KF-050_FOLLOWUP
KNOWN_FAILURES_CENTRAL_ENTRY_CHANGE=NOT_PERFORMED_REVIEW_ONLY

## 4. 新板与初始配置

使用全新 ESP32-C6，先做经授权的只读资格确认：
- ROM/chip/revision/flash size、安全配置与实际产品目标匹配；
- 记录唯一 hardware identity，不能复用 Board A/B 的身份；
- 读分区/NVS，确认没有旧项目 peer/broker/setup/boot-state；
- Manager 对新 node 没有旧 replay/canonical 身份记录；
- “未使用”是输入，不能替代证据；发现历史状态即停止并分类，不直接 erase 掩盖。

资格确认后，用正式产品镜像建立空产品状态：
- bootloader、partition table、OTA metadata、application 必须来自同一受审 artifact；
- offsets 依据 artifact manifest/partition table，不能照搬 Board B 的 minimal-write 两项；
- 只允许在新板绑定并明确授权后 clean NVS/full erase；不得触碰生产旧板；
- Setup Secret/PoP 使用正式 provisioning 路径，不导入 Board B 状态，不用 legacy helper/harness；
- 配对完成后必须确认 Manager COMMIT 和至少两条正式 canonical telemetry；
- boot_id 非零，Manager high-water 与接收会话一致，同 boot seq 严格前进；
- 完整产生 telemetry 的受控重启后 session 增大。计数在首次 identity 分配时创建，不把“每个电气 reset 必然 +1”当合同；没有隐藏额外启动时可精确对账。

当前 R2 artifact 元数据已重新核对：
run=37204582611
artifact=11303803442
outer_sha256=be604ae4bba09d1a675017518a8847fdd655f2f5bb64dca200bb6e8d49378582
expired=false
归档 firmware SHA256=7a4a53f08fd9550f46637a216f8bee89903428805f5de40d1e3bec9b17bc05ef
本轮未下载二进制重算内层 hash。若初始化修补改变产品源码，最终验收必须改绑新 source/artifact；旧 R2 证据保留为 relocation 阶段证据。

## 5. stale Broker 构造

推荐：同一二层测试网络上，同一 T1 从实际地址 A 变为实际地址 B；节点 SSID、网络及身份不变。

A/B 必须经过现场地址冲突、DHCP、接口、路由、Docker publication、ingress 和回滚检查，本轮没有足够 fresh live topology 冻结具体命令。

步骤：
1. T1=A。正式 provisioning 使新板 durable Broker host=A，auto discovery 正常，TLS identity/CA/credentials 固定。
2. 特别检查 GH_N3W_NODE_BROKER_HOST；不能认为 PAIRING_ADVERTISED_HOST=auto 自动保证 credential bundle 的 Broker host=A。现有故意 stale 配置不适合作为新板健康初始条件。
3. 初始环境配置如需重启 Manager，必须在测试基线之前完成。冻结 container identity、StartedAt、restart counts、身份材料 hash、board durable Broker record。
4. 无可用 Relay 的受控场景；不要关闭生产 Relay 来凑条件。
5. 节点保持运行，不 reset。不改节点 NVS。
6. 通过预先冻结的网络变更方法使 T1=A->B；移除 A，不保留 alias/NAT/forwarder。
7. 不重启 Manager/Broker。auto discovery 必须在同进程内返回 B；节点连接 B:8883。
8. 观察 candidate promotion、Manager accepted 和 canonical seq 推进。
9. B 保持不变，受控冷启动节点一次；仍从 durable A 出发并自动恢复 B，boot session 增大，canonical 继续推进。
10. 保存证据后按冻结网络回滚方案恢复环境；不得恢复旧 NVS 或 Manager replay 快照。

Manager 当前 main 的 n3w_simplified_discovery.py 确实在每次 auto response 中通过 candidate_for()/resolve_route_selected_ipv4(source_ip) 选择路由本地 IPv4。但运行镜像是否包含该实现、现场路由是否选择 B，需要 live preflight。

若无法安全修改实际 T1 地址，则停止该执行准备；不要用手改 Broker host、仅 DNS 变更、保留 A 的地址别名或伪造 discovery 代替这一 acceptance 场景。

## 6. PASS / FAIL 与计时

必须 PASS：
- 健康初始 canonical 基线及新身份绑定成立；
- 原 durable A 的真实不可达成立；
- 相同运行中的 Manager discovery 返回 B；
- 节点不经 repair pairing，通过既有 TLS/CA/MQTT identity 连接 B；
- runtime candidate promotion；
- Manager 接受新 production telemetry，canonical 至少连续推进两次；
- durable Broker host 仍为 A，身份/凭据/TLS 记录未变；
- Manager/Broker container identity、StartedAt、restart count 均不变；
- 无 Relay 本轮恢复在预先冻结的 120 秒产品验收窗口内；
- B 上受控重启后再次自动恢复，并保持 session 单调。

辅助但不能单独判 PASS：
TCP handshake、MQTT Connected、local publish accepted、candidate promoted、CI green、单张 canonical 截图、单独 restart count。

时钟分别记录：
- 地址 A 真正撤除/失效时刻；
- 节点首次确认持续 MQTT disconnected 的时刻；
- discovery 开始/结束；
- retarget/MQTT connected/promotion；
- 首次 Manager accepted/canonical 变化；
- 下一条 canonical 变化。

10 秒 trigger 从符合 Direct+Wi-Fi-ready+MQTT-disconnected 条件开始计，不等于拔网线或 reset 后必然第 10 秒发包。
1 秒 discovery 为收集窗口，6 秒 candidate 为上限，2 秒为 cleanup reserve。允许事先约定的小幅调度/取证误差，不能失败后追认延长。
存在 60 秒 discovery 最小间隔，应记录它而不是把所有重试都要求 10 秒。

重要源码边界：
standalone Direct 分支使用 discovery-completed + candidate/cleanup 的局部 deadline；它未直接引用 DirectRecoveryAttempt 的 120 秒 absolute deadline。
30/120 秒父预算属于 Direct recovery 状态机路径。不能把 standalone 源码描述为“由同一个 120 秒父计时器强制终止”。
120 秒可以作为本次真实换址到可用连接的产品验收上限，且须同时记录从 MQTT failure 起计的时间。超限不能靠重置计时器通过。

生产 telemetry 保持 60 秒。canonical 首条最多另等一个业务周期加预先定义的小裕量，不把业务周期悄悄算成 relocation 超时，也不缩短 cadence 使测试好看。建议 promotion 后观察 180 秒，要求至少两次 canonical 前进；加一次冷启动复测即可，不默认长时间 soak。

healthy Relay 30 秒不能由这次无 Relay 测试替代证明，沿用既有独立 evidence，不重开 KF-094/095/096。

有效前置条件下功能失败=FAIL；身份/地址/镜像绑定不符或环境不可控=STOP/INVALID。两者都不能判 PASS。

## 7. 必留证据

- exact source/tree、PR head、artifact/run、四类固件文件 hash、实际写入与校验记录；
- 新板 ROM identity、初始分区/NVS 判定及新 node 映射；
- pairing COMMIT、前后 session/seq/canonical 和 Manager replay 只读记录；
- A/B 变更前后接口/路由/publication/ingress，A 不再服务的证据；
- 连续 serial、discovery/TCP 抓包、Broker 认证日志、Manager accepted/canonical 记录；
- 一致的时间基准、所有 reset 与 reconnect 动作；
- durable Broker record 的前后比较及 cold-boot 二次 rediscovery；
- container identity/StartedAt/restart count，TLS/credential hash 不变；
- 回滚结果。

原始 NVS/packet/credentials 证据可能包含秘密，只放私有 evidence root；公共仓库保存去敏结果和 hash，不提交秘密或私网地址。NVS 整分区 hash 会因 boot counter/日志正常变化，不能要求它整体不变；应比较相关 record。

## 8. 风险与防误判

- 不把 Broker 的 retained/旧 canonical 当本次新帧；对账 node/boot_id/seq。
- 同 boot 换地址后 boot_id 应保持，seq 继续；只有受控 reboot 后才要求新 boot_id。
- 不把旧 A 的 TLS timeout 误判成新 B 的 TLS 失败。
- RAM-only 意味着 reboot 后会重新发现；这是必须验证的行为，不是失败本身。
- 只从 NVS 原始页面挑“最大合法历史记录”不足以证明当前 active key；正式验收需解析有效当前记录或用受审读接口。
- serial 打开、esptool/read flash 可能 reset；计时窗口内不插入这些操作。
- 不在故障后恢复旧全 flash/NVS 快照，否则可能回滚 counter；网络 rollback 不能包含身份 rollback。
- 新板 happy path 不能覆盖首次配对前后断电原子性。
- 继承的 counter 初始化缺口须单独闭环，不能因为来源较早就宣布不存在。

## 9. 合并结论

CURRENT_MERGE_ALLOWED=false
R2_RELOCATION_REWRITE_REQUIRED=false
PRODUCT_BOOT_INITIALIZATION_REPAIR_REQUIRED=true
CLEAN_BOARD_FINAL_GATE_F=PENDING

不能承诺“当前 R2 新板顺利一次即可 merge”。需最小初始化修补/回归闭环、最终 source/artifact clean-board Gate F、required CI、stacked PR base/integration 一致性及正常 merge 授权。若产品代码变化，67a0460 原 artifact 不再是最终 whole-product acceptance authority。

本轮没有全量重审 V1 或重新打开 radio 恢复 guard。

## 10. NEXT_ONE_GATE

N3W_CLEAN_PAIRING_BOOT_COUNTER_INITIALIZATION_CLOSURE_20261005_01

下一门只针对：
- 将本次提取方法复现提升为完整组件/现有 host 框架重启回归；
- 在首次身份持久化之前建立可靠初始 boot floor；
- 保持既有身份 counter 缺失/损坏 fail-closed；
- 冻结最小修补及 exact artifact 后，再回到 clean-board preexecution design。

不执行 Board B helper，不改 T1，不清 high-water，不先烧新板碰运气。

## Evidence scope / archive

The report and reproducer below are public-safe review artifacts. No live raw evidence was newly collected. Source/test files in the repository are unchanged. Central KF-050 entry is not rewritten by this independent review; this document records its required follow-up. This archive is not a production authorization.

## Appendix: extracted-method host reproducer

The two production methods below are copied without changes from the exact reviewed header. Other types are intentionally minimal in-memory substitutes. The failing path returns before any mocked boot-manager method. Do not call this a complete component or physical power-loss test.

Compile: g++ -std=c++17 -Wall -Wextra -pedantic repro.cpp -o repro
Run: ./repro

```cpp
#include <cstdint>
#include <iostream>
#define ESP_LOGE(...) ((void)0)
enum class SimpleNvsStatus { OK, MISSING };
enum class StoreStatus { OK, MISSING, CORRUPT, IO_ERROR };
enum class CoreError { NONE, ERROR };
struct ProvisionedPeerStateV2 { int system_id=1,node_id=1; bool valid() const{return true;} void clear(){} };
using ProvisionedBrokerStateV2=ProvisionedPeerStateV2;
struct IdentityStore { bool present=false; SimpleNvsStatus load(ProvisionedPeerStateV2*){return present?SimpleNvsStatus::OK:SimpleNvsStatus::MISSING;} };
struct CounterStore { bool present=false; uint64_t value=0; StoreStatus load(uint64_t* out){*out=value;return present?StoreStatus::OK:StoreStatus::MISSING;} };
struct ManagerStub {
  bool initialized=false;
  bool ready(){return initialized;}
  CoreError provision_recovery_floor(CounterStore* s,uint64_t v){s->present=true;s->value=v;return CoreError::NONE;}
  CoreError begin(CounterStore* s,uint64_t){++s->value;initialized=true;return CoreError::NONE;}
};
struct ActualMethods {
  IdentityStore peer_store_,broker_store_;
  CounterStore& boot_session_store_;
  ManagerStub boot_session_manager_;
  bool fresh_identity_candidate_=false,failed=false;
  ActualMethods(CounterStore& s,bool identity):boot_session_store_(s) {
    peer_store_.present=broker_store_.present=identity;
    fresh_identity_candidate_=!persisted_runtime_state_present_();
  }
  bool provisioned(){return peer_store_.present&&broker_store_.present;}
  void mark_failed(){failed=true;}
  bool persisted_runtime_state_present_() {
    ProvisionedPeerStateV2 peer;
    ProvisionedBrokerStateV2 broker;
    const bool present =
        peer_store_.load(&peer) == SimpleNvsStatus::OK &&
        broker_store_.load(&broker) == SimpleNvsStatus::OK && peer.valid() &&
        broker.valid() && peer.system_id == broker.system_id &&
        peer.node_id == broker.node_id;
    peer.clear();
    broker.clear();
    return present;
  }
bool begin_boot_session_if_needed_() {
    if (boot_session_manager_.ready()) return true;

    uint64_t last_session = 0;
    StoreStatus store_status = boot_session_store_.load(&last_session);
    if (store_status == StoreStatus::MISSING) {
      // Only a device that had no persisted product identity when this process
      // started may establish the initial zero floor. A provisioned identity
      // with a missing counter is a rollback/recovery condition and fails closed.
      if (!fresh_identity_candidate_ || !provisioned()) {
        ESP_LOGE(
            "n3w_boot_session",
            "Provisioned identity has no durable boot-session counter");
        mark_failed();
        return false;
      }
      const CoreError provision_result =
          boot_session_manager_.provision_recovery_floor(
              &boot_session_store_, 0);
      if (provision_result != CoreError::NONE) {
        ESP_LOGE(
            "n3w_boot_session",
            "Initial boot-session floor persistence failed code=%u",
            static_cast<unsigned>(provision_result));
        mark_failed();
        return false;
      }
    } else if (store_status != StoreStatus::OK) {
      ESP_LOGE(
          "n3w_boot_session",
          "Durable boot-session counter unavailable status=%u",
          static_cast<unsigned>(store_status));
      mark_failed();
      return false;
    }

    const CoreError begin_result =
        boot_session_manager_.begin(&boot_session_store_, 0);
    if (begin_result != CoreError::NONE) {
      ESP_LOGE(
          "n3w_boot_session",
          "Boot-session start failed code=%u",
          static_cast<unsigned>(begin_result));
      mark_failed();
      return false;
    }

    return true;
  }
};
int main(){
  CounterStore blank;
  ActualMethods first(blank,false);
  first.peer_store_.present=first.broker_store_.present=true;
  // Pairing is durable, but telemetry identity has not yet been requested.
  ActualMethods reboot(blank,true);
  bool failure=reboot.begin_boot_session_if_needed_();
  std::cout<<"REBOOT_AFTER_PAIRING_BEFORE_FIRST_TELEMETRY="<<(failure?"ACCEPTED":"REJECTED")<<" counter_present="<<blank.present<<" marked_failed="<<reboot.failed<<"\n";
  if(failure||blank.present||!reboot.failed)return 1;
  CounterStore normal;
  ActualMethods uninterrupted(normal,false);
  uninterrupted.peer_store_.present=uninterrupted.broker_store_.present=true;
  if(!uninterrupted.begin_boot_session_if_needed_())return 2;
  ActualMethods next(normal,true);
  if(!next.begin_boot_session_if_needed_()||normal.value!=2)return 3;
  std::cout<<"UNINTERRUPTED_FIRST_TELEMETRY_THEN_REBOOT=ACCEPTED counter=2\n";
}

```
