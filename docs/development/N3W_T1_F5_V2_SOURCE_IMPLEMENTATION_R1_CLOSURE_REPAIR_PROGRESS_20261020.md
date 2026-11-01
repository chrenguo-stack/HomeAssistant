# N3W T1 F5 V2 R1 closure repair 进展 — 2026-10-20

## 0. Gate

~~~text
TASK=N3W_T1_F5_V2_SOURCE_IMPLEMENTATION_R1_CLOSURE_REPAIR_20261020_01
RESULT=SOURCE_REPAIR_IMPLEMENTED_CI_PENDING

SOURCE_BASE_MAIN=4223f23d2579241f6568a1ba3fbbccf26b3bc3c1
SOURCE_BRANCH=feat/n3w-t1-f5-v2-source-implementation-20261019
SOURCE_PR=624

REVIEWED_HEAD_BEFORE_REPAIR=7585469cfb2e06b63013bd737a1e5a783915c2d5
SOURCE_TEST_HEAD_BEFORE_PROGRESS_ALIGNMENT=4a083d2bb8de94f87f9e5c000ee52537578cbfd5

T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
MERGE=false
R2_STARTED=false
~~~

本 gate 只修复 R1 focused closure review 发现的 3 个 blocker，不进入 R2。

## 1. C1 — production authority root itself is fresh-host residue

Fresh qualification 之前只检查：

~~~text
/var/lib/n3w-production/run.json
~~~

这无法覆盖：

~~~text
authority root 已创建
+
run.json 尚未发布
+
过程异常中断
~~~

留下的 mutation residue。

现在 explicit product residue set 同时检查：

~~~text
/var/lib/n3w-production
/var/lib/n3w-production/run.json
~~~

因此即使只有 authority root、没有 marker file，也会：

~~~text
HOST.PRODUCT_ABSENT=FAIL
STATUS=FAIL_REFLASH_REQUIRED
~~~

新增 focused regression：

~~~text
production authority root present
run.json absent
-> FAIL_REFLASH_REQUIRED
~~~

## 2. C2 — marker authority root is revalidated on read/hash/accept

原 repair 已保证 `start` 前验证 authority root：

~~~text
directory
owner=current privileged execution uid
mode=0700
not symlink
~~~

closure review 发现 STARTED 之后，`read_marker()`、`marker_sha256()` 和 `_atomic_replace()` 没有重新验证 parent authority metadata。

现在：

~~~text
read_marker()
-> validate parent authority root
-> validate marker file
-> read/validate marker

marker_sha256()
-> validate parent authority root
-> validate marker file
-> hash marker

accept_marker()
-> read_marker() parent validation
-> exact STARTED binding validation
-> _atomic_replace()
   -> parent validation
   -> marker validation
   -> temp fsync
   -> parent revalidation immediately before replace
   -> atomic replace
   -> directory fsync
~~~

新增回归覆盖：

- STARTED 后把 authority root mode 改成 0755；
- read/hash/inspect 全部 fail-closed；
- accept 也 fail-closed；
- 原 STARTED marker bytes 保持不变。

## 3. C3 — forensic evidence root symlink rejected before any resolution/mutation

原 `_ensure_root()` 顺序是：

~~~text
root.resolve()
-> root.is_symlink()
~~~

这会先跟随 symlink，使后面的 symlink test 失去意义。

现在固定为：

~~~text
absolute path without symlink resolution
-> reject root symlink
-> if existing:
     require directory
     require current uid ownership
     require mode 0700
-> if absent:
     require non-symlink directory parent
     mkdir 0700
     fsync parent
     verify owner/mode
~~~

已有 evidence root 不再被静默 `chmod 0700`；权限不正确直接 fail-closed，避免 collector 改写一个并非自己可信控制的现有目录。

新增回归覆盖：

~~~text
evidence root is symlink
-> reject
-> target directory mode unchanged
-> target directory remains empty

existing evidence root mode=0755
-> reject
-> do not chmod it
~~~

## 4. R1 boundary unchanged

本 gate 没有修改：

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
R2_STARTED=false
HOST_BASELINE_ADAPTATION_STARTED=false
F3_V2_CONTEXT_ADAPTATION_STARTED=false
PROVISION_SOURCE_MUTATION=false
F4_SOURCE_MUTATION=false
V2_ORCHESTRATOR_IMPLEMENTATION_STARTED=false
POST_REBOOT_ACCEPTANCE_IMPLEMENTATION_STARTED=false
~~~

## 5. Current stop

~~~text
R1_CLOSURE_REPAIR=IMPLEMENTED_CANDIDATE
R1_CLOSURE_REPAIR_CI=PENDING

NEXT_ONE_GATE=
N3W_T1_F5_V2_SOURCE_IMPLEMENTATION_R1_CLOSURE_REPAIR_EXACT_HEAD_CI_COMPLETION_CHECK_20261020_01

AUTO_EXECUTE_R2=false
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
MERGE=false
STOP=true
~~~
