# N3-W T1 E03 successor recovery read-only preauth STOP — KF-137

Date: 2026-10-30

~~~text
TASK=N3W_T1_E03_SUCCESSOR_RECOVERY_READONLY_PREAUTH_20261030_01
PR725_HEAD=614c08a397462850f0167b77c9da45ae69a323ad
PR739_HEAD_AT_STOP=e1483c66bbd6e8b0f08c540980ef4e666c15e6b6
PR740_HEAD=ff2904bcdedbae6651cbfe92104b12ad47d33903
MANAGER_TAR_SIZE_BYTES=62681088
PORTABLE_IDENTITY_SHA256=52c92c74648b657b05f7748014e0df4a0e406ae40e6d8a3201ff10633ea0d588
CONFIG_DIGEST=sha256:089153fa4bbc823a1357427083f23ef96933a119c6ae150c143b62d7b40859e4
PREDECESSOR_FRESH_REBIND=PASS
PREDECESSOR_SHA256=cb5e542a958886880b98d73742595694b93d3f4f16f83765e0fc3fc69d9a1bc8
HOST_BINDING_SHA256=550e4fa9e89ae98848d873823ad4c5d352275647be52e4f693b7dd58ae72a8da
PREAUTH_STATUS=STOP
PREAUTH_REASON=manager_image_count_invalid
PREAUTH_EXIT_CODE=3
T1_COMPOSE_SHA256=9ea58161d5f8e24233bacbfe1f31edd5f6f6c62c272271823788c0c5b59e8357
T1_MANAGER_IMAGE_SOURCE=GH_MANAGER_IMAGE_ENV_INDIRECTION
T1_MANAGER_IMAGE_LINE_COUNT=1
SOURCE_FALSE_STOP=CONFIRMED
LIVE_CONFIGURATION_DRIFT=false
SUCCESSOR_AUTHORIZATION_CLAIMED=false
T1_MUTATION=false
COMPOSE_MUTATION=false
SERVICE_STOP_START=false
DOCKER_LOAD_TAG_RMI=false
BOARD_ACCESS=false
LIVE_RECOVERY=false
MERGE=false
KF137=OPEN
PR740_SOURCE_REPAIR_CLOSURE=REOPENED_BY_LIVE_PREAUTH_FALSE_STOP
READONLY_PREAUTH=CANNOT_PASS_UNTIL_SOURCE_REPAIR
NEXT_ONE_GATE=N3W_T1_E03_SUCCESSOR_RECOVERY_COMPOSE_ENV_AUTHORITY_SOURCE_REPAIR_20261030_01
AUTO_EXECUTE_NEXT_GATE=false
~~~

## Root cause

The real fresh-product Compose contains one Manager image entry:

    image: "${GH_MANAGER_IMAGE:?GH_MANAGER_IMAGE required}"

The PR #740 successor rewrite_manager_image() implementation assumes that the raw Compose YAML contains one whitespace-free literal image reference and then compares that literal directly with the predecessor image. The valid product expression therefore fails before preauthorization can finish.

Fresh-product bootstrap intentionally writes GH_MANAGER_IMAGE into /etc/n3wfc4/docker-compose.env. The raw Compose YAML references that variable. The successor implementation models only the YAML file as the mutable deployment authority, so its model does not match the deployed product.

This is a source false-STOP, not T1 configuration drift. The old executor carried the same raw-YAML rewrite assumption but the earlier cross-store image-ID false STOP occurred before this path was reached.

## Required repair boundary

- Preserve the product GH_MANAGER_IMAGE env indirection; do not hardcode the target image into production Compose YAML as a workaround.
- Treat Compose YAML plus docker-compose.env as the deployment input set.
- Require exactly one GH_MANAGER_IMAGE assignment in the env authority.
- Freeze env-before and env-candidate SHA256; candidate may change only GH_MANAGER_IMAGE from predecessor to target.
- Validate before/candidate rendered Compose and require the only semantic delta to be the Manager image.
- Extend durable transaction, operation intent, resume and rollback to cover env before/after/unknown.
- Unknown Compose YAML or unknown Compose env must BLOCK with no write.
- Rollback may restore env-before only after exact candidate env write is proven for this transaction.
- Release/deployment binding must explicitly cover both deployment inputs instead of overloading a field that means only the YAML file hash.
- Add regression coverage using the exact fresh-product variable form above and repeat independent source review before live preauth retry.

## Stop boundary

The read-only preauth gate is not PASS. It stopped before successor authorization claim and before any product mutation. No service stop/start, Compose or env write, Docker load/tag/rmi, board access, live recovery or merge occurred.
