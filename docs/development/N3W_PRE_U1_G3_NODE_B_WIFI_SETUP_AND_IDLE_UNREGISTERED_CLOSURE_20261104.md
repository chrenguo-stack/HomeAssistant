# N3-W Pre-U1 G3 Node B Wi-Fi setup / idle-unregistered closure

Date: 2026-11-04

## 1. Result

```text
GATE=N3W_PRE_U1_G3_NODE_B_WIFI_SETUP_AND_IDLE_UNREGISTERED_20261104_01
RESULT=CLOSED_PASS

PRE_U1_G0_RESULT=CLOSED_PASS
PRE_U1_G1_RESULT=CLOSED_PASS
PRE_U1_G2_RESULT=CLOSED_PASS
PRE_U1_G3_RESULT=IN_PROGRESS

LOCAL_FACTORY_SHA256=9ccc469898832bda612634aef64ca946631e81574076be504ef864aaee56d8f9
EXPECTED_FACTORY_SHA256=9ccc469898832bda612634aef64ca946631e81574076be504ef864aaee56d8f9
LOCAL_FACTORY_SHA256_MATCH=true
LOCAL_FACTORY_SIZE=1532256
EXPECTED_FACTORY_SIZE=1532256
LOCAL_FACTORY_SIZE_MATCH=true
LOCAL_FACTORY_BINDING=PASS

NODE_B_BOOT_NORMAL=true
NODE_B_WIFI_SETUP_COMPLETED=true
NODE_B_WIFI_CONNECTED=true
NODE_B_IDLE_UNREGISTERED_QR_VISIBLE=true
NODE_B_FIRST_REGISTRATION_STARTED=false

NODE_A_CURRENTLY_OFFLINE=true
NODE_A_G2_ACCEPTANCE_RETAINED=true

FLASH_MUTATION=false
NVS_MUTATION=true
T1_RUNTIME_MUTATION=false
DIRECT_CREDENTIAL_INJECTION=false
REGISTRATION_MUTATION=false
PR774_MERGE=false
```

Node B was configured through the normal Captive Portal using the product Wi-Fi setup entry on LCD page 5. After successful Wi-Fi connection, page 5 changed to the normal idle-unregistered / online-registration QR. The operator stopped at that boundary and did not scan the registration QR, select a host, click “寻找主机” or “开始注册”, or enter any first-registration transaction.

## 2. Factory artifact binding

Before Wi-Fi mutation, the local `firmware.factory.bin` used for Node B was rebound read-only:

```text
SHA256=9ccc469898832bda612634aef64ca946631e81574076be504ef864aaee56d8f9
SIZE=1532256
MATCH=PASS
```

This matches the frozen Node A/B factory artifact authority. No reflash was performed. The earlier post-boot whole-image verify mismatch remains classified under KF-132 and is not a reflash trigger.

## 3. Scope boundary

This closure proves only:

- the frozen local factory image binding matches;
- Node B boots normally;
- normal Captive Portal Wi-Fi setup succeeds;
- Node B reaches the idle-unregistered / online-registration QR;
- no first-registration transaction has started.

It does not prove Node B registration, credential issuance, durable Manager commit, Node A/Node B coexistence, or G3 overall completion.

## 4. Next boundary

```text
NEXT_ONE_GATE=N3W_PRE_U1_G3_NODE_A_RESTORE_AND_DUAL_BASELINE_READONLY_20261104_01
AUTO_EXECUTE_NEXT_GATE=false
NEW_AUTHORIZATION_REQUIRED=NODE_A_PHYSICAL_RESTORE_ONLINE

NODE_B_REGISTRATION_ALLOWED=false
T1_RUNTIME_MUTATION_ALLOWED=false
PR774_MERGE=false
STOP=true
```

Before formal Node B registration, Node A must be physically restored and fresh continuity/baseline evidence must prove the existing registered node and product services are healthy. Do not scan Node B's registration QR or begin registration before that gate closes.
