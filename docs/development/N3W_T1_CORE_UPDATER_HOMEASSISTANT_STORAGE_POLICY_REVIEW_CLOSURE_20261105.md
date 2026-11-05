# N3-W T1 Core Updater — Home Assistant storage policy review closure

Date: 2026-11-05

## 1. Result

~~~text
TASK=N3W_T1_CORE_UPDATER_HOMEASSISTANT_STORAGE_POLICY_REVIEW_20261105_01

READONLY_EXECUTION_HEAD=9cf4fcee9512013ca99675b3b477cf77429bd669
READONLY_RESULT=PASS
READONLY_CI=13_OF_13_SUCCESS

T1_ACCESS=true
T1_MUTATION=false
PERSISTENT_T1_FILE_WRITE=false
SERVICE_RESTART=false
IMAGE_LOAD=false
UPDATER_APPLY=false
UPDATER_ROLLBACK=false
BOARD_ACCESS=false
RUNTIME_STATE_STABLE=true

HISTORICAL_FIXED_5_GIB_P5_RESERVE=RETIRED
P5_POST_PEAK_RESERVE_BYTES=1610612736
P5_POST_PEAK_RESERVE_GIB=1.5

PRODUCT_RUNTIME_MIN_FREE_REQUIREMENT=UNFROZEN_LONGITUDINAL_EVIDENCE_REQUIRED
LIVE_HA_APPLY_AUTHORIZED=false
MERGE=false
~~~

## 2. Real T1 baseline

The accepted read-only execution measured:

~~~text
FILESYSTEM_TOTAL_BYTES=14453903360
FILESYSTEM_USED_BYTES=8651415552
FILESYSTEM_FREE_BYTES=5785710592
FILESYSTEM_FREE_RATIO=40.03%

FILESYSTEM_TOTAL_INODES=903984
FILESYSTEM_FREE_INODES=644147
FILESYSTEM_FREE_INODE_RATIO=71.26%

STORAGE_BACKEND=containerd
STAGING_DOCKER_IMAGE_STORE_SAME_DEVICE=true
~~~

Current service image sizes:

~~~text
HOMEASSISTANT_IMAGE_BYTES=2448504642
MANAGER_IMAGE_BYTES=62859745
BROKER_IMAGE_BYTES=27541691
~~~

Mutable allocation used for the P5 reserve derivation:

~~~text
SELECTED_PERSISTENT_AND_MAINTENANCE_ALLOCATED_BYTES=118689792
CONTAINER_WRITABLE_LAYER_ALLOCATED_BYTES=55357440
OBSERVED_MUTABLE_ALLOCATED_BYTES=174047232
~~~

The selected persistent/maintenance set contains the HA state root, Manager state,
Broker data, updater state, /var/log and apt cache. Container writable layers are
counted separately and therefore not double-counted with writable bind storage.

## 3. Why 5 GiB is retired

ADR-0009 explicitly separates:

~~~text
MASTER_BUILD_WORKSPACE_REQUIREMENT
PRODUCT_RUNTIME_MIN_FREE_REQUIREMENT
UPGRADE_ROLLBACK_WORKSPACE_REQUIREMENT
~~~

The R8 fixed 5 GiB value was a conservative fresh-install/master-build constant.
The reviewed R8 design states that no quantitative derivation for exactly 5 GiB
was found and that it must not be treated as the product physical minimum.

Applying that constant directly to a one-component HA upgrade would reject useful
upgrade headroom without evidence that 5 GiB is needed by runtime or rollback.

## 4. P5 upgrade reserve derivation

P5 now uses a target-specific operational reserve:

~~~text
RAW_RESERVE =
max(
  1 GiB absolute floor,
  10% of measured filesystem total,
  8 * measured mutable allocated bytes
)

P5_POST_PEAK_RESERVE =
RAW_RESERVE rounded upward to the next 256 MiB
~~~

For the accepted T1 evidence:

~~~text
1 GiB floor=1073741824
10% filesystem=1445390336
8x mutable=1392377856

RAW_RESERVE=1445390336
ROUND_QUANTUM=268435456
P5_POST_PEAK_RESERVE_BYTES=1610612736
P5_POST_PEAK_RESERVE_GIB=1.5
~~~

This 1.5 GiB value is intentionally an upgrade-admission reserve. It is not
promoted to the lifetime product runtime minimum.

## 5. Upgrade/rollback workspace accounting

P5 admission is:

~~~text
FREE_BEFORE_UPGRADE
>=
EXACT_TARGET_ARCHIVE_BYTES
+ EXACT_TARGET_IMPORT_WORST_CASE_BYTES
+ P5_POST_PEAK_RESERVE_BYTES
~~~

The exact archive is frozen at:

~~~text
TARGET_ARCHIVE_BYTES=835309535
~~~

The exact target import worst-case value is not guessed from the current HA image.
P5 derives it from the downloaded exact target archive by summing the uncompressed
Docker-save regular-file member sizes before any T1 staging.

The predecessor HA image is already resident before the upgrade and remains
retained by Generic V2 for automatic/explicit rollback. The measured free-space
baseline already reflects those predecessor bytes. Adding the predecessor image
size again would double-count it.

With the measured current free space and the 1.5 GiB reserve:

~~~text
FREE_BEYOND_RESERVE_BYTES=4175097856
FREE_AFTER_ARCHIVE_RESERVATION_FOR_TARGET_IMPORT_BYTES=3339788321
CURRENT_HA_IMAGE_BYTES=2448504642
TARGET_IMPORT_ALLOWANCE_VS_CURRENT_HA=136.4%
~~~

The admission therefore permits an exact target import worst-case up to about
3.11 GiB while retaining the 1.5 GiB safety reserve. The current HA image is about
2.28 GiB, so the model provides about 36% growth allowance versus the current image
without relying on that approximation for final PASS/FAIL.

## 6. Post-apply guard

After a successful updater apply and removal of the temporary remote staging
directory, P5 re-reads the real storage authority.

Required:

~~~text
POST_CLEANUP_FREE_BYTES >= 1610612736
~~~

Failure of this post-cleanup reserve check is not converted into a second apply or
a blind rollback. It becomes a STOP/recovery decision boundary.

## 7. Product runtime minimum remains separate

One point-in-time baseline cannot establish long-term Home Assistant database,
log, history and state growth. Therefore:

~~~text
PRODUCT_RUNTIME_MIN_FREE_REQUIREMENT=UNFROZEN_LONGITUDINAL_EVIDENCE_REQUIRED
~~~

This is deliberate and consistent with ADR-0009. Future product-runtime threshold
work must use longitudinal evidence and must not reuse P5's 1.5 GiB upgrade reserve
as a lifetime product promise.

## 8. Versioned policy authority

~~~text
infra/n3w-t1/upgrades/homeassistant-2026.10.4-storage-policy.json
~~~

The policy binds the accepted evidence numbers, derivation formula, frozen target
identity and the explicit statement that live HA apply remains unauthorized.

## 9. Source repair closure

The evidence-bound P5 storage-policy repair is closed on exact executable source:

~~~text
P5_STORAGE_POLICY_REPAIR_SOURCE_HEAD=a5a9260e5dd274cca55ddd106721be3159e051ec
PR788_STATE=OPEN_DRAFT
PR788_MERGEABLE=true
PR788_EXACT_HEAD_CI=14_OF_14_SUCCESS

HA_TARGET_MANIFEST_BLOB_SHA=6966b4fe4d7620ccc436643cc840da9ae95e6010
STORAGE_POLICY_BLOB_SHA=01a5cec8877e2837504ed798e91ca552ab6f2a0e

GENERIC_V2_SOURCE_CHANGED=false
FROZEN_HA_TARGET_CHANGED=false
P5_APPLY_INVOCATION_COUNT_MAX=1
P5_EXPLICIT_ROLLBACK_ROUTE_COUNT=0
HISTORICAL_FIXED_5_GIB_EXECUTOR_LITERAL=false

P5_SOURCE_PREAUTHORIZATION=PREAUTH_READY
STORAGE_POLICY_REVIEW=CLOSED_PASS
~~~

The final source review confirmed that the fixed 5 GiB literal is absent from the
P5 executor, the exact HA target blob is unchanged, Generic V2 source is unchanged,
the executor still contains only one apply invocation and no explicit rollback
call, and the manifest still keeps live authorization false.

## 10. Next boundary

The next boundary is the explicit user decision whether to grant the one-shot P5
live Home Assistant apply authorization:

~~~text
N3W_T1_CORE_UPDATER_HOMEASSISTANT_2026_10_4_LIVE_APPLY_P5_20261105_01
~~~

Until that explicit authorization is granted:

~~~text
LIVE_HA_APPLY_AUTHORIZED=false
AUTHORIZATION_GRANTED=false
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
AUTO_EXECUTE_LIVE_APPLY=false
MERGE=false
~~~
