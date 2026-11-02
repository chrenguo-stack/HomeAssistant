# N3-W T1 Core Stack Clean Reference R3 current-product registration readiness exact readonly preflight source repair progress

Date: 2026-11-02

~~~text
TASK=N3W_T1_CORE_STACK_CLEAN_REFERENCE_R3_CURRENT_PRODUCT_REGISTRATION_READINESS_EXACT_READONLY_PREFLIGHT_20261102_01
STATE=SOURCE_REPAIR_CI_PASS_AWAIT_LIVE_RETRY

PREVIOUS_LOCAL_PACKAGE_AUTHORITY=PASS
PREVIOUS_LIVE_INSPECT_EXECUTED=false
PREVIOUS_FAILURE_CLASS=LOCAL_SCRIPT_PARSE_ERROR_PLUS_HOST_CONTAINER_PATH_BINDING_BUG

FINAL_REPAIR_HEAD=1a2115d40e62140ac81c48a5b4bb7d4963fe1aee
FINAL_BRIDGE_BLOB=3e2acae957fb422eedacade660a50fea050c5b6a
FINAL_TEST_BLOB=28f3a86ac2cf837f943541f698d42320c3d0df0f
FINAL_WORKFLOW_BLOB=d6efc87c059324faf37b7d9eef68d8f5e7ccb8fa

FINAL_CI_RUN=41378062886
FINAL_CI_RESULT=SUCCESS
FINAL_TEST_COUNT=29
FINAL_BUILD_BRIDGE_PACKAGE=SUCCESS
FINAL_ARTIFACT_ID=13112421203
FINAL_ARTIFACT_DIGEST=sha256:729dc3b72133a2fb29285b27c32cab35b81eb091f3e80cce3e64d2d5ae9f7ab8
FINAL_PACKAGE_MANIFEST_SHA256=652017236e0e753392e72e072fa89cf6d5d59cdd92fdc2f0f1c92f220c35b2a4

TRUSTED_LAN_AUTHORITY_BLOB=ea964cd2b9b9380785f3aee5e8d6383180be4ee0
REGISTRATION_GUARD_BLOB=ef5077b6bc80c73bc8d3f35cf7a33a198ce918c7
BROKER_GUARD_BLOB=795903b06c7ee93a0602649e478bc070723ab8c0

HOST_TRUSTED_LAN_STATE=/run/n3wfc4-trusted-lan/state.json
MANAGER_TRUSTED_LAN_TARGET=/run/n3w/trusted-product-lan
MANAGER_TRUSTED_LAN_BIND_READONLY=true

T1_MUTATION=false
PAIRING_WINDOW_OPENED=false
BOARD_ACCESS=false
MERGE=false
~~~

The first live retry attempt did not execute the exact readiness observer. A local shell
packaging error stopped the script, and the host-side baseline exposed a source binding bug:
the observer tried to read the Manager-container trusted-LAN target path on the host.

The frozen product authority publishes the host file at
`/run/n3wfc4-trusted-lan/state.json` and mounts the containing directory read-only into the
Manager at `/run/n3w/trusted-product-lan`.

The repair now:

- reads the exact host authority path;
- verifies the Manager bind source and target;
- requires the bind to be read-only;
- binds the exact trusted-LAN authority source blob;
- retains the current-product registration readiness model;
- remains structurally readonly.

CI run `41378062886` is SUCCESS with 29 tests and an independently verified exact package.

The gate remains open until the real T1 exact readonly inspect passes with pre/post state
unchanged and temporary transport residue removed.
