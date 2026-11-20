# N3-W T1 U11 R40 post-claim supervision false-STOP / source repair closure — 2026-11-16

```text
TASK=N3W_T1_U11_R40_POSTCLAIM_SUPERVISION_FALSE_STOP_SOURCE_REPAIR_CLOSURE_20261116
PR=807
MAIN_HEAD=3e7faf258d670c9eaf3be6ede9bbb02df2ac009d
R40_GRANT_HEAD=7649743b27f125c37ce360dafe5a3455ef10bbdc
R40_EXECUTION_ID=u11-r40-live02-20261116T063426Z
R40_RESULT=STOP_POSTCLAIM
R40_RC=2
R40_AUTHORIZATION_CLAIMED=true
R40_AUTHORIZATION_CONSUMED=true
R40_REPLAY_PERMITTED=false
R40_RECOVERY_REQUIRED=true

LIVE_TRANSACTION_PHASE=U10_INTERNAL_PREDECESSOR_CAPACITY_RELEASED
LIVE_TRANSACTION_SHA256=c0dc58ebcfcd2876aec5bfcf556723ae779106803e19df5541b1847fc494bba3
USB_PHASE=U10_INTERNAL_PREDECESSOR_CAPACITY_RELEASED

TARGET_IMAGE_LOAD=true
COMPOSE_BINDING_MUTATION=true
SERVICE_MUTATION=false
TRANSACTION_MUTATION=false
USB_MUTATION=false
U11_TRANSITION=false
U12_PLUS=false

ROOT_CAUSE=PROVEN
KF162=OPEN
SOURCE_REPAIR_HEAD=155f9a7b62d6b758fb87c109b3ffbf54aa5614c7
SOURCE_REPAIR_CI=16_OF_16_SUCCESS
R39_PRECLAIM_COVERAGE_GAP=true
LIVE_RECOVERY_AUTHORIZED=false
```

## Physical result

R40 Attempt 01 was a local wrapper SAFE STOP before T1 access: the wrapper created a log file inside the evidence root before executor start, violating the executor's required-empty evidence-root contract. No R40 claim or product mutation occurred.

Corrected Attempt 02 reached the real T1. Embedded R39 preclaim passed; R40 was then durably claimed and consumed. The exact Home Assistant target image was loaded and verified, and the production Home Assistant Compose binding was changed from the predecessor reference to `local/n3w-homeassistant:2026.10.4-5881590f`.

The executor then returned `STOP_POSTCLAIM` before U11 durable persistence. Host transaction and USB phase both remain exact `U10_INTERNAL_PREDECESSOR_CAPACITY_RELEASED`. Broker remains running, Manager and Home Assistant remain stopped, and the services owner remains failed/quiesced.

## Read-only forensic attribution

The T1 production services owner includes the repository-owned drop-in:

`/etc/systemd/system/n3wfc4-services-activation.service.d/95-n3w-ha-ota.conf`

The drop-in resets and replaces `ExecStart` / `ExecStop` to add `/opt/HomeAssistant/infra/n3w-t1/production/docker-compose.ha-ota.yml`.

The old `LocalHost._service_unit()` read raw `systemctl cat` output and required exactly one base `ExecStart=` and one base `ExecStop=`. It did not apply systemd reset semantics. Therefore the legitimate base + empty-reset + replacement sequence was misclassified as `services_supervision_contract_drift`.

U11 performs this supervision check inside `_require_prestart_owner_state()` before invoking `systemctl start`. Real-T1 evidence matches that order:
- no new services-owner journal entry in the R40 failure window;
- no new Docker container event in the same window;
- services-owner `ExecMainStartTimestamp` remains from the prior runtime;
- no target Home Assistant container was created;
- historical Manager exit 137 is not the R40 cause and reports `OOMKilled=false`.

## R39 false-PASS coverage gap

R39 checked the durable U10 transaction, USB mirror/recovery assets, owner quiescence, Broker/Manager identities, target/predecessor image absence and internal capacity. It did not validate the effective HA-OTA services-owner command before the future claim.

Therefore the R39 PASS did not prove the one precondition that failed post-claim. The historical R39 executor remains unchanged. A successor recovery gate must add that exact read-only check before any new recovery claim.

## Source repair

Source authority:

`155f9a7b62d6b758fb87c109b3ffbf54aa5614c7`

Changes are bounded to:
- `tools/n3w_t1_core_updater_host.py`;
- `tools/n3w_t1_core_updater_ha_u11_host.py`;
- `tests/tools/test_n3w_t1_core_updater_ha_u11_host.py`.

The common host helper now resolves the effective `ExecStart` / `ExecStop` after reset semantics. U11 supplies and requires the exact HA-OTA overlay commands. Regression tests include the real base + reset + replacement shape and reject wrong effective commands.

CI:

```text
TOTAL=16
SUCCESS=16
FAILED=0
RUNNING=0
HA_TARGET_BINDING_RUN=43825253517
MANAGER_A_TO_B_RUN=43825253528
```

## Recovery boundary

R40 is consumed/no-replay and must never be retried.

The next task is not a direct service restart. It is a successor recovery gate designed from the exact partial state:
- target image already present;
- target binding already published;
- services not started by R40;
- durable host/USB phase still U10;
- R40 failure ledger present and consumed/no-replay;
- Broker continuity preserved.

The successor must first perform a fresh read-only preflight that verifies all above facts plus the exact effective systemd supervision contract. Live service start, USB U11 metadata, host U11 transaction, U12 acceptance and U13 commit/rollback remain outside the current authorization.

```text
NEXT_ONE_GATE=U11_POST_R40_SUCCESSOR_RECOVERY_GATE_DESIGN_AND_READONLY_PREFLIGHT
R40_REPLAY=false
LIVE_RECOVERY_AUTHORIZED=false
U12_AUTHORIZED=false
U13_AUTHORIZED=false
BOARD_ACCESS=false
MERGE=false
```
