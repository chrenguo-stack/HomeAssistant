# N3-W T1 Broker 8883 ingress guard source package

Status: `SOURCE_CANDIDATE_ONLY`

本目录保存 T1 Broker TCP/8883 动态入口保护所需的部署文件。它不是 live 执行授权，不能因为文件已进入 GitHub 就直接修改生产 T1。

## Source-to-host mapping

```text
tools/n3w_broker_ingress_guard.py
→ /usr/local/sbin/n3w-broker-ingress-guard
mode=0755
owner=root:root

infra/n3w-t1/systemd/n3wfc4-broker-ingress-guard.service
→ /etc/systemd/system/n3wfc4-broker-ingress-guard.service
mode=0644
owner=root:root

infra/n3w-t1/systemd/n3wfc4-broker-activation.service
→ /etc/systemd/system/n3wfc4-broker-activation.service
mode=0644
owner=root:root

infra/n3w-t1/NetworkManager/dispatcher.d/90-n3wfc4-broker-ingress-guard
→ /etc/NetworkManager/dispatcher.d/90-n3wfc4-broker-ingress-guard
mode=0755
owner=root:root

infra/n3w-t1/broker-activation.env.example
→ operator-created /etc/n3wfc4/broker-activation.env
mode=0600
owner=root:root
```

`broker-activation.env` 只允许保存 Compose 文件路径、env-file 路径和固定 Compose project identity；不得保存 Broker、Manager、TLS 或其他生产凭据。

## Required rendered-Compose contract

任何 live 安装前，目标 T1 的真实 rendered Compose 必须先通过：

```text
tools/n3w_pairing_deployment_gate.py
```

至少证明：

```text
Manager network_mode=host
Manager ports absent
Compose project name=n3wfc4
Broker restart=no
Broker host publication=0.0.0.0:8883 -> 8883/tcp
host TCP/8883 publication owner=Broker only
Broker networks=n3wfc4-private,n3wfc4-services
effective network names exact-match
Manager loopback endpoint is IPv4 loopback
```

客户 LAN IPv4 或 subnet 不得进入 Compose、systemd unit、dispatcher 或 activation env。Broker activation 的 Compose project identity 必须显式冻结为 `n3wfc4`；不得依赖 Compose 文件所在目录名推导 project name。

## Runtime ownership

规则生命周期：

```text
Docker
→ n3wfc4-broker-ingress-guard.service
→ n3wfc4-broker-activation.service
```

NetworkManager dispatcher 只负责在 `eth0` 的相关事件发生后重新调用 guard。dispatcher 事件携带的地址不是 trusted-subnet authority；guard 每次重新读取 NetworkManager 当前状态。

guard 只拥有：

```text
DOCKER-USER 中 comment=n3wfc4-broker-ingress-v1 的 exact anchor
N3WFC4-BROKER-INGRESS chain
```

不得 flush 或重写其他 Docker/管理员 firewall state。

## Fail-closed

```text
unique current eth0 IPv4 subnet
→ allow eth0 + current subnet
→ terminal DROP

no valid subnet / disconnected / multiple different subnets
→ terminal DROP only

firewall apply/readback failure
→ error
→ Broker activation owner must not continue
```

## Live deployment boundary

后续 live gate 必须先取得 fresh read-only baseline、真实路径、hash、rollback snapshot 和 explicit authorization。

安装时不能先启用 wildcard Broker 再补 guard。必须先证明 fail-closed guard 已存在，再进入 Broker recreate/activation。

rollback 也必须先停止或撤销 wildcard Broker publication，证明 host TCP/8883 wildcard 已关闭，然后才能删除项目自有 anchor/chain。若 wildcard 是否关闭无法证明，保留 DROP guard。
