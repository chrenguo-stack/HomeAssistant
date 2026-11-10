# N3-W T1 Home Assistant mandatory-USB OTA R7A
# KF-147 Stage B preclaim Manager IPC V3 blocker + exact artifact closure — 2026-11-09

## Result

```text
GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_LIVE_REPAIR_B_T1_POLICY_SOURCE_REPAIR_20261109_01
RESULT=PRECLAIM_STOP_MANAGER_IPC_V3_UNSUPPORTED

AUTHORIZATION_GRANTED=true
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
T1_MUTATION=false
```

Fresh read-only evidence proves the live T1 is healthy and the existing U1 transaction/candidate
state is preserved, but the running Manager only supports host IPC response schemas V1/V2.

```text
MANAGER_IMAGE=local/greenhouse-manager:fresh-7807271e4c48
MANAGER_IPC_V3_SUPPORT=false
MANAGER_IPC_V2_SUPPORT=true

HOST_IPC_V3_SUPPORT=false
HOST_RELEASE_POLICY_PRESENT=false

TRANSACTION_PHASE=U1_PREPARE_REQUESTED
TRANSACTION_STATUS=ACTIVE
TRANSACTION_AUTHORIZATION_CLAIMED=false
TRANSACTION_AUTHORIZATION_CONSUMED=false

PREPARE_CONFIRMATION_REQUIRED=true
PREPARE_CONFIRMATION_CONSUMED=false
PREPARE_ERROR_CODE=None
CANDIDATE_MODEL=Extreme
CANDIDATE_CAPACITY_BYTES=32017047552
CAPACITY_SNAPSHOT_PRESENT=false

USB_LIKE_DISK_COUNT=1
USB_MODEL=Extreme
USB_MOUNTED=false

OTA_PUBLIC_HTTP=200
OTA_PUBLIC_CONTENT_LENGTH=835309535
```

The KF-147 repaired host IPC returns schema V3 when capacity projection is present. Because the
production Manager container does not mount host repository source, installing only repaired host
source would produce a deterministic Manager/host protocol mismatch. Stage B therefore stopped
before claim.

## Exact Manager V3-compatible artifact

The existing repository exact ARM64 build workflow was triggered from PR #800 exact head and passed.

```text
BUILD_WORKFLOW=N3W T1 fresh install exact ARM64 CI
BUILD_RUN_ID=42616473226
BUILD_JOB_ID=129157473947
BUILD_RESULT=SUCCESS
SOURCE_HEAD=44e7d74727147975de88e85c4b18ba3f7493fd76

MANAGER_IMAGE=local/greenhouse-manager:fresh-44e7d7472714
MANAGER_IMAGE_ID=sha256:fd5104d610645347fe47137dbb24121851fa8a48530df3e3c905704607c5e3d4
MANAGER_TAR_SHA256=9316817590c4fe74498629d0451a4897c2e11bef7bc4b423b66e47bb846099c5
MANAGER_TAR_SIZE_BYTES=62957568

ARTIFACT_ID=13673322402
ARTIFACT_DIGEST_SHA256=c2540433fb2d33631d67c0bc7433040510f74a039af939b6438aa5c73fbda3e1
ARTIFACT_NAME=n3w-t1-fresh-exact-arm64-44e7d74727147975de88e85c4b18ba3f7493fd76
```

From KF-147 production-source freeze head
`26a25537cdefa83d47c62b3ecc867a2cc37e8b8d` to build head
`44e7d74727147975de88e85c4b18ba3f7493fd76`, no Manager source, host updater source,
production Compose/systemd source, or release-policy source changed. The only matching authority
change in those families is qualification evidence JSON. Therefore the exact Manager artifact is a
materialization of the already-closed KF-147 source, not a new product feature delta.

## Safety boundary

```text
PREPARE_REPLAY=false
CONFIRM_USB_ERASE=false
WIPEFS=false
PARTITION_WRITE=false
MKFS=false
MOUNT=false
TARGET_DOWNLOAD=false
U2_PLUS=false
BOARD_ACCESS=false
MERGE=false
```

## Next gate

The next live mutation cannot be hidden inside the original Stage B authorization because the
original live scope was bounded to Policy V2/repaired host-source installation and host-daemon
restart. Replacing the running Manager image is an additional live component mutation.

```text
NEXT_GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_MANAGER_IPC_V3_IMAGE_ONLY_LIVE_APPLY_20261109_01
NEXT_GATE_AUTHORIZED=false
AUTO_EXECUTE_NEXT_GATE=false
```

The future gate must:
- load only the exact Manager tar above;
- transition only Manager from `fresh-7807271e4c48` to `fresh-44e7d7472714`;
- preserve Home Assistant and Broker identities;
- preserve the U1 transaction and Extreme candidate byte-exactly;
- keep PREPARE and destructive USB APIs uninvoked;
- provide automatic Manager rollback on post-apply failure;
- STOP after Manager V3 capability is proven.

After that gate passes, the original KF-147 Stage B policy/source repair may resume under a fresh
bounded continuation authorization.
