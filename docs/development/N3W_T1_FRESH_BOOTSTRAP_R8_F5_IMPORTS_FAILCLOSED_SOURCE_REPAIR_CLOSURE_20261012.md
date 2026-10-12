# N3-W T1 fresh bootstrap R8 F5 imports fail-closed source repair closure（2026-10-12）

## 1. Gate result

~~~text
CONVERSATION_GITHUB_ALIGNMENT=PASS
PR=541
PR_STATE=OPEN_DRAFT
BASE_MAIN=d423211b6196c2f2f0f01dff072c4f877fbe58ee
SOURCE_REVIEW_HEAD=5ed613673ec1ead29a1153d0e3916bdd3539a3fb
SOURCE_REVIEW_HEAD_CI=25/25_PASS
MERGE=false
T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
PRODUCTION_SERVICE_START=false
~~~

## 2. Astra R3 input

Astra R3 independently returned:

~~~text
F5=OPEN_BLOCKER
D1=CLOSED
A8=CLOSED
DOWNSTREAM_SOURCE_BLOCKER=YES
NEW_BLOCKERS=0
TOTAL_BLOCKERS=1
R7_PRELIVE_RECOMMENDATION=BLOCK
~~~

The sole remaining path was containerd configuration imports.

The external-containerd probe read the primary effective config path and then used config.root, but did not process or reject non-empty imports. A later imported file can override a string field such as root, so the capacity check could inspect the wrong filesystem.

## 3. Minimal F5 repair

Product/harness repair commit:

~~~text
F5_IMPORTS_FAILCLOSED_COMMIT=0957958c535d67c29cec411df98829d00e7a9028
~~~

The generated storage probe now evaluates:

~~~text
config_imports = config.get("imports")
if config_imports not in (None, []):
    raise RuntimeError("containerd_imports_unsupported")
~~~

The project deliberately does not implement containerd's full recursive config merge semantics in this stage.

Contract:

~~~text
imports absent -> continue
imports = [] -> continue
non-empty imports -> STOP_PRECLAIM
no guessed merged root
no DockerRootDir fallback
no payload transfer
no authorization claim
~~~

Prospective live authorization rotated because executable source changed:

~~~text
PREDECESSOR=_07
PREDECESSOR_GRANTED=false
PREDECESSOR_STATUS=SUPERSEDED_UNGRANTED

SUCCESSOR=N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_LIVE_APPLY_20261012_08
SUCCESSOR_GRANTED=false
SUCCESSOR_CLAIMED=false
SUCCESSOR_CONSUMED=false
~~~

## 4. Required execution-level regression

Astra R3 required execution of the actual generated storage probe rather than only source-string assertions.

The test fixture launches bounded fake dockerd/containerd processes and executes:

~~~text
python -c _remote_storage_probe_script()
~~~

against controlled command/config/storage evidence.

Covered cases:

~~~text
DIRECT_CONFIG_ROOT:
  external containerd primary config directly sets root
  -> generated probe resolves that exact root

NON_EMPTY_IMPORTS:
  primary config sets root and imports another TOML
  -> generated probe exits nonzero
  -> stderr contains containerd_imports_unsupported
~~~

## 5. Two CI failures classified as test-fixture-only

First fixture failure:

~~~text
COMMIT=0957958c535d67c29cec411df98829d00e7a9028
CAUSE=fake systemctl used shell $4 for service name; actual command service name is $2
PRODUCT_F5_LOGIC_REACHED=false
~~~

Correction:

~~~text
0ad32499c6545ced0614baa2274cafdb60061204
test(n3w): fix storage probe service fixture
~~~

Second fixture failure:

~~~text
CAUSE=fake containerd process used python -c; probe correctly supports containerd short -c and misread Python's own -c as the config option
PRODUCT_F5_LOGIC_REACHED=false
~~~

Correction:

~~~text
5ed613673ec1ead29a1153d0e3916bdd3539a3fb
test(n3w): emulate containerd argv without python flag collision
~~~

Both corrections touch only:

~~~text
tests/tools/test_n3w_t1_fresh_product_staging_host.py
~~~

They do not weaken or modify the F5 fail-closed production path.

## 6. Final exact CI

~~~text
EXACT_HEAD=5ed613673ec1ead29a1153d0e3916bdd3539a3fb
TOTAL=25
PASS=25
FAIL=0
IN_PROGRESS=0
QUEUED=0
~~~

Critical workflows:

~~~text
N3W T1 fresh bootstrap deployable payload CI=PASS
N3W T1 production stack staging payload CI=PASS
N3W T1 fresh install exact ARM64 CI=PASS
N3W T1 fresh install host-only CI=PASS
N3W T1 deployment gate CI=PASS
N3W T1 S20 production image binding CI=PASS
N3W T1 HA bootstrap isolated CI=PASS
C-07 node retirement CI=PASS
greenhouse-manager CI=PASS
M2 manager runtime secret ownership CI=PASS
Public repository safety CI=PASS
~~~

Deployable evidence:

~~~text
RUN_ID=38245536856
FOCUSED_TESTS=71 passed
FRESH_CROSS_STORE_IMAGE_BINDING=PASS
FRESH_DOCKER_ARCHIVE_CONFIG_BINDING=PASS
FRESH_POSTCHECK_STATE_OWNER_AUDIT_UID999=PASS
FRESH_DYNSEC_VOLUME_LIFECYCLE=PASS
FRESH_CREDENTIAL_BUNDLE_IMMUTABILITY=PASS
FRESH_LIVE_ADAPTER_PRECOMMIT_REHEARSAL=PASS
~~~

Production stack staging evidence:

~~~text
RUN_ID=38245536675
FOCUSED_TESTS=47 passed
~~~

## 7. Current stop

~~~text
FINAL_INDEPENDENT_REVIEW=NOT_RUN_AFTER_R8
REPLACEMENT_ARTIFACT=NOT_BOUND
RETAINED_R3_PAYLOAD_CLEANUP=NOT_AUTHORIZED
T1_READONLY_PREFLIGHT=NOT_RUN_FOR_R8
LIVE_AUTHORIZATION=_08_NOT_GRANTED
MERGE=false
~~~

Do not proceed to artifact binding or T1 until the next-chat final focused review closes F5 and confirms DOWNSTREAM_SOURCE_BLOCKER=NO.
