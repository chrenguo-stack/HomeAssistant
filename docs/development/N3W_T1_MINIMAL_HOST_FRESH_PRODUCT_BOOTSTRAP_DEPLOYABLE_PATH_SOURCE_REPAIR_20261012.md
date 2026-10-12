# N3-W T1 minimal-host fresh product bootstrap deployable path source repair（2026-10-12）

## Gate

```text
TASK=N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_DEPLOYABLE_PATH_SOURCE_REPAIR_20261012_01
SCOPE=GITHUB_AND_HOST_ONLY
LIVE_T1_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
```

## R1 foundation

The first source repair removes three blockers before adding the live adapter/payload:

1. add `docker-compose.fresh.yml`, whose Manager image must be injected from an exact fresh image lock instead of the historical S20 tag;
2. make the deployment gate accept a fresh image-lock schema with a source-head-bound Manager image while preserving the historical S20 contract for legacy evidence;
3. harden fresh payload tar validation/extraction so symlink, hardlink, device/FIFO and other special members are rejected before extraction.

The historical `docker-compose.yml` and S20 image-lock remain untouched and are not eligible for the fresh-bootstrap live path.

```text
R1_SOURCE_COMMITTED=true
R1_CI=PENDING
LIVE_T1_MUTATION=false
```

The next commit in the same gate adds the repository-owned live FreshInstallerAdapters implementation and a fresh-bootstrap-specific deployable payload workflow.
