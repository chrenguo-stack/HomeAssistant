# N3-W T1 Home Assistant mandatory-USB OTA R7A
# KF-147 host release policy + hybrid dynamic capacity source design — 2026-11-09

## 1. Gate and scope

```text
GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_HOST_RELEASE_POLICY_SOURCE_DESIGN_20261109_01
RESULT=CLOSED_DESIGN
KF=KF-147

HOMEASSISTANT_REPOSITORY=chrenguo-stack/HomeAssistant
HOMEASSISTANT_PR=800
DESIGN_BASE_HEAD=181507d72ccca5a6f1f4c0abe3c1de4b8f3837da

OTA_ORIGIN_REPOSITORY=chrenguo-stack/hahub.top
OTA_ORIGIN_REPOSITORY_HEAD=140fad2f12e116f25510e968cf87c69409dfc171

LIVE_T1_MUTATION=false
LIVE_OTA_SERVER_MUTATION=false
USB_MUTATION=false
CONFIRM_USB_ERASE=false
U2_PLUS=false
BOARD_ACCESS=false
MERGE=false
```

This design closes KF-147 at source-design level only. It does not deploy an OTA origin,
install a host policy on T1, restart the host daemon, format the current SanDisk candidate,
download the Home Assistant target, or advance the live HA-USB transaction.

The current live transaction remains frozen at:

```text
TRANSACTION_PHASE=U1_PREPARE_REQUESTED
TRANSACTION_STATUS=ACTIVE
PUBLIC_PHASE=USB_REQUIRED_CONFIRMATION
USB_CONFIRMATION_REQUIRED=true
USB_CONFIRMATION_CONSUMED=false
USB_CANDIDATE_MODEL=Extreme
USB_CANDIDATE_CAPACITY_BYTES=32017047552
```

The current USB stays inserted. PREPARE must not be replayed.

## 2. Root cause being repaired

KF-147 proved two coupled defects in the current R7A source/deployment contract:

1. `FixedHostReleasePolicyProvider` requires
   `/etc/n3w-t1-ota/homeassistant-release-source.json`, but A1 activation does not install it.
2. The schema treats all four non-target capacity inputs as fixed release-policy constants,
   although HA persistent data is device/time dependent and predecessor recovery is transition dependent.

Therefore the repair must not be a blind copy of a hand-written JSON file.

## 3. Frozen product decisions

```text
OTA_ARTIFACT_ORIGIN=https://ota.hahub.top
OTA_ARTIFACT_ORIGIN_MODEL=SELF_HOSTED_NGINX_STATIC
OTA_BINARY_IN_GIT=false
OTA_BINARY_ON_SERVER_FILESYSTEM=true
OTA_ARTIFACT_PATH_IMMUTABLE=true

CAPACITY_FORMULA=FIXED
CAPACITY_INPUT_MODEL=HYBRID_DYNAMIC

TARGET_ARTIFACT_INPUT=RELEASE_FIXED
PREDECESSOR_RECOVERY_INPUT=RELEASE_TRANSITION_BOUND
HA_DATA_BACKUP_INPUT=RUNTIME_DYNAMIC
TRANSACTION_WORKING_INPUT=FIXED_FORMULA
REMOVABLE_RESERVE_INPUT=FIXED_FORMULA

USB_MEASURED_USABLE_FLOOR_BYTES=15032385536
UI_MIN_RECOMMENDED_NOMINAL_USB_GB=32

PREPARE_AND_ERASE_CONFIRMATION_SEPARATE=true
INSTALL_AUTHORIZATION_SEPARATE=true
```

"Dynamic" means that the formula and safety rules are fixed, while the inputs that are truly
device/time dependent are measured at runtime.

## 4. OTA origin design

### 4.1 Existing infrastructure reused

The `hahub.top` server integration already defines an independent static OTA container:

```text
container=esp_ota
image=nginx:alpine
host_storage=./ota
container_storage=/usr/share/nginx/html
existing_host_port=8081
```

The main website is a different Nginx container and its site deploy script uses
`rsync --delete`. Therefore Home Assistant OTA binaries must not be stored under the website
deployment tree.

### 4.2 Canonical server-side storage

```text
/root/myserver/ota/
  n3w/
    homeassistant/
      releases/
        <release_identity>/
          homeassistant-arm64.tar.gz
```

For the current target:

```text
release_identity=homeassistant-2026.10.4
filename=homeassistant-arm64.tar.gz
size_bytes=835309535
sha256=eba1da958fc9c759c30d1cb34445c364e895bcd8d5e6c0d8392ab6849ece9973
```

Canonical URL:

```text
https://ota.hahub.top/n3w/homeassistant/releases/homeassistant-2026.10.4/homeassistant-arm64.tar.gz
```

### 4.3 Nginx routing

The public HTTPS Nginx must add an exact virtual host for `ota.hahub.top` before the wildcard
FRP virtual host.

Logical route:

```text
ota.hahub.top:443
  -> public TLS termination
  -> ota_server:80
  -> /usr/share/nginx/html
  -> /root/myserver/ota
```

The OTA virtual host must:

- accept GET and HEAD only;
- keep autoindex disabled;
- serve the immutable binary with exact Content-Length;
- use `application/octet-stream`;
- support normal byte-range responses when Nginx provides them;
- set a long immutable cache policy for versioned release paths;
- never expose upload/delete APIs;
- not proxy through FRP;
- not place OTA payloads in the Git repository.

### 4.4 Publication contract

A release path is immutable.

```text
SAME_RELEASE_PATH_OVERWRITE=false
LATEST_SYMLINK_AS_AUTHORITY=false
ATOMIC_PUBLISH=true
PREPUBLICATION_SIZE_VERIFY=true
PREPUBLICATION_SHA256_VERIFY=true
```

Publication uses a temporary server-side filename, verifies exact size and SHA-256, fsyncs as
appropriate, and atomically renames into the final versioned path. A different byte sequence requires
a different release identity/path.

### 4.5 Downloader origin restrictions

R7A source repair must tighten `artifact_url` validation:

```text
scheme=https
hostname=ota.hahub.top
username=null
password=null
query=empty
fragment=empty
path_prefix=/n3w/homeassistant/releases/
filename=homeassistant-arm64.tar.gz
```

The final response URL must equal the policy URL exactly. Cross-origin or same-origin redirects are
not required for R7A and must fail closed.

The existing exact byte count, SHA-256 and portable image identity checks remain mandatory.

## 5. Host release-policy schema V2

The fixed path remains:

```text
/etc/n3w-t1-ota/homeassistant-release-source.json
```

Repository authority for the current target will be:

```text
infra/n3w-t1/upgrades/homeassistant-2026.10.4-host-release-policy.json
```

New schema:

```text
gh.n3w-t1-ha-ota-host-release-policy/2
```

Required shape:

```json
{
  "schema": "gh.n3w-t1-ha-ota-host-release-policy/2",
  "release_identity": "homeassistant-2026.10.4",
  "artifact_url": "https://ota.hahub.top/n3w/homeassistant/releases/homeassistant-2026.10.4/homeassistant-arm64.tar.gz",
  "target_archive_sha256": "<exact sha256>",
  "target_archive_size_bytes": 835309535,
  "expected_predecessor_image_ref": "<exact predecessor>",
  "predecessor_recovery_budget_bytes": "<release-qualified integer>",
  "capacity_policy": {
    "usb_measured_usable_floor_bytes": 15032385536,
    "round_up_quantum_bytes": 268435456,
    "ha_data_backup_min_budget_bytes": 1073741824,
    "ha_data_growth_margin_ratio_ppm": 250000,
    "ha_data_growth_margin_floor_bytes": 536870912,
    "transaction_working_floor_bytes": 536870912,
    "transaction_working_target_ratio_ppm": 100000,
    "removable_reserve_floor_bytes": 1073741824,
    "removable_reserve_ratio_ppm": 100000,
    "recommended_nominal_usb_sizes_gb": [32, 64, 128, 256, 512, 1024],
    "nominal_usable_guard_ppm": 900000
  }
}
```

The numeric predecessor budget is intentionally not guessed in source design. It is produced by
release qualification using the exact predecessor and exact recovery encoding, then committed as
release-transition authority.

## 6. Capacity model

### 6.1 Fixed formula

```text
BASE_REQUIRED_BYTES =
  TARGET_ARTIFACT_BYTES
+ PREDECESSOR_RECOVERY_BUDGET_BYTES
+ HA_DATA_BACKUP_BUDGET_BYTES
+ TRANSACTION_WORKING_BUDGET_BYTES

REMOVABLE_RESERVE_BYTES =
  ROUND_UP_256_MiB(
    max(
      1_GiB,
      ceil(BASE_REQUIRED_BYTES * 10%)
    )
  )

USB_REQUIRED_BYTES =
  BASE_REQUIRED_BYTES
+ REMOVABLE_RESERVE_BYTES

USB_PASS =
  MEASURED_USABLE_BYTES >= 14_GiB
  AND
  MEASURED_USABLE_BYTES >= USB_REQUIRED_BYTES
```

All arithmetic must use integer bytes with overflow/range checks.

### 6.2 Target artifact

```text
TARGET_ARTIFACT_BYTES=approved release exact archive size
```

For the current target this remains exactly `835309535`.

### 6.3 Predecessor recovery budget

This value is not global and is not per-user.

It is bound to the exact transition:

```text
expected predecessor -> approved target
```

Release qualification must use the same predecessor recovery encoding as the product implementation
and measure the generated recovery artifact. The committed budget is:

```text
MEASURED_EXPORT_BYTES=<qualification evidence>

PREDECESSOR_RECOVERY_BUDGET_BYTES =
ROUND_UP_256_MiB(
  max(
    ceil(MEASURED_EXPORT_BYTES * 110%),
    MEASURED_EXPORT_BYTES + 256_MiB
  )
)
```

The policy must also contain the exact `expected_predecessor_image_ref`; runtime rejects any mismatch.

### 6.4 HA data backup budget — runtime dynamic

Canonical production HA persistent source:

```text
/var/lib/n3wfc4-homeassistant
container target=/config
```

At PREPARE, the privileged host side performs a read-only measurement of the production HA data tree.
It must not follow symlinks outside the production root and must fail closed on unsupported external
persistent state.

Let:

```text
HA_DATA_MEASURED_BYTES=<runtime apparent bytes of supported backup scope>
```

Then:

```text
HA_DATA_GROWTH_MARGIN_BYTES =
max(
  512_MiB,
  ceil(HA_DATA_MEASURED_BYTES * 25%)
)

HA_DATA_BACKUP_BUDGET_BYTES =
ROUND_UP_256_MiB(
  max(
    1_GiB,
    HA_DATA_MEASURED_BYTES + HA_DATA_GROWTH_MARGIN_BYTES
  )
)
```

This budget is a preflight/admission estimate. It does not replace actual backup verification.

The runtime must remeasure at INSTALL revalidation. If the requirement grows beyond the bound USB's
available capacity, installation stops before U9.

### 6.5 Transaction working budget

```text
TRANSACTION_WORKING_BUDGET_BYTES =
ROUND_UP_256_MiB(
  max(
    512_MiB,
    ceil(TARGET_ARTIFACT_BYTES * 10%)
  )
)
```

This budget covers transaction metadata, temporary atomic-write files, checksums, bounded self-test
and implementation workspace. Primary target/predecessor/backup payload bytes are counted separately
and must not be double-counted.

### 6.6 Reserve budget

The removable-media reserve is a fixed product rule, not a fixed byte constant:

```text
REMOVABLE_RESERVE_BYTES =
ROUND_UP_256_MiB(
  max(
    1_GiB,
    ceil(BASE_REQUIRED_BYTES * 10%)
  )
)
```

This mirrors the project's existing evidence-based preference for a floor + proportional reserve,
while keeping removable-media accounting separate from the historical internal P5 reserve.

## 7. Three capacity checkpoints

### Checkpoint A — PREPARE / before USB insertion

Read-only only:

- bind approved target;
- bind exact expected predecessor;
- read/validate policy V2;
- measure current HA data;
- compute `USB_REQUIRED_BYTES`;
- compute user-facing recommended nominal USB size.

No USB erase and no U2+.

### Checkpoint B — immediately before and after format

Immediately before destructive format:

- recompute dynamic HA data input;
- prove same candidate;
- prove same target/predecessor;
- reject before wipefs if the candidate cannot plausibly satisfy the current requirement.

After ext4 format:

- measure real usable bytes;
- recompute the current requirement;
- require both the 14 GiB hard floor and full formula PASS.

Only then may U2 be accepted and target download begin.

### Checkpoint C — INSTALL revalidation before U6/U7/U9

Before INSTALL proceeds:

- remeasure HA data;
- recompute required capacity;
- inspect actual free bytes on the bound USB;
- account for target already stored;
- fail closed if predecessor + HA backup + working/reserve headroom is no longer sufficient.

After predecessor export and actual HA backup creation, U8 uses actual verified archive sizes and real
free space. U9 remains forbidden unless recovery assets are complete and capacity still passes.

Thus an underestimate cannot become a destructive internal-image deletion.

## 8. User-facing USB size recommendation

The UI must not expose GiB accounting internals as the primary instruction.

Compute:

```text
REQUIRED_FOR_RECOMMENDATION =
max(
  USB_REQUIRED_BYTES,
  14_GiB
)

NOMINAL_TIER_PASS(size_gb) =
  floor(size_gb * 1_000_000_000 * 90%) >= REQUIRED_FOR_RECOMMENDATION
```

Choose the smallest passing tier from:

```text
32, 64, 128, 256, 512, 1024 GB
```

If no tier passes, expose a bounded unsupported-capacity error rather than inventing a size.

32 GB is therefore the minimum UI recommendation, not a hard-coded admission rule. A smaller device
may only be accepted if the real post-format measured capacity and full formula pass, but normal product
guidance starts at 32 GB to reduce edge-case failures.

Frozen primary copy:

```text
请插入一个可清空的 {RECOMMENDED_USB_SIZE_GB} GB 或更大容量 U 盘。
系统会先检查 U 盘是否合适，在你确认前不会清除任何数据。
```

Capacity failure:

```text
U 盘容量不足。
请插入一个 {RECOMMENDED_USB_SIZE_GB} GB 或更大容量 U 盘。
```

Candidate confirmation copy:

```text
已检测到：{MODEL} · {DISPLAY_CAPACITY_GB} GB
清空后将用于保存升级文件和恢复数据。
```

Destructive action label:

```text
清空 U 盘并准备升级
```

The destructive action remains a separate explicit user action after insertion and candidate display.

## 9. Public status schema delta

`OtaRuntimeSnapshot` / `OtaStatus` must add bounded public fields:

```text
usb_required_bytes_or_null
usb_recommended_nominal_gb_or_null
usb_capacity_check_state
user_message_code_or_null
```

Allowed public capacity states:

```text
NOT_CALCULATED
RECOMMENDATION_READY
CANDIDATE_PENDING
CANDIDATE_CAPACITY_INSUFFICIENT
CANDIDATE_READY_FOR_CONFIRMATION
FORMATTED_CAPACITY_PASS
CAPACITY_REQUIREMENT_CHANGED
```

Raw USB serial/WWN, private host paths, backup paths and detailed private capacity evidence remain
outside MQTT/public status.

Manager presentation may render the frozen Chinese copy from the enumerated message code + numeric
recommended tier. MQTT must not accept arbitrary host-generated HTML or shell-derived text.

## 10. Prepare-state durability and current-live migration

The prepare state schema must gain an additive capacity snapshot containing at least:

```text
capacity_policy_schema
target_artifact_bytes
predecessor_recovery_budget_bytes
ha_data_measured_bytes
ha_data_backup_budget_bytes
transaction_working_budget_bytes
removable_reserve_bytes
usb_required_bytes
recommended_nominal_usb_gb
calculated_at_unix
```

For new transactions this snapshot is created during PREPARE.

The existing live U1 transaction predates KF-147 and has no capacity snapshot. Source/live repair must
support a one-time additive backfill:

```text
EXISTING_TRANSACTION_RESET=false
PREPARE_REPLAY=false
USB_REINSERT=false
CANDIDATE_RESELECTION=false
PHASE_CHANGE=false
CONFIRMATION_CONSUMED_CHANGE=false
```

The repaired host daemon may read the existing U1 transaction + current candidate, load policy V2,
perform read-only dynamic capacity measurement, and atomically add the missing capacity snapshot.
Failure leaves the transaction at U1 and keeps destructive confirmation blocked.

## 11. A1/deployment contract repair

The R7A A1 source authority must add:

```text
infra/n3w-t1/upgrades/homeassistant-2026.10.4-host-release-policy.json
  -> /etc/n3w-t1-ota/homeassistant-release-source.json
```

Required deployment properties:

```text
owner=root
group=root
mode=0644
symlink=false
byte_exact_repository_asset=true
```

A1 source validation must fail if the policy asset is absent from `SOURCE_DESTINATIONS` or from
the package source-authority manifest.

Post-install validation must read back and SHA-256 compare both:

- `approved-homeassistant.json`;
- `homeassistant-release-source.json`.

The host daemon must not become active for destructive preparation when either authority is absent or
cross-binding fails.

## 12. Cross-binding requirements

Policy V2 must exact-bind to the approved manifest and current transaction:

```text
release_identity
target_archive_sha256
target_archive_size_bytes
expected_predecessor_image_ref
```

The approved manifest remains the update approval/compatibility authority.
The host release policy is the fixed transport/capacity execution authority.
Neither document may silently override the other.

## 13. Required source files for repair

Expected HomeAssistant source-repair surface:

```text
tools/n3w_t1_core_updater_ha_prepare_host.py
tools/n3w_t1_core_updater_ha_prepare.py
tools/n3w_t1_core_updater_ha_daemon.py
tools/n3w_t1_core_updater_ha_usb_media.py

host/greenhouse-manager/src/greenhouse_manager/runtime/t1_ota_manager.py
host/greenhouse-manager/src/greenhouse_manager/runtime/ha_update.py

infra/n3w-t1/upgrades/homeassistant-2026.10.4-host-release-policy.json
tools/execution_packages/n3w/r7a/host_a1_live_activation/executor.py
tools/execution_packages/n3w/r7a/host_a1_live_activation/manifest.json

tests/tools/test_n3w_t1_core_updater_ha_prepare_host_r7a.py
tests/tools/test_n3w_t1_core_updater_ha_prepare_r7a.py
tests/tools/test_n3w_t1_core_updater_ha_ipc.py
manager OTA/update-surface tests
A1 package/deployment tests
```

A small pure capacity helper module may be added if it reduces duplication, but the repair must not
rewrite Generic V2 or broaden Manager privilege.

Expected `hahub.top` source-repair surface:

```text
hahub-frp/server-integration/default.conf
hahub-frp/server-integration/docker-compose.yml (only if service-network wiring needs explicitness)
deployment/verification documentation or script
```

No OTA binary is committed to that repository.

## 14. Required tests

At minimum:

1. Policy V1 fixed four-budget schema is rejected by repaired production path.
2. Policy V2 exact schema accepted.
3. Wrong origin / query / fragment / redirect rejected.
4. Target size/SHA/release/predecessor binding drift rejected.
5. HA data budget formula boundary tests.
6. Integer overflow/negative/boolean/oversize inputs fail closed.
7. Working and reserve formula rounding tests.
8. Nominal 32/64/128/256... tier mapping boundaries.
9. 14 GiB measured floor remains independent from recommendation.
10. Dynamic requirement growth between PREPARE and confirm blocks before wipefs.
11. Dynamic requirement growth before INSTALL blocks before U9.
12. A1 package cannot PASS without policy source asset.
13. A1 deployed policy byte-exact readback.
14. Existing U1 prepare-state backfill preserves transaction/candidate/confirmation state.
15. Manager public projection exposes recommended tier without raw serial/private path.
16. Candidate confirmation remains a separate action from PREPARE.
17. Existing Manager/Broker/HA identity and DynSec regression suites remain green.
18. `hahub.top` Nginx config test proves exact `ota.hahub.top` route does not fall through to wildcard FRP.
19. Published artifact HEAD/GET Content-Length, byte count and SHA-256 match the repository authority before live T1 download.

## 15. Live repair and authorization boundary

KF-147 source repair and CI do not authorize live changes.

Later live stages must be separated:

```text
A. OTA_ORIGIN_LIVE_PUBLICATION
   - deploy exact ota.hahub.top Nginx route
   - publish exact 2026.10.4 artifact
   - verify external HTTPS size/SHA
   - no T1 mutation

B. T1_KF147_LIVE_POLICY_REPAIR
   - install exact policy V2
   - install repaired source/daemon as authorized
   - preserve current U1/candidate
   - backfill capacity snapshot
   - fresh read-only destructive preflight

C. NEW_CONFIRM_USB_ERASE_AUTHORIZATION
   - only after A+B PASS
```

Because KF-147 changes the destructive eligibility contract materially, the earlier authorization:

```text
N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_BOUNDARY_B_CONFIRM_USB_ERASE_20261109_01
```

must not be reused after source/live repair.

Disposition:

```text
OLD_CONFIRM_AUTHORIZATION=SUPERSEDED_UNCLAIMED
CLAIMED=false
CONSUMED=false
ARTIFICIAL_CONSUMPTION=false
```

A fresh explicit destructive authorization is required after the repaired preflight.

## 16. Closure

```text
KF147_SOURCE_DESIGN=CLOSED
RELEASE_SOURCE_SELECTED=true
RELEASE_SOURCE=https://ota.hahub.top
CAPACITY_MODEL=HYBRID_DYNAMIC
UI_USB_SIZE_GUIDANCE=DYNAMIC_STANDARD_NOMINAL_TIER

SOURCE_REPAIR_REQUIRED=true
OTA_ORIGIN_SOURCE_REPAIR_REQUIRED=true
LIVE_OTA_ORIGIN_MUTATION_REQUIRED_LATER=true
LIVE_T1_REPAIR_REQUIRED_LATER=true

CURRENT_LIVE_USB_MUTATION=false
CURRENT_LIVE_T1_MUTATION=false
MERGE=false

NEXT_STAGE=KF147_SOURCE_REPAIR
NEXT_GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_HOST_RELEASE_POLICY_SOURCE_REPAIR_20261109_01
```
