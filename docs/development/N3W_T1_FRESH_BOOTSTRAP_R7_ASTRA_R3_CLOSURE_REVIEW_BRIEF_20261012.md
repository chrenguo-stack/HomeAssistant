# N3-W T1 fresh bootstrap R7 — Astra R3 focused closure review brief（2026-10-12）

## 1. Mission

Perform a narrow independent closure review after the Astra R2 BLOCK result and the subsequent F5/D1/A8 repairs.

This review must answer only whether the project may proceed from source-review closure to:

~~~text
replacement exact artifact binding
→ bounded cleanup plan for retained R3 payload
→ real-T1 read-only baseline / transport / capacity preflight
~~~

This review does NOT authorize a live apply.

~~~text
READ_ONLY_REVIEW=true
T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
PRODUCTION_SERVICE_START=false
MERGE=false
LIVE_AUTHORIZATION_GRANTED=false
~~~

## 2. Exact authority

~~~text
REPOSITORY=chrenguo-stack/HomeAssistant
PR=541
BRANCH=plan/n3w-t1-full-fresh-install-from-zero-20261010
PR_STATE=OPEN_DRAFT

PRODUCT_SOURCE_HEAD=41d05b99813ae5ea3887b4f2b80b75164f35dda4
PR_HEAD_AT_BRIEF=7ebceebe6f52310b60a0e1adf0e9486a8968f575
~~~

The PR HEAD includes documentation-only commits after the product source. The product execution authority remains PRODUCT_SOURCE_HEAD.

Previous review chain:

~~~text
ASTRA_R1_SOURCE=c263b9df6bac900332d27a50a66dd603d7d5e1e4
ASTRA_R1_RESULT=BLOCK
ASTRA_R1_BLOCKERS=F1,F2,F3,F4,F5,F6

ASTRA_R2_SOURCE=dec88fdc19daf50185d09acf4a38db8c18816ef2
ASTRA_R2_RESULT=BLOCK
ASTRA_R2_CLOSED=F1,F2,F3,F4,F6
ASTRA_R2_OPEN=F5
ASTRA_R2_NEW_BLOCKER=D1_POSTCHECK_STATE_OWNER_MISMATCH
ASTRA_R2_A8=OPEN_NONBLOCKER
~~~

Primary files:

~~~text
tools/n3w_t1_fresh_product_staging_host.py
tools/n3w_t1_fresh_product_bootstrap.py
host/greenhouse-manager/src/greenhouse_manager/bootstrap/fresh_installer.py
host/greenhouse-manager/src/greenhouse_manager/bootstrap/fresh_product_state.py
.github/workflows/n3w-t1-fresh-bootstrap-deployable-payload-ci.yml
tests/tools/test_n3w_t1_fresh_product_staging_host.py
tests/tools/test_n3w_t1_fresh_product_bootstrap.py
docs/development/N3W_T1_FRESH_BOOTSTRAP_R6_ASTRA_R2_BLOCKERS_SOURCE_REPAIR_PROGRESS_20261012.md
docs/development/N3W_CURRENT_STATE.md
docs/development/N3W_CURRENT_STATE_INDEX.md
docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
~~~

## 3. CI state to fresh-rebind

Product-source commit itself:

~~~text
HEAD=41d05b99813ae5ea3887b4f2b80b75164f35dda4
TOTAL=25
PASS=23
CANCELLED=2
FAIL=0
~~~

The two cancelled workflows were concurrency-cancelled after the next docs-only commit started new runs:

~~~text
C-07 node retirement CI
N3W T1 HA bootstrap isolated CI
~~~

Current PR HEAD:

~~~text
HEAD=7ebceebe6f52310b60a0e1adf0e9486a8968f575
TOTAL=25
PASS=25
FAIL=0
IN_PROGRESS=0
QUEUED=0
~~~

R3 must independently fresh-rebind CI and confirm that the two previously cancelled workflows passed on the current docs-only PR HEAD without product-source changes.

Do not interpret concurrency cancellation as product failure, but do not silently ignore it either.

## 4. Current authorization state

~~~text
_03=CLAIMED_CONSUMED_NO_REPLAY
_04=SUPERSEDED_UNGRANTED
_05=SUPERSEDED_UNGRANTED
_06=SUPERSEDED_UNGRANTED
_07=N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_LIVE_APPLY_20261012_07

_07_GRANTED=false
_07_CLAIMED=false
_07_CONSUMED=false
~~~

R3 must not authorize _07.

## 5. Closure item F5 — actual image-store root / capacity authority

### R2 blocker

The prior host preflight guessed:

~~~text
DockerRootDir/containerd
~~~

and silently fell back to DockerRootDir if that directory did not exist. That could miss an external containerd root such as /var/lib/containerd and allow a one-shot apply with insufficient actual image-store space.

### Current repair

The host wrapper now resolves an explicit image-store backend:

~~~text
classic
external containerd
embedded containerd
~~~

For classic:

~~~text
image_store_root = DockerRootDir
source = docker_root
~~~

For external containerd:

~~~text
read running dockerd argv
read /etc/docker/daemon.json when present
read running containerd argv
read effective containerd config when present

resolve containerd root from:
  --root / -r
  else config root
  else containerd documented default /var/lib/containerd

resolve containerd socket from:
  process argv
  else config grpc.address
  else /run/containerd/containerd.sock

resolve Docker containerd socket from:
  dockerd --containerd
  else daemon config
  else /run/containerd/containerd.sock

require realpath(Docker socket) == realpath(containerd socket)
~~~

For embedded containerd:

~~~text
image_store_root = DockerRootDir/containerd/daemon
source = embedded_containerd
~~~

Fail-closed conditions include:

~~~text
containerd service not running
containerd socket mismatch
invalid config
unresolved image-store root
unrecognized image-store authority
different staging / Docker / image-store filesystems
non-positive free-space readings
~~~

Capacity authority now uses the minimum free bytes across:

~~~text
/var/tmp
DockerRootDir
actual image_store_root
~~~

and then applies the conservative:

~~~text
extracted payload
+ content-store estimate
+ unpacked snapshot estimate
+ 5 GiB post-peak reserve
~~~

### R3 questions

Independently verify:

1. no path still silently falls back from unknown external containerd root to DockerRootDir;
2. external containerd process/config precedence is correct enough for the supported T1 target;
3. Docker and the probed containerd instance are actually bound by socket identity;
4. embedded-containerd handling is not confused with external containerd;
5. capacity admission uses the actual image-store free space;
6. inability to prove authority causes preclaim STOP.

Required classification:

~~~text
F5=CLOSED | OPEN_BLOCKER | OPEN_NONBLOCKER
~~~

If OPEN, cite exact code and give the concrete false-PASS/false-FAIL path.

## 6. Closure item D1 — stopped postcheck state-owner mismatch

### R2 blocker

Fresh staging changes Manager and N3W state ownership to runtime UID/GID 999.

The old stopped postcheck then ran audit_fresh_state() in a root container, while fresh_product_state requires ownership to equal the caller UID. Therefore a fully successful install would fail at postcheck with manager_root_owner_invalid and consume the authorization.

### Current repair

The stopped postcheck is split into two isolated read-only audit containers.

State audit:

~~~text
user=999:999
network=none
direct bind:
  /var/lib/greenhouse-manager/manager -> /manager readonly
  /var/lib/greenhouse-manager/n3w -> /n3w readonly
audit_fresh_state(/manager, /n3w)
~~~

The child directories are mounted directly so UID 999 does not need to traverse the root-owned parent /var/lib/greenhouse-manager.

Root audit remains separate for:

~~~text
/var/lib/greenhouse-manager/identity -> /identity readonly
/var/lib/n3wfc4-broker -> /broker readonly
/opt/greenhouse-secrets -> /secrets readonly

verify_initialization()
audit_fresh_dynsec_document()
verify_clean_service_credential_bundle()
~~~

The exact deployable-payload workflow now additionally runs the exact Manager image as UID 999 against the staged manager/n3w state and requires node_credential_count=0.

A contract regression also forces a postcheck failure and requires:

~~~text
failed_stage=postcheck
cleanup_result=PASS
cleanup_called=true
~~~

### R3 questions

Verify:

1. audit_fresh_state now observes the same effective UID/GID that owns the state;
2. direct child mounts remove the root-parent traversal issue;
3. root-only identity / broker / credential checks remain appropriately privileged and read-only;
4. no remaining stopped_postcheck path audits UID-999-owned Manager/N3W state as root;
5. postcheck failure still enters transaction cleanup and remains consumed/no-replay.

Required classification:

~~~text
D1=CLOSED | OPEN_BLOCKER | OPEN_NONBLOCKER
~~~

## 7. Closure item A8 — artifact download timeout fallback

### R2 finding

The repository fallback existed, but gh run download timeout raised subprocess.TimeoutExpired and bypassed the fallback.

### Current repair

The initial gh run download stage now falls into the same fallback on:

~~~text
FreshHostTransportError
OSError
subprocess.TimeoutExpired
~~~

The fallback remains:

~~~text
GitHub artifact metadata binding
→ REST artifact endpoint
→ capture temporary HTTPS redirect
→ blob download without forwarding GitHub bearer token
→ whole ZIP SHA256 verification
→ safe exact six-file extraction
→ wrapper/archive/manifest binding
~~~

A regression injects a gh TimeoutExpired and requires the fallback to complete only after ZIP integrity and exact outer file set validation.

### R3 questions

Verify that:

1. timeout now reaches the same integrity-bound fallback;
2. the fallback remains pre-T1 and cannot consume authorization;
3. source/artifact identity is not weakened;
4. no new secret-bearing token propagation to the blob host was introduced.

Required classification:

~~~text
A8=CLOSED | OPEN_BLOCKER | OPEN_NONBLOCKER
~~~

A8 may remain nonblocking only if any residual issue still occurs strictly before T1 mutation/claim and cannot weaken identity binding.

## 8. Downstream source-blocker re-scan

Re-scan current exact product source only for source-visible blockers that would still make the next prelive stage unsafe.

Focus on:

~~~text
host transport
capacity admission
payload transfer ordering
authorization claim ordering
all three image loads
identity/state/broker construction
DynSec
runtime staging
commit
stopped postcheck
cleanup after postcheck failure
durable no-replay ledger
no production start
no board access
~~~

Do not reopen F1/F2/F3/F4/F6 unless the new F5/D1/A8 repair actually regressed them.

Required classification:

~~~text
DOWNSTREAM_SOURCE_BLOCKER=YES | NO
~~~

If YES, list each exact blocker separately.

## 9. Required output

Return exactly:

~~~text
REVIEW_SOURCE_HEAD=
PR_HEAD_AT_REVIEW=
CI_STATE=

F5=
D1=
A8=
DOWNSTREAM_SOURCE_BLOCKER=

NEW_BLOCKERS=
TOTAL_BLOCKERS=

R7_PRELIVE_RECOMMENDATION=
BLOCK
or
PROCEED_TO_ARTIFACT_BINDING_AND_READONLY_PREFLIGHT

R7_LIVE_APPLY_RECOMMENDATION=
NOT_YET_AUTHORIZED

MERGE_RECOMMENDATION=
NO_MERGE

REQUIRED_SOURCE_REPAIRS=
REQUIRED_TESTS=
REQUIRED_PRELIVE_STEPS=
~~~

For any OPEN or new blocker, include:

~~~text
exact path/function/source fragment
concrete failure mode
why it blocks or does not block prelive
minimum repair
minimum regression test
~~~

## 10. Closure threshold

Only return:

~~~text
PROCEED_TO_ARTIFACT_BINDING_AND_READONLY_PREFLIGHT
~~~

if all are true:

~~~text
F5=CLOSED
D1=CLOSED
A8 is CLOSED or explicitly nonblocking
DOWNSTREAM_SOURCE_BLOCKER=NO
current CI confirms 25/25 PASS
_07 remains NOT_GRANTED
~~~

Even with PASS, the next permitted sequence is only:

~~~text
bind replacement exact artifact
→ freeze cleanup boundary for retained R3 payload
→ perform read-only minimal-host inventory
→ perform read-only storage/transport/capacity preflight
→ independently review that evidence
~~~

Do not authorize live apply, do not clean retained payload, and do not merge PR #541 in this review.
