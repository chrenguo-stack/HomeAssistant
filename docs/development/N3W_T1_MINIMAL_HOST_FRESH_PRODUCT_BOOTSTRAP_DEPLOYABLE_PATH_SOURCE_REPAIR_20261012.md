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


## Final source / CI / artifact closure

The deployable-path source gate has completed its source/CI work.

```text
PRODUCT_SOURCE_HEAD=d5a1be83aa5ab039696297ebdfa4ce787fe168ba
PRODUCT_SOURCE_TREE=73d720ccf88348d4dcc60e21f48c9a81048f3f30
EXACT_HEAD_WORKFLOW_COUNT=25
EXACT_HEAD_WORKFLOW_PASS_COUNT=25
ALL_EXACT_HEAD_CI=PASS

FRESH_BOOTSTRAP_DEPLOYABLE_RUN_ID=38194585872
FRESH_BOOTSTRAP_DEPLOYABLE_RUN_NUMBER=11
FRESH_BOOTSTRAP_DEPLOYABLE_CI=PASS

ARTIFACT_ID=11723440338
ARTIFACT_NAME=n3w-t1-fresh-bootstrap-deployable-d5a1be83aa5ab039696297ebdfa4ce787fe168ba
ARTIFACT_DIGEST=sha256:588e1d793c6a03193e6ecbb46fd809f44bfed45659cf00566a16cf1faf779f06
PAYLOAD_ARCHIVE_SHA256=5f79c883ba16d06e0bc5f89a36e829c43e3083ffd57e222d429baf1a8801d873
PAYLOAD_MANIFEST_SHA256=067c7d5af5d816cd8800de374cc6532126c2a3f6f7dfe37db915c784dc9459b4

FRESH_DEPLOYMENT_GATE=PASS
FRESH_LIVE_ADAPTER_PRECOMMIT_REHEARSAL=PASS
FRESH_BOOTSTRAP_INNER_BINDING=PASS
FRESH_BOOTSTRAP_DEPLOYABLE_POST_UPLOAD_BINDING=PASS

T1_ACCESS=false
LIVE_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
```

The source-repair gate is now `CLOSED_PASS`. This does **not** authorize live T1 bootstrap.

The next gate is an independent, read-only final review of this exact source head and exact deployable artifact:

```text
NEXT_ONE_GATE=
N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_EXACT_HEAD_ARTIFACT_FINAL_SOURCE_AND_EXECUTION_PATH_REVIEW_20261012_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
FRESH_BOOTSTRAP_LIVE_AUTHORIZATION_GRANTED=false
PR541_MERGE=false
```
