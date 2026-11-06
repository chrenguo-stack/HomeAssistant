# N3-W T1 Core Updater — Home Assistant storage policy review preexecution

Date: 2026-11-05

## Gate

~~~text
TASK=N3W_T1_CORE_UPDATER_HOMEASSISTANT_STORAGE_POLICY_REVIEW_20261105_01
STATE=READONLY_EVIDENCE_PREPARED

P5_SOURCE_HEAD=8310804a222676aba78334f3c0fd291da636242d
P5_CI=13_OF_13_SUCCESS
PR787=OPEN_DRAFT
LIVE_HA_APPLY_AUTHORIZED=false

T1_ACCESS=READONLY_WHEN_EXECUTED
T1_MUTATION=false
PERSISTENT_T1_FILE_WRITE=false
TEMPORARY_SCRATCH_WRITE=true
SERVICE_RESTART=false
IMAGE_LOAD=false
UPDATER_APPLY=false
UPDATER_ROLLBACK=false
CREDENTIAL_MUTATION=false
BOARD_ACCESS=false
MERGE=false
~~~

## Why this gate exists

ADR-0009 already separates three capacity questions:

~~~text
MASTER_BUILD_WORKSPACE_REQUIREMENT
PRODUCT_RUNTIME_MIN_FREE_REQUIREMENT
UPGRADE_ROLLBACK_WORKSPACE_REQUIREMENT
~~~

The historical R8 `MIN_POST_PEAK_FREE_BYTES=5 GiB` belongs to the bounded
fresh-install/master-build lineage. The R8 storage remediation design explicitly
states that exactly 5 GiB has no quantitative derivation from T1 measurements and
must not be claimed as the product physical minimum.

P5 initially reused that historical reserve as an extra safety gate. This review
does not lower it merely to force PASS. It first collects real T1 storage evidence,
then defines an upgrade-specific workspace rule separately from the product-runtime
minimum-free rule.

## Read-only evidence

The versioned probe records:

- actual Docker/containerd image-store authority;
- root/staging/Docker/image-store total, used and free bytes;
- inode totals/free counts;
- current Broker/Manager/Home Assistant container IDs and stable runtime state;
- current service image sizes;
- container writable-layer sizes;
- allocated/apparent size of each writable bind mount;
- HA state root, Manager state roots, Broker data root;
- core-updater state root;
- `/var/log` and apt-cache usage;
- `docker system df` read-only summary;
- before/after unit/container state equality.

The public result contains only numeric capacity summaries and image/bind sizes.
The full remote report stays in the operator-local private evidence root.

## No conclusion before evidence

Until the real T1 read-only run is reviewed:

~~~text
PRODUCT_RUNTIME_MIN_FREE_REQUIREMENT=UNFROZEN
UPGRADE_ROLLBACK_WORKSPACE_REQUIREMENT=UNFROZEN
HISTORICAL_5_GIB_AS_PRODUCT_MINIMUM=false
LIVE_HA_APPLY_AUTHORIZED=false
~~~

After evidence, the intended P5 capacity model is:

~~~text
FREE_BEFORE_UPGRADE
>=
EXACT_TARGET_ARCHIVE_STAGING
+ TARGET_IMAGE_IMPORT_PEAK
+ ROLLBACK_COMPATIBLE_PREDECESSOR_RETENTION
+ PRODUCT_RUNTIME_MIN_FREE_REQUIREMENT
~~~

The terms must be bound to measured/verified bytes rather than a copied historical
constant.

## Execution boundary

Required confirmation:

~~~text
READONLY HA STORAGE POLICY BASELINE: YES
~~~

A PASS from this gate authorizes only policy analysis. It does not authorize
Home Assistant live apply.
