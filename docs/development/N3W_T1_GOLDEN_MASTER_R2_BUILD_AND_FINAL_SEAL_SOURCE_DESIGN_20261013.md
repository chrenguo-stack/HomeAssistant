# N3-W T1 Golden Master R2 Build + Final Seal Source Design（2026-10-13）

TASK=
`N3W_T1_GOLDEN_MASTER_R2_BUILD_AND_FINAL_SEAL_SOURCE_DESIGN_20261013`

## 0. Decision

```text
DESIGN_RESULT=PASS
DESIGN_BASE=a98aff1f6916c12de84bbb9a2b3ae41ebc80b4e4
PRODUCT_SOURCE_EQUIVALENT_TO=9155855a71f4750ebf7a7b22d9b4e000627e2f98
PRODUCT_SOURCE_DRIFT_SINCE_9155855a=false

P2B_TARGET_ARMBIAN_READONLY_EVIDENCE=CLOSED_PASS
R2_SOURCE_DESIGN=PASS
R2_LIVE_EXECUTION=false
T1_ACCESS=false
T1_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
MERGE=false
```

The compare from `9155855a...` to the design base contains documentation only. The
reviewed product source used for this design is therefore unchanged from the P2B exact
execution source.

This design is subordinate to:

- `docs/adr/0009-t1-golden-master-firstboot-production-lifecycle.md`;
- `docs/development/N3W_T1_GOLDEN_MASTER_FIRSTBOOT_SOURCE_DECOMPOSITION_AND_REPAIR_DESIGN_20261012.md`;
- `docs/development/N3W_T1_EXPLICIT_DEVICE_PROVISIONING_COMMAND_AND_BOOT_DECOUPLING_DESIGN_FREEZE_20261013.md`;
- `docs/development/N3W_T1_EXPLICIT_DEVICE_PROVISIONING_P2B_TARGET_ARMBIAN_READONLY_EVIDENCE_EXECUTION_CLOSURE_20261013.md`.

## 1. What P2B changed

P2B closed the previous “generic Linux assumption” gap for the **current target host
state**:

- target is Armbian 26.05.0 / arm64 / S912-Phicomm-T1;
- both machine-id paths are populated regular files and contain the same identity;
- ECDSA, ED25519 and RSA SSH host keys are populated;
- exact target contains `sshd-keygen.service` with `ConditionFirstBoot=yes` and
  `ssh-keygen -A`;
- exact target contains `systemd-machine-id-commit.service`, but its observed commit
  path is mount-point gated;
- `/etc/NetworkManager/system-connections` contains zero persisted profiles;
- `armbian-firstrun.service` exists, but its implementation body was not captured.

Therefore the current T1 is an instantiated host, not a clone-ready sealed master.

The following remain forbidden assumptions:

```text
POPULATED_MACHINE_ID_CLONE_AUTO_UNIQUIFIES=false
POPULATED_SSH_HOST_KEYS_CLONE_AUTO_UNIQUIFIES=false
ARMBIAN_FIRSTRUN_IS_UNIQUENESS_AUTHORITY=false
EMPTY_NM_PROFILE_DIRECTORY_PROVES_NETWORK_UNIQUENESS=false
```

## 2. R2 is split into three bounded source packages

R2 must not become one large live tool. Freeze:

```text
R2A=GOLDEN_MASTER_BUILD_SOURCE_REPAIR
R2B=FINAL_SEAL_ORCHESTRATION_AND_AUDIT_SOURCE_REPAIR
R2C=TARGET_ARMBIAN_SEAL_ADAPTER_EVIDENCE_AND_SOURCE_REPAIR
```

R2A and the host-independent part of R2B can proceed repository-only.

R2C needs additional exact target-Armbian evidence before any real machine-id,
SSH-host-key, NetworkManager or journal/random-seed mutation adapter is written.

## 3. R2A — real Golden Master build source package

### 3.1 Existing source that is retained

Keep the already-reviewed pure orchestrator:

`host/greenhouse-manager/src/greenhouse_manager/bootstrap/golden_master_installer.py`

Its stage order remains:

```text
preflight_master
→ authorization claim callback
→ load_images
→ stage_public_runtime
→ commit_public_candidate
→ master_postcheck
```

Failure after mutation starts must clean only master-owned public material and images.
It must never delete or rewrite instance material that it did not create.

### 3.2 Existing R8 implementation reused, not forked

`tools/n3w_t1_fresh_product_bootstrap.py::LiveFreshInstallerAdapters` already owns:

- exact offline image load and runtime binding;
- public-source staging;
- public-only commit;
- master postcheck;
- master-owned cleanup.

R2A must reuse these functions instead of cloning the R8 logic into a second large
implementation.

The minimum compatibility addition is a master-specific preflight adapter whose return
contract proves:

```text
status=PASS
instance_material_absent=true
production_service_start=false
```

The historical R8 apply entry point and its authorization identity must remain unchanged.

### 3.3 New host tool

Add:

`tools/n3w_t1_golden_master_build.py`

Responsibilities:

1. load and verify the exact build payload manifest;
2. bind exact source/image/public file inventory;
3. run a read-only preflight;
4. require a separate one-shot Golden Master build authorization before first mutation;
5. invoke the pure `run_golden_master_build()` orchestrator;
6. produce a public-safe build result;
7. never create SYSTEM_ID, MANAGER_ID, CA private keys, service credentials, DynSec,
   Manager state, HA state or product listeners;
8. never start Broker/Manager/HA.

The build authorization is distinct from historical R8 `_08` and cannot be replayed.

### 3.4 Public release manifest

The build package must create a secret-free release manifest before public commit.

Minimum binding:

```text
schema
release_id
source_head
payload_manifest_sha256
image_lock_sha256
public_source_tree_sha256_or_inventory_hash
manager/homeassistant/broker exact image binding
architecture=linux/arm64
instance_material_absent=true
secret_values_included=false
seal_state=UNSEALED
```

The manifest is public material and belongs under the public product tree, not
`/etc/n3wfc4` or another instance-owned directory.

## 4. R2B — Final Seal orchestration and audit

Add a small pure module and host wrapper:

```text
host/greenhouse-manager/src/greenhouse_manager/bootstrap/golden_master_seal.py
tools/n3w_t1_golden_master_seal.py
```

Two operations are frozen:

```text
audit
seal
```

### 4.1 audit

`audit` is read-only. It may run repeatedly.

It must positively prove all of the following:

- exact release/public source/image binding;
- no instance-owned product directories or files;
- no product containers;
- no product Docker volumes;
- only allowed public/default networks;
- no product listeners;
- no product firewall activation;
- production activation units are not active;
- no SYSTEM_ID / MANAGER_ID;
- no system/Broker CA private key;
- no Broker TLS private key;
- no service credentials or Broker admin secret;
- no instantiated DynSec;
- no Manager/N3W business state;
- no HA Owner/test state;
- no unknown transaction/candidate/staging residue;
- OS identity state is classified, not guessed.

A missing expected public item or any unknown identity-bearing state is STOP, not WARN.

### 4.2 seal

`seal` is a controlled mutation operation and must require exact one-shot authorization.

The pure orchestrator may define ordering and adapter contracts now, but the real
target-Armbian OS-identity adapter is not implemented until R2C evidence closes.

Required order:

```text
READONLY_PREFLIGHT
→ CLAIM_ONE_SHOT_AUTHORIZATION
→ REMOVE/REJECT_INSTANCE_MATERIAL
→ PREPARE_OS_IDENTITY_NEUTRAL_STATE
→ FINAL_NO_SECRET_AUDIT
→ PUBLIC_RELEASE_BINDING_AUDIT
→ CAPTURE_QUIESCENCE_AUDIT
→ WRITE_SEAL_RECORD_LAST
→ FSYNC
→ SHUTDOWN_REQUIRED
```

The tool must return:

```text
disk_capture_ready=true
shutdown_required=true
reboot_before_capture_forbidden=true
production_service_start=false
```

only when every stage is proven.

### 4.3 Seal record

The seal record is public evidence. It binds:

- release_id;
- source head;
- public release manifest hash;
- image-lock hash;
- seal schema/version;
- public audit hash;
- OS-identity-neutral audit hash;
- no-secret assertion;
- shutdown-required assertion.

It contains no hostname, raw machine-id, raw SSH fingerprint, private network locator,
credential or secret.

## 5. Exact neutral state: policy frozen, mutation not yet frozen

From P2B evidence, the final captured master **must not** contain the current host's
populated machine-id or SSH host private keys.

Freeze the desired state:

```text
CAPTURE_HAS_BUILD_HOST_MACHINE_ID=false
CAPTURE_HAS_BUILD_HOST_SSH_PRIVATE_KEYS=false
CAPTURE_HAS_BUILD_HOST_NETWORK_IDENTITY_RESIDUE=false
CAPTURE_HAS_BUILD_HOST_JOURNAL_IDENTITY_RESIDUE=false
CAPTURE_HAS_BUILD_HOST_RANDOM_SEED_RESIDUE=false
```

However, do not yet freeze the concrete filesystem mutation sequence for those items.

Reason: P2B proved installed mechanisms and current state, but did not capture enough
target-specific evidence to prove the exact behavior of a sealed image after those
files are removed/emptied.

## 6. R2C — additional exact target evidence required

Before writing the real Seal OS-identity mutation adapter, one bounded **read-only**
target-Armbian evidence gate must capture at least:

1. exact `systemd --version`;
2. exact `/usr/lib/armbian/armbian-firstrun` identity-relevant behavior;
3. exact `/etc/default/armbian-firstrun` identity-relevant non-secret settings;
4. exact relationship expected between `/etc/machine-id` and
   `/var/lib/dbus/machine-id` on first boot;
5. exact SSH host-key generation ordering already identified by
   `sshd-keygen.service`, plus any package helper that changes that behavior;
6. identity-bearing state under `/var/lib/NetworkManager`, plus relevant
   NetworkManager/netplan configuration that controls stable-id, DHCP identity or MAC
   generation;
7. journald persistent machine-id directories/state;
8. random-seed persistent state and boot regeneration mechanism;
9. exact ordering showing when network/SSH may become reachable relative to identity
   establishment.

No secret values are needed; names, metadata, selected config fields and hashes are
sufficient.

This evidence gate requires a new explicit T1 read-only authorization. The already
consumed P2B authorization is not replayed.

## 7. R2A/R2B source files

Expected first source-repair package:

ADD:

```text
tools/n3w_t1_golden_master_build.py
tools/n3w_t1_golden_master_seal.py
host/greenhouse-manager/src/greenhouse_manager/bootstrap/golden_master_seal.py
host/greenhouse-manager/tests/bootstrap/test_golden_master_seal.py
tests/tools/test_n3w_t1_golden_master_build.py
tests/tools/test_n3w_t1_golden_master_seal.py
.github/workflows/n3w-t1-golden-master-ci.yml
```

MODIFY, only as necessary:

```text
tools/n3w_t1_fresh_product_bootstrap.py
.github/workflows/n3w-t1-fresh-bootstrap-deployable-payload-ci.yml
```

Do not modify:

```text
firmware
current Broker/Manager/HA activation topology
NetworkManager dispatcher live installation
historical R8 authorization identity/ledger semantics
board tooling
```

The current source-only `n3wfc4-provision-resume.service` remains uninstalled until
the functional real host provisioning adapter is ready and the Golden Master install
path owns it.

## 8. Required CI

R2 source CI must prove:

```text
MASTER_BUILD_PUBLIC_ONLY=true
MASTER_BUILD_INSTANCE_MATERIAL_ABSENT=true
MASTER_BUILD_EXACT_IMAGES=true
MASTER_BUILD_NO_PRODUCT_LISTENERS=true
MASTER_BUILD_NO_PRODUCTION_SERVICE_START=true

SEAL_AUDIT_READONLY=true
SEAL_UNKNOWN_IDENTITY_STATE_FAIL_CLOSED=true
SEAL_POPULATED_MACHINE_ID_NOT_CAPTURE_READY=true
SEAL_POPULATED_SSH_HOST_KEYS_NOT_CAPTURE_READY=true
SEAL_NETWORK_IDENTITY_UNKNOWN_NOT_CAPTURE_READY=true
SEAL_RECORD_MARKER_LAST=true
SEAL_REBOOT_BEFORE_CAPTURE_FORBIDDEN=true

R8_REGRESSION=PASS
P1_P2A_PROVISIONING_REGRESSION=PASS
PUBLIC_REPOSITORY_SAFETY=PASS
```

Fault injection must cover failure before claim, failure after claim, incomplete public
commit, unknown/unsafe symlink paths, seal audit mismatch and cleanup uncertainty.

## 9. Blocker disposition

```text
SB1_MIXED_PUBLIC_INSTANCE_STAGE=CLOSED
SB2_MIXED_COMMIT_CLEANUP_OWNERSHIP=CLOSED
SB3_MIXED_POSTCHECK=CLOSED
SB4_DURABLE_PROVISIONING_TRANSACTION=CLOSED_SOURCE
SB5_NO_SEAL_IMPLEMENTATION=PARTIAL_READY_FOR_SOURCE_REPAIR
SB6_NO_OS_IDENTITY_ADAPTER=OPEN_TARGET_EVIDENCE_BLOCKER
SB7_NO_FACTORY_CLONE_UNIQUENESS_HARNESS=OPEN_R4

R2A_SOURCE_REPAIR=READY
R2B_HOST_INDEPENDENT_SOURCE_REPAIR=READY
R2C_REAL_OS_IDENTITY_SEAL_ADAPTER=HOLD_FOR_TARGET_READONLY_EVIDENCE
```

## 10. Next execution order

```text
NEXT_ONE_GATE=
N3W_T1_GOLDEN_MASTER_R2A_R2B_HOST_INDEPENDENT_SOURCE_REPAIR_20261013_01

SOURCE_MUTATION=true
T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
MERGE=false
```

After source repair + CI + independent review:

```text
NEXT_REQUIRED_LIVE_GATE=
N3W_T1_GOLDEN_MASTER_R2C_TARGET_ARMBIAN_SEAL_ADAPTER_READONLY_EVIDENCE

T1_READONLY_AUTHORIZATION_REQUIRED=true
OLD_P2B_AUTHORIZATION_REPLAY=false
```
