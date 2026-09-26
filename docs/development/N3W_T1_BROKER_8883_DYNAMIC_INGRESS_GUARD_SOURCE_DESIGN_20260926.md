# N3-W T1 Broker 8883 Dynamic Ingress Guard — Source Design

Status: `SOURCE_DESIGN_CLOSED_PASS`  
Date: 2026-09-26  
Gate: `N3W_T1_BROKER_8883_DYNAMIC_INGRESS_GUARD_SOURCE_DESIGN_20260926_01`

> 本文件只冻结源码/部署设计，不授权任何 T1、防火墙、Compose、Broker、Manager 或板卡修改。  
> 客户现场 IPv4 地址、子网、私有路径和凭据不得写入公开仓库。

## 1. 目标与边界

本设计只解决一个问题：

> Broker 改为显式 `0.0.0.0:8883` Docker publication 后，只允许当前 T1 有线可信局域网进入 TCP/8883；换 DHCP、换路由器或换网段后自动更新；无法确定可信网段时默认关闭外部入口。

本门不处理：

- B2：稳定 T1 hostname / TLS identity 生命周期；
- B3：已配对节点中历史 literal Broker IP 的迁移；
- PR #474 物理验证；
- Broker/Manager/板卡 live mutation。

冻结前提：

```text
NETWORK_AUTHORITY=NetworkManager
WIRED_INTERFACE=eth0
WIRED_ADDRESS_MODE=DHCP
DOCKER_FIREWALL_BACKEND=iptables
DOCKER_FILTER_HOOK=DOCKER-USER
BROKER_TLS_PORT=8883
CUSTOM_CHAIN=N3WFC4-BROKER-INGRESS
STATIC_CUSTOMER_IP_OR_SUBNET=false
UNKNOWN_OR_AMBIGUOUS_SUBNET=FAIL_CLOSED
```

## 2. 总体结构

最小结构固定为三部分：

```text
NetworkManager 当前 eth0 IPv4 状态
        │
        ▼
n3wfc4-broker-ingress-guard helper
        │
        ├─ 计算当前唯一可信 IPv4 subnet
        └─ 原子刷新本项目自有 iptables chain
        │
        ▼
DOCKER-USER
        │
        └─ original destination TCP/8883
              │
              ▼
        N3WFC4-BROKER-INGRESS
              ├─ eth0 + 当前可信 subnet → RETURN
              └─ 其他来源                → DROP
```

Docker 自动维护的 chain 不修改、不 flush。

## 3. 为什么必须按 original destination 识别 8883

Docker published port 的包到达 `DOCKER-USER` 时已经完成 DNAT，因此此时普通 destination port 可能已经变成容器内部地址/端口。

因此锚点必须按 conntrack 中“连接最初要访问的端口”识别 TCP/8883，设计语义冻结为：

```text
protocol=tcp
conntrack_direction=ORIGINAL
conntrack_original_destination_port=8883
jump=N3WFC4-BROKER-INGRESS
```

等价目标规则形态：

```text
DOCKER-USER:
  match tcp
  match conntrack ORIGINAL direction
  match original destination port 8883
  jump N3WFC4-BROKER-INGRESS
```

锚点本身不得限制为 `-i eth0`。原因是 Broker publication 是 IPv4 wildcard；如果锚点只匹配 eth0，其他接口上的 8883 会绕过本 guard。

自有 chain 再决定哪些来源允许：

```text
N3WFC4-BROKER-INGRESS:
  if input interface == eth0
     and source is in current trusted subnet:
       RETURN
  else:
       DROP
```

允许动作用 `RETURN`，不用 `ACCEPT`。这样允许流量回到 `DOCKER-USER` 后，仍继续受其他已有管理员规则约束，不抢占别人的 firewall policy。

## 4. trusted subnet 的唯一 authority

可信网段只来自“执行当下 NetworkManager 对 eth0 的当前状态”。

不得使用：

- dispatcher 事件里缓存的旧地址；
- Compose 常量；
- 环境变量中的客户网段；
- 当前测试现场地址；
- 上一次运行持久化下来的 subnet；
- 路由表猜测出的其他接口网络。

helper 每次执行都重新读取 NetworkManager 当前 eth0 状态。

### 4.1 解析规则

输入为当前 eth0 的 IPv4 address/prefix 集合。

每个候选地址必须：

- 是有效 IPv4 unicast；
- 不是 unspecified；
- 不是 loopback；
- 不是 multicast；
- 不是 link-local；
- prefix 不得为 `/0`。

候选使用标准 IPv4 network 归一化，例如：

```text
address/prefix
→ ip_interface
→ .network
```

判定：

```text
0 个唯一有效 network
→ FAIL_CLOSED

1 个唯一有效 network
→ TRUSTED_SUBNET=<runtime value>

>1 个不同 network
→ FAIL_CLOSED
```

如果 eth0 有多个 IPv4 地址，但归一化后都属于同一个 network，仍视为一个唯一可信 subnet。

不要求网段必须是 RFC1918 私网。产品不能把“某一种客户 LAN 地址范围”写死为设计前提。

### 4.2 运行时值不持久化为产品配置

当前可信 subnet 只用于生成当前 firewall rules。

允许保存 public-safe 诊断信息，例如：

- prefix length；
- subnet 的 SHA-256；
- 候选数量；
- 本次 generation/reason。

不得把原始客户 subnet 写入公开日志、GitHub 或长期产品配置作为下一次启动 authority。

## 5. fail-closed 规则

fail-closed 分为两类。

### 5.1 网络事实正常但无法唯一确定 subnet

例如：

- eth0 尚未取得 IPv4；
- DHCP 正在切换；
- eth0 当前同时属于两个不同 IPv4 network；
- 只得到无效/不可信候选。

此时 helper 必须成功把自有 chain 收敛为：

```text
N3WFC4-BROKER-INGRESS:
  DROP
```

这是预期的安全状态，不应退回“保留旧 subnet 继续放行”。

### 5.2 firewall 自身无法安全写入或验证

例如：

- `DOCKER-USER` 不存在；
- 规则 transaction 失败；
- 锚点无法唯一识别；
- apply 后 read-back 与目标不一致。

此时不得把入口改成 broad allow。

后续 live gate 必须把这类情况视为 unsafe，并保持/恢复“Broker wildcard 不可对外工作”的状态。若无法证明安全 guard 仍生效，则停止 Broker wildcard 路径并进入人工恢复，不允许带未知 firewall 状态继续运行。

## 6. 幂等与原子规则生命周期

本项目只拥有：

```text
CUSTOM_CHAIN=N3WFC4-BROKER-INGRESS
ANCHOR_COMMENT=n3wfc4-broker-ingress-v1
```

不得把 `DOCKER-USER` 或整个 filter table 当作本项目所有。

### 6.1 稳定锚点

最终必须满足：

```text
DOCKER_USER_OWNED_ANCHOR_COUNT=1
DOCKER_USER_OWNED_ANCHOR_POSITION=1
```

锚点只匹配 original-direction TCP/8883，并跳转到自有 chain。

如果历史上存在多个同 comment、同语义的本项目锚点，repair 只允许清理本项目自己能精确识别的锚点，再原子收敛为一个；不得删除其他规则。

### 6.2 自有 chain 刷新

routine DHCP/network refresh 不重建整个 `DOCKER-USER`。

只原子替换 `N3WFC4-BROKER-INGRESS` 内容：

正常唯一 subnet：

```text
allow eth0 + trusted subnet → RETURN
terminal DROP
```

无/歧义 subnet：

```text
terminal DROP
```

实现阶段必须使用单次可验证的 iptables transaction，例如经过目标主机验证的：

```text
iptables-restore --noflush
```

或等强度机制。

禁止用一串“先删旧规则、再逐条加新规则”的离散命令制造中间 broad-open 窗口。

### 6.3 明确禁止

```text
flush DOCKER-USER
flush filter table
flush Docker-owned chain
delete foreign rule
append duplicate anchor every refresh
fall back to ACCEPT on error
```

## 7. NetworkManager 刷新机制

NetworkManager dispatcher 只负责“通知重新计算”，不负责提供 subnet authority。

dispatcher 关注 eth0 的这些变化：

```text
pre-up
up
dhcp4-change
reapply
pre-down
down
```

事件处理流程：

```text
NetworkManager event
→ 仅判断 interface/action 是否相关
→ 同步启动 bounded guard refresh
→ guard helper 再读取当前 NetworkManager eth0 状态
→ 原子应用规则
```

dispatcher 中的地址环境变量不得直接生成 firewall rule。

这样即使 NetworkManager dispatcher 队列里存在较旧事件，真正执行时仍以“此刻”的 eth0 状态为准。

refresh 必须有明确超时，不能无限占住 NetworkManager dispatcher。

## 8. 开机与 Docker 生命周期顺序

不能依赖“Docker 先把 wildcard Broker 自动拉起来，guard 稍后再补”。

冻结顺序：

```text
docker.service active
→ ingress-guard oneshot
→ Broker activation
```

### 8.1 guard service

`n3wfc4-broker-ingress-guard.service`：

- `After=docker.service`；
- Docker 不可用时失败；
- 不要求 `network-online.target`；
- 网络未就绪时也必须能够安装 drop-only guard；
- 每次运行重新读取 NetworkManager 当前状态；
- oneshot 结束后不依赖内存保存客户 subnet。

guard 在 Docker service 启动/重启后必须重新运行。

### 8.2 Broker activation

后续 source repair 必须建立一个明确的 Broker 启动 owner，使 wildcard Broker 只能在 guard 成功后启动。

启动依赖：

```text
Requires=docker.service
Requires=n3wfc4-broker-ingress-guard.service
After=docker.service
After=n3wfc4-broker-ingress-guard.service
```

Broker container 不得使用会绕过 systemd guard 顺序、在 Docker daemon 启动时自行恢复 wildcard publication 的 restart policy。

冻结要求：

```text
BROKER_DOCKER_RESTART_POLICY=no
```

由 systemd activation owner 在 boot / Docker service restart 路径中按“guard → Broker”顺序恢复。

NetworkManager 可以早于或晚于 Docker：

- 如果网络先好：guard 直接得到唯一 subnet；
- 如果 Docker 先好：guard 先装 drop-only，Broker 可启动但 LAN 入口关闭；
- 后续 NetworkManager `up/dhcp4-change` 再刷新成允许当前 subnet。

因此不需要为了取得 DHCP 地址而阻塞 Docker/Broker 启动。

## 9. 与 Manager loopback 的边界

Manager 继续：

```text
network_mode=host
ports absent
TLS server name=armbian
```

本 guard 保护 Docker forwarded published-port ingress，不把 Manager 本机 loopback 连接当成 trusted-LAN 判定来源。

但源码设计不能假定 host-local path 一定不受实际 Docker/netfilter 实现影响。

因此 live acceptance 必须继续从 exact Manager runtime namespace 做：

```text
getaddrinfo(armbian)
TCP connect
TLS server-name validation
```

只有 live probe 才能证明 Manager 本机连续性。

## 10. 额外 source contract：8883 publication 唯一归 Broker

guard 会按 original destination TCP/8883 保护整个 Docker forwarding path。

因此 source repair 必须增加静态 guard：

> 在 rendered Compose 中，除 Broker 这一个已冻结 publication 外，任何其他 service 都不得发布或用 port range 覆盖 host TCP/8883。

这不是重开 PR #475 R3；它是 ingress-guard 自身为了避免误拦其他 Docker service 所需要的新前置条件。

PR #475 已经证明 Broker 自身只存在一个显式 `0.0.0.0:8883 -> 8883/tcp` publication；本门后继 source repair 再补“其他 service 不得占用 8883”的全 Compose 检查。

## 11. Rollback

rollback 必须先关 wildcard exposure，再拆 guard，顺序不可反。

冻结顺序：

```text
1. fresh snapshot / hashes
2. stop Broker wildcard path
   或恢复已验证的 prechange non-wildcard publication
3. prove host no longer has live wildcard TCP/8883 publication
4. disable Broker activation owner / NetworkManager dispatcher
5. remove exact owned DOCKER-USER anchor
6. remove exact owned custom chain
7. verify unrelated DOCKER-USER/Docker/firewall rules unchanged
```

如果第 3 步不能证明 wildcard 已关闭：

```text
KEEP_FAIL_CLOSED_GUARD=true
ROLLBACK_RESULT=ROLLBACK_INCOMPLETE
```

不得为了“回滚干净”而先删掉 DROP guard。

## 12. 可观测性

helper 每次运行输出结构化、secret-safe 状态，建议 schema：

```text
gh.n3w-broker-ingress-guard/1
```

至少包含：

```text
status=PASS|FAIL_CLOSED|ERROR
interface=eth0
candidate_network_count=
trusted_network_prefix_length=
trusted_network_sha256=
anchor_count=
anchor_position=
rule_generation=
reason=
raw_customer_subnet_in_public_output=false
```

私有 live evidence 可另外保存：

- `iptables-save` exact rules；
- packet/rule counters；
- NetworkManager exact current state；
- rendered Compose/runtime mapping。

默认不增加逐包 firewall 日志，避免噪声和客户 LAN 信息泄露。

## 13. Source / host regression 计划

后继 source repair 至少覆盖：

### 13.1 NetworkManager 状态解析

- connected + 单一 IPv4 subnet → allow；
- 多个 IPv4 address、同一归一化 subnet → allow；
- 0 个有效 subnet → drop-only；
- 两个不同有效 subnet → drop-only；
- link-local-only → drop-only；
- malformed address/prefix → drop-only；
- `/0` → drop-only。

### 13.2 firewall 语义

断言：

- hook 是 `DOCKER-USER`；
- 使用 conntrack original destination TCP/8883；
- 限定 `ctdir=ORIGINAL`；
- anchor 不限 `-i eth0`；
- 自有 chain 的 allow 同时要求 eth0 + trusted subnet；
- allow action 是 `RETURN`；
- chain 最后一条是 `DROP`；
- 不出现 broad `ACCEPT`；
- 不 flush `DOCKER-USER`/filter/Docker-owned chains。

### 13.3 幂等 / transaction

- 同一状态重复 refresh，最终规则完全一致；
- DHCP subnet A → B，只保留 B；
- A → unknown，变成 drop-only；
- unknown → B，恢复 B；
- exact owned anchor 最终始终一个；
- foreign DOCKER-USER rules 顺序/内容保持；
- transaction failure 不产生 broad-open 中间状态。

### 13.4 NetworkManager dispatcher

- 非 eth0 不触发；
- 不相关 action 不触发；
- dispatcher 不把 event address 当 subnet authority；
- helper 每次 fresh read current state；
- 调用 bounded，不无限等待。

### 13.5 boot / deployment

静态检查：

- Docker 在 guard 前；
- guard 在 Broker activation 前；
- Broker Docker restart policy 为 `no`；
- Broker 仍是唯一覆盖 host TCP/8883 的 Compose service；
- PR #475 的 explicit `0.0.0.0:8883`、双网络、Manager host-network/no-ports 合同继续通过。

## 14. 后续 live acceptance oracle

本门不执行以下测试，只提前冻结验收标准。

### A. prechange

证明并保存：

- exact runtime/Compose authority；
- NetworkManager eth0 当前状态；
- `iptables-save`；
- Docker runtime mapping；
- Broker/Manager prestate；
- fresh rollback snapshot/hash。

### B. guard 安装，Broker 仍不做 wildcard live activation

要求：

```text
DOCKER_USER_OWNED_ANCHOR_COUNT=1
CUSTOM_CHAIN_PRESENT=true
CUSTOM_CHAIN_TERMINAL_DROP=true
UNRELATED_RULES_UNCHANGED=true
```

### C. 后续授权后启用 wildcard Broker

证明 runtime：

```text
BROKER_RUNTIME_PUBLICATION=0.0.0.0:8883/tcp
BROKER_RUNTIME_NETWORKS=n3wfc4-private,n3wfc4-services
```

### D. Manager 本机连续性

从 exact Manager network namespace：

```text
armbian resolves as expected
TCP 8883=PASS
TLS server-name armbian=PASS
```

### E. trusted-LAN 正向入口

从当前可信 LAN 的独立客户端：

```text
TCP/TLS 8883=PASS
ALLOW_RULE_COUNTER_INCREASES=true
```

### F. 非可信来源负向入口

必须从一个真正不满足 `eth0 + trusted subnet` 的独立来源发起。

要求：

```text
TCP_8883=BLOCKED
DEFAULT_DROP_COUNTER_INCREASES=true
```

如果现场没有可构造的独立负向来源：

```text
INGRESS_NEGATIVE_ACCEPTANCE=NOT_PROVEN
```

不能用“没有日志”冒充 PASS。

### G. DHCP / 换网段

无需修改产品配置：

```text
old subnet disappears
no/ambiguous transition → drop-only
new unique subnet → rule refresh
anchor count remains 1
new trusted LAN TCP/TLS=PASS
```

### H. reboot / Docker restart

验证：

```text
guard precedes Broker activation
no broad-open startup window proven by ordering/state evidence
anchor count=1
no duplicate rules
Broker runtime mapping preserved
Broker dual networks preserved
Manager TCP+TLS preserved
```

B2 hostname 发布/解析、B3 已配对节点迁移和板卡 telemetry 不属于本 gate 的 live acceptance。

## 15. 拟议 source repair 文件边界

后继 gate 可采用下面的最小文件集合；具体路径在 source repair 开始时再 fresh 检查：

```text
tools/n3w_broker_ingress_guard.py
tests/tools/test_n3w_broker_ingress_guard.py
systemd/n3wfc4-broker-ingress-guard.service
systemd/n3wfc4-broker-activation.service
NetworkManager/dispatcher.d/<bounded project dispatcher>
tools/n3w_pairing_deployment_gate.py
tests/tools/test_n3w_pairing_deployment_gate.py
focused CI workflow
```

仓库当前没有可复用的 N3-W systemd / NetworkManager dispatcher 部署约定，因此后继 source repair 必须保持文件集合小，并为新增部署文件提供静态 regression；不得引入新的通用部署框架。

## 16. 本门结论

```text
DESIGN_AUTHORITY=this document
DOCKER_FILTER_HOOK=DOCKER-USER
CUSTOM_CHAIN=N3WFC4-BROKER-INGRESS
PACKET_MATCH=conntrack ORIGINAL original-destination TCP/8883
TRUSTED_SUBNET_AUTHORITY=NetworkManager current eth0 connected IPv4 subnet
NETWORK_CHANGE_REFRESH_AUTHORITY=NetworkManager dispatcher triggers fresh current-state reread
BOOT_ORDERING=Docker -> fail-closed guard -> Broker activation
BROKER_DOCKER_RESTART_POLICY=no
FAIL_CLOSED_BEHAVIOR=zero/ambiguous subnet => drop-only; unsafe firewall state => no broad-open continuation
RULE_IDEMPOTENCE=one owned anchor + atomically replaced owned chain
ROLLBACK_MODEL=close wildcard first, remove owned guard last
SOURCE_TEST_PLAN=DEFINED
LIVE_ACCEPTANCE_PLAN=DEFINED

LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
PR474_MERGE=false
PR475_MERGE=false

SOURCE_DESIGN_RESULT=PASS
NEXT_ROUTE=N3W_T1_BROKER_8883_DYNAMIC_INGRESS_GUARD_SOURCE_REPAIR_20260926_01
AUTO_EXECUTE_NEXT_GATE=false
STOP=true
```
