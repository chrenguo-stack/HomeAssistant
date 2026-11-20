# N3-W T1 U13B P3 distinct target source review — Home Assistant 2026.10.3

## Purpose

Prepare a distinct exact Home Assistant target for the first U13B rollback-mechanics physical acceptance without entering any T1 mutation.

```text
CURRENT_REAL_T1_HOMEASSISTANT=local/n3w-homeassistant:2026.10.4-5881590f
CANDIDATE_VERSION=2026.10.3
CANDIDATE_UPSTREAM_TAG=2026.10.3
CANDIDATE_UPSTREAM_SOURCE_COMMIT=1f214b8461dd1fbbd66e10765c6905f49d3c1d86
CURRENT_UPSTREAM_SOURCE_COMMIT=357cae5c598dfcd7a0ea7dc5b1facccd4ec6037b
MUTATION_PROFILE=IMAGE_ONLY_V1
ACCEPTANCE_ONLY_DISTINCT_TARGET=true
```

This is intentionally an acceptance target, not a recommendation to downgrade field devices.

## Compatibility review

The three managed Home Assistant storage contracts are identical at 2026.10.3 and 2026.10.4:

```text
core.config_entries=1.5
core.device_registry=3.4
core.entity_registry=1.23
```

The upstream source delta from 2026.10.3 to 2026.10.4 is four commits and six files:

- homeassistant/components/lutron_caseta/manifest.json
- homeassistant/const.py
- homeassistant/helpers/aiohttp_client.py
- pyproject.toml
- requirements_all.txt
- tests/helpers/test_aiohttp_client.py

No managed-storage implementation, MQTT contract or N3-W persistent binding authority is changed by that delta.

Machine-readable review:
`infra/n3w-t1/upgrades/homeassistant-2026.10.3-u13b-physical-compatibility-review.json`

Canonical review SHA-256:
`e1e950bd76e1b8154c43d5ff50cdbceceee0fc51bb68e20022a6189f16546dd0`

## Why 2026.11.0 is not used

The existing 2026.10.4 compatibility review already defers 2026.11.0 because `core.entity_registry` advances from minor version 23 to 24 with semantic migration. That exceeds the present IMAGE_ONLY_V1 rollback contract.

## Exact artifact requirement

The candidate is not usable until CI proves an exact Linux ARM64 GHCR manifest and produces:

- compressed Docker archive;
- archive SHA-256 and byte size;
- portable image identity;
- upstream index/manifest digests;
- exact local image tag;
- GitHub artifact ID and artifact digest.

The artifact workflow is:
`.github/workflows/n3w-u13b-p3-ha-2026-10-3-exact-artifact-ci.yml`.

## Boundaries

```text
T1_ACCESS=false
T1_MUTATION=false
USB_MUTATION=false
SERVICE_MUTATION=false
IMAGE_MUTATION=false
HA_DATA_MUTATION=false
NEW_CLEAN_OTA_MUTATION_AUTHORIZED=false
U13B_LIVE_EXECUTION_AUTHORIZED=false
CONTROLLED_ROLLBACK_MUTATION_AUTHORIZED=false
BOARD_ACCESS=false
MERGE=false
```

Successful artifact production permits only later repository-side target freezing. It does not authorize P3 live OTA.
