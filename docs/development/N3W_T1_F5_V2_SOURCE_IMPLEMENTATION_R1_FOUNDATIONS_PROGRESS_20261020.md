# N3W T1 F5 V2 R1 foundations 源码实现进展 — 2026-10-20

## 0. Gate

~~~text
TASK=N3W_T1_F5_V2_SOURCE_IMPLEMENTATION_R1_FOUNDATIONS_20261019_01
STATUS=SOURCE_CANDIDATE_IMPLEMENTED_CI_PENDING

SOURCE_BASE_MAIN=4223f23d2579241f6568a1ba3fbbccf26b3bc3c1
SOURCE_BRANCH=feat/n3w-t1-f5-v2-source-implementation-20261019
SOURCE_PR=624
R1_SOURCE_CONTENT_HEAD_BEFORE_PROGRESS_ALIGNMENT=062715db7c30850d4c1e8fc88594a67ca1e09def

T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
MERGE=false
~~~

本阶段只实现工作包中冻结的 R1 foundations，不进入 HOST_BASELINE/F3/Provision/F4 业务 mutation 编排。

## 1. Added foundations

~~~text
tools/n3w_t1_production_v2_contract.py
tools/n3w_t1_ssh_transport.py
tools/n3w_t1_fresh_armbian_qualification.py
tools/n3w_t1_production_marker.py
tools/n3w_t1_failure_forensics.py
~~~

对应 focused tests：

~~~text
tests/tools/test_n3w_t1_production_v2_contract.py
tests/tools/test_n3w_t1_ssh_transport.py
tests/tools/test_n3w_t1_fresh_armbian_qualification.py
tests/tools/test_n3w_t1_production_marker.py
tests/tools/test_n3w_t1_failure_forensics.py
~~~

新增 source CI：

~~~text
.github/workflows/n3w-t1-f5-v2-source-ci.yml
~~~

## 2. Production V2 contract

新增稳定 schema：

~~~text
gh.n3w-t1-production-v2-release/1
gh.n3w-t1-production-v2-plan/1
gh.n3w-t1-production-v2-result/1
gh.n3w-t1-production-v2-run/1
gh.n3w-t1-production-v2-run-context/1
gh.n3w-t1-production-v2-forensics/1
~~~

release contract 首版冻结：

- exact source head/tree；
- Standard Fresh Armbian OS/board/arch contract；
- docker.io / docker-compose-v2 exact package versions；
- apt source policy；
- F3/F4/reboot/V2 Mac/transport artifact hashes；
- minimum post-peak free capacity；
- public evidence field allowlist and sensitive-name rejection。

F3 run context 明确位于 immutable payload 之外，且 action 只允许 `F3_DEPLOY`。

## 3. SSH transport reuse

R1 选择性复用了 archived V1 PR #612 已复核的 SSH transport 和测试：

~~~text
SOURCE_REFERENCE=9048dd7c6b48c0620471919c0cf96c96bdab71f1
SSH_SOURCE_BLOB=dec4c9159195e2008094d94fef3fc76c4b977e46
SSH_TEST_BLOB=2206f47310949fbe78d743762319e2cf95efafe4
~~~

保留：

- exact known_hosts / host-key binding；
- one password prompt per connection epoch；
- ControlMaster connection reuse；
- child command禁止重新认证 fallback；
- private local control socket/work root；
- reboot 前后两个独立 authentication epoch；
- explicit session-close proof；
- no password persistence / no new management key。

未恢复 V1 top-level production authority/runtime recovery 状态机。

## 4. Fresh Armbian qualification

qualification 直接实现 V2 三态：

~~~text
PASS
FAIL_REFLASH_REQUIRED
STOP_UNAVAILABLE
~~~

只读取并判断：

~~~text
HOST.OS_ARCH
HOST.ARMBIAN_IDENTITY
HOST.FIRSTBOOT
HOST.SSH_TRUST
HOST.PRIVILEGE
HOST.NETWORK_TIME
HOST.STORAGE
HOST.APT_SOURCE
HOST.DOCKER_ABSENT
HOST.PRODUCT_ABSENT
~~~

Standard Fresh Armbian baseline保持与已接受 F2 证据一致：

~~~text
ID=ubuntu
VERSION_ID=26.04
VERSION_CODENAME=resolute
PRETTY_NAME=Armbian OS 26.05.0 resolute
BOARD=S912-Phicomm-T1
BOARD_NAME=Aml.S912
VERSION=26.05.0
BRANCH=current
ARCH=arm64
IMAGE_TYPE=rebuild
~~~

probe 本身只使用 read-only systemctl/ip/timedatectl/dpkg-query/dpkg/文件读取/文件存在性/磁盘容量/DNS 查询。

SSH/只读 probe 证据不可取得时返回 `STOP_UNAVAILABLE`，不自动标记 reflash。
已经观察到 OS/Docker/product 等 fresh-contract 偏差时才返回 `FAIL_REFLASH_REQUIRED`。

## 5. Minimal durable marker

target durable marker仍固定：

~~~text
/var/lib/n3w-production/run.json
~~~

首版命令面只有：

~~~text
inspect
start
accept
~~~

明确不存在：

~~~text
resume
repair
clear
reset
force
reopen
~~~

`start` 使用 same-filesystem temp + fsync + no-overwrite hard-link create + directory fsync。

`accept` 只接受 exact STARTED binding，使用 atomic replace + fsync，并最后设置：

~~~text
state=ACCEPTED
T1_PRODUCTION_READY=true
~~~

duplicate start、binding mismatch、second accept 都 fail-closed。

## 6. Failure forensics

实现顺序基础件：

~~~text
freeze_failure
-> collect_snapshot
-> build_manifest
-> verify_manifest
-> reflash_disposition only after session_closed=true
~~~

固定 evidence：

~~~text
failure-summary.json
forensic-snapshot.json
evidence-manifest.json
~~~

collector本身不包含 SSH/服务启停/删除/安装等 target mutation command。

probe 不可用时只记录：

~~~text
status=UNAVAILABLE
reason=<exception class>
~~~

manifest 仍可 `FORENSIC_SNAPSHOT_COMPLETE=true`。

原始 failure-summary 采用 no-overwrite private atomic write；后续异常不能覆盖原始失败事实。

## 7. R1 source boundary

本阶段没有修改：

~~~text
tools/n3w_t1_fresh_host_baseline.py
tools/n3w_t1_fresh_product_bootstrap.py
tools/n3w_t1_fresh_product_staging_host.py
tools/n3w_t1_device_provisioning_host.py
tools/n3w_t1_f4_activation_host.py
tools/n3w_t1_f4_reboot_authority.py
tools/n3w_t1_f4_reboot_verify.py
~~~

因此：

~~~text
HOST_BASELINE_ADAPTATION_STARTED=false
F3_V2_CONTEXT_ADAPTATION_STARTED=false
PROVISION_SOURCE_MUTATION=false
F4_SOURCE_MUTATION=false
V2_ORCHESTRATOR_IMPLEMENTATION_STARTED=false
POST_REBOOT_ACCEPTANCE_IMPLEMENTATION_STARTED=false
~~~

## 8. CI boundary

新增 dedicated source gate：

~~~text
N3W T1 F5 V2 source CI / r1-foundations
~~~

负责：

- Python compile；
- 5 组 R1 focused tests；
- R1 forbidden V1-authority/recovery boundary；
- T1/board false safety output。

当前 exact PR-head CI 仍需 fresh completion check，因此本记录不宣称 R1 CLOSED_PASS。

## 9. Current stop

~~~text
R1_SOURCE_IMPLEMENTATION=IMPLEMENTED_CANDIDATE
R1_CI=PENDING

NEXT_ONE_GATE=
N3W_T1_F5_V2_SOURCE_IMPLEMENTATION_R1_EXACT_HEAD_CI_COMPLETION_CHECK_20261020_01

AUTO_EXECUTE_R2=false
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
MERGE=false
STOP=true
~~~
