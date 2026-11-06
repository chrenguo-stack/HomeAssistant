# N3-W T1 Home Assistant mandatory-USB OTA P5 source implementation R2 closure — 2026-11-06

## 1. Gate result

```text
GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_P5_SOURCE_IMPLEMENTATION_R2_20261106_01
GATE_RESULT=CLOSED_PASS

SOURCE_DESIGN_HEAD=14a085f5efa7cce7439c084924ed7da53c19b620
R1_EXECUTABLE_SOURCE_HEAD=284a7120da246df733de61668f20fd46510c81ca
R1_FINAL_DOCS_HEAD=c07ff36a68bcdf25366fba4e736bc69afd28c27d
R2_EXECUTABLE_SOURCE_HEAD=e5d9575d24d30f2498e1e64cedd245b6f124c866
PR=#788
BRANCH=review/n3w-t1-core-updater-storage-policy-20261105

REAL_USB_FORMAT=false
REAL_BLOCK_DEVICE_ACCESS=false
REAL_DOCKER_COMMAND=false
LIVE_T1_MUTATION=false
BOARD_ACCESS=false
MERGE=false
R3_ENTERED=false
```

R2 closes the simulated Home Assistant mandatory-USB transaction slice. It validates the U0-U13 transaction orchestration against synthetic removable media, a synthetic Docker image store and synthetic Home Assistant persistent data. It does not execute block-device commands, format a physical USB device, stop the real Home Assistant service, mutate Docker on T1 or access a board.

## 2. R2 source delta

Production-side source delta is intentionally narrow:

```text
tools/n3w_t1_core_updater_ha_usb.py
```

R2 adds pure orchestration/guard functions for:

- PREPARE request U0 -> U1;
- formatted-media binding U1 -> U2;
- target preparation and exact target verification U2 -> U4;
- INSTALL intent U4 -> U5 without authorization claim;
- predecessor recovery preparation U5 -> U6;
- verified predecessor + HA quiesce U6 -> U7;
- U8 final recovery admission;
- U9 fresh authorization claim;
- predecessor capacity release U9 -> U10 only after destructive-cutover admission;
- target started/accepted/committed U10 -> U13A;
- rollback completion U9-U12 -> U13B only after both image and HA data are restored;
- deterministic power-loss reentry classification;
- exact USB filesystem UUID continuity after U9.

R2 also tightens formatted-media authority by independently requiring both:

```text
filesystem=ext4
label=N3W-UPDATE
```

No host command execution is added.

## 3. Synthetic transaction test model

R2 test authority:

```text
tests/tools/test_n3w_t1_core_updater_ha_usb_r2.py
```

The test model uses only temporary/synthetic resources:

```text
SYNTHETIC_USB=true
SYNTHETIC_DOCKER_IMAGE_STORE=true
SYNTHETIC_HA_CONFIG_TREE=true
REAL_/dev_ACCESS=false
REAL_DOCKER=false
REAL_SYSTEMD=false
```

The synthetic USB metadata models GPT/ext4/N3W-UPDATE/UUID/capacity without invoking partition or filesystem tools.

The synthetic Docker host models predecessor export, exact-target load, exact-predecessor restore and active image identity without invoking Docker.

The synthetic HA data tree models /config, .storage and SQLite-like persistent state, plus create/verify/restore behavior. Its confidentiality/authenticity flags are test-contract simulations only; R2 does not claim to implement the final production backup encryption/key-recovery mechanism.

## 4. R2 acceptance coverage

R2 proves these frozen behaviors:

1. target preparation reaches READY_TO_INSTALL while HA remains running;
2. predecessor export and HA backup do not exist at READY_TO_INSTALL;
3. corrupt target stops before READY_TO_INSTALL with predecessor/runtime unchanged;
4. INSTALL intent does not claim or consume live authorization;
5. corrupt predecessor recovery stops before U7/U9;
6. HA is quiesced before consistent HA data backup;
7. corrupt HA backup stops before U8/U9;
8. U8 requires exact target + exact predecessor recovery + valid HA data backup + exact production prestate + capacity;
9. U9 is the first destructive-cutover authority;
10. predecessor removal is rejected before U9;
11. successful target activation keeps target-migrated production /config;
12. rollback PASS requires both predecessor image restore and pre-upgrade HA data restore;
13. image-only rollback is insufficient;
14. after U9, missing USB returns RECOVERY_MEDIA_REQUIRED;
15. after U9, wrong USB UUID fails closed;
16. U9/U10/U11 reentry classifies rollback-required with the same USB;
17. U12 with the same USB is forward-commit eligible;
18. every U0-U11 phase has deterministic reentry classification;
19. forged formatted-media authorization with the wrong label is rejected;
20. no broad Docker prune/systemd/block-device command path exists in the R2 orchestrator.

The R1 safety contracts remain active, including root/internal disk rejection, multiple-device rejection, read-only USB rejection, explicit destructive confirmation, 14 GiB measured floor, transaction-capacity formula and Generic-V2/HA-USB mutual exclusion.

## 5. CI failure and repair history

Initial R2 source head:

```text
INITIAL_R2_HEAD=cdde5ff8685c53d214b461afc06a8ab8be57089f
```

Two updater workflows failed because the R2 test used the wrong Python keyword:

```text
WRONG=observed_filesystem_uuid
CORRECT=observed_usb_filesystem_uuid
```

This was a test-call error only. Product/state-machine logic did not fail.

Repair:

```text
TEST_KEYWORD_REPAIR_HEAD=35239c99de3928c56864a3393e0f18044048f36a
PRODUCT_LOGIC_CHANGED_BY_REPAIR=false
```

That repair head passed 16/16 workflows.

Independent source review then found two bounded closure gaps:

- frozen required-test #21 required deterministic power-loss classification coverage for every U0-U11 phase, while the first suite covered only selected phases;
- formatted-media binding enforced ext4 but did not independently enforce the frozen label N3W-UPDATE.

Both were repaired without architecture expansion.

Final R2 executable authority:

```text
R2_EXECUTABLE_SOURCE_HEAD=e5d9575d24d30f2498e1e64cedd245b6f124c866
WORKFLOW_COUNT=16
SUCCESS=16
FAILURE=0
```

Focused source-job results:

```text
N3W_T1_CORE_UPDATER_MANAGER_A_TO_B_SOURCE_JOB=184_PASSED
N3W_T1_CORE_UPDATER_HA_TARGET_BINDING_SOURCE_JOB=144_PASSED
MANAGER_EXACT_PACKAGE_SLICE=SUCCESS
MANAGER_PRE_U1_V2_SIMULATION=SUCCESS
HA_EXACT_TARGET_BINDING=SUCCESS
```

## 6. Independent source review result

Independent review of the final R2 source confirms:

```text
DESTRUCTIVE_BOUNDARY_BEFORE_U9=false
ROLLBACK_IMAGE_ONLY_PASS=false
ROLLBACK_REQUIRES_IMAGE_AND_DATA=true
POST_U9_USB_UUID_CONTINUITY_REQUIRED=true
U0_U11_POWER_LOSS_CLASSIFICATION_COVERED=true
WRONG_MEDIA_LABEL_REJECTED=true
BROAD_DOCKER_PRUNE=false
SUBPROCESS_HOST_EXECUTION_ADDED=false
REAL_BLOCK_DEVICE_COMMAND_ADDED=false
```

R2 remains a simulated transaction gate. It does not provide real host adapters.

## 7. Baseline impact classification

The accepted production authority remains unchanged:

```text
CURRENT_AUTHORITY_MANIFEST=infra/n3w-t1/production/t1-core-stack-current.json
CURRENT_REPOSITORY_PRODUCT_SOURCE_HEAD=5b32e1ae82104a42f9e4e6907fe44d9172e87615
CURRENT_REPOSITORY_MANAGER=local/greenhouse-manager:fresh-5b32e1ae8210
CURRENT_REPOSITORY_HOMEASSISTANT=local/n3w-homeassistant:2026.10.0-0c73235a
CURRENT_REPOSITORY_BROKER=local/n3w-mosquitto:2.1.2-3184566d
LIVE_DEPLOYMENT_STATE=APPLIED_ACCEPTED
```

Classification:

```text
CURRENT_AUTHORITY_MANIFEST_CHANGED=false
U0_HISTORICAL_BASELINE_CHANGED=false
PRODUCTION_COMPOSE_CHANGED=false
GREENHOUSE_MANAGER_SOURCE_CHANGED=false
HOMEASSISTANT_CONFIG_CHANGED=false
BROKER_SOURCE_CHANGED=false
LIVE_T1_RUNTIME_STACK_CHANGED=false
```

R2 changes development/updater source authority only. Existing historical execution packages and their frozen source bindings remain historical evidence and are not rewritten.

The R1-recorded Generic V2 successor package identity remains evidence for the Generic V2 package that contains the localized transaction-state mutual-exclusion repair. It is not promoted to a complete HA-USB execution package by R2; R2 still does not perform host packaging/integration.

## 8. Deferred work

R2 intentionally does not implement:

- approved OTA manifest provider;
- MQTT Update discovery/state;
- PREPARE/INSTALL command ingress from greenhouse-manager;
- production IPC between greenhouse-manager and privileged updater;
- physical USB enumeration/partition/format/mount;
- real predecessor Docker export/load/remove;
- real HA service quiesce/start;
- production HA data backup encryption/authentication/restore;
- real-T1 read-only preflight;
- live install.

## 9. Next gate

```text
NEXT_ONE_GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_P5_SOURCE_IMPLEMENTATION_R3_20261106_01
R3_SCOPE=GREENHOUSE_MANAGER_OTA_CONTROL_PLANE_ONLY
R3_PRIVILEGED_HOST_OPERATIONS=false
R3_DOCKER_SOCKET_ACCESS=false
R3_BLOCK_DEVICE_ACCESS=false
R3_REAL_USB_FORMAT=false
R3_LIVE_T1_MUTATION=false
R3_BOARD_ACCESS=false
MERGE=false
```

R3 may implement approved-manifest normalization, version/update-state projection, Home Assistant MQTT Update discovery/state and bounded PREPARE/INSTALL/STATUS intent validation in greenhouse-manager. It must not become a second upgrade authority and must not accept raw host paths, block-device names, Docker arguments or shell commands.
