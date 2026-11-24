# N3-W T1 OTA V1.3 R8V13-07 U10 live-repair read-only preflight physical PASS

Date: 2026-11-25

## Scope

This record archives the exact spare-T1 read-only evidence captured before any U10 live-repair mutation.

- Stage: `N3W_T1_CORE_STACK_OTA_V1_3_R8_PHYSICAL_ACCEPTANCE`
- Task: `R8V13-07`
- Transaction: `d86669e6d16bb9420191920bc2b02583e7f7207eff0b51ed3f9e6321f99389d4`
- Preflight: `tools/execution_packages/n3w/t1_ota_r8v13_07/N3W_T1_R8V13_07_U10_LIVE_REPAIR_READONLY_PREFLIGHT_20261124_01.sh`
- Physical mutation: false
- INSTALL replay: false

## Source binding

```text
PREFLIGHT_BLOB=87a564592f0204199be061d6c823b45e0936b889
PREFLIGHT_SHA256=c1a117208aad4ccc613885f233cc32efb4b609b86f1f2cf7530fc3d36a297886
PREFLIGHT_SOURCE_BINDING=PASS
EXPECTED_SOURCE_HEAD=a9b76d77c2a930a21089af7fe0cc814f4db60a9a
EXPECTED_ARTIFACT_ID=14939405227
EXPECTED_ARTIFACT_SHA256=9843b55453ba0025cbedae228c20e10da6b45b8284e559d2c8035876d98d42e5
EXPECTED_NEW_MANIFEST_SHA256=489aa375fda2b0fba76ee4e9bd30ab168ce9ee00feff05ee074af5b656d1eca8
EXPECTED_NEW_PYZ_SHA256=d7915bc3e42531a829ab22ecb74a7148878c3a2310313e4f1ac07acc8785185e
```

## Durable transaction and live binding

```text
TRANSACTION_BINDING=PASS
TARGET_BINDING_ENV=PASS
TX_FILE_SHA256=4c68793fb1909366aa9acee7c06b74f3bac12dfae8681b1c4a6407abd6d2bd44
COMPOSE_ENV_SHA256=8f4a73bfa8126f9e4ee993197cece40fddcdf140c994687a391014d627c0e8cc
LIVE_OLD_PYZ_SHA256=5208dadc14c2cf0024c0711de60ce0f70f5a19ea27de4e74f290d4c3c8bcfe0a
LIVE_LAUNCH_SHA256=955f0f69553f8f80639fab630dd23e23aec40d9e84a48f23536712701dbb1d05
LIVE_HA_REF=local/n3w-homeassistant:2026.10.0-0c73235a
LIVE_HA_ID=sha256:c261fa53f30508951833492ba2a19af6cfbb6aa8f2806b531d8f5c6599265306
ROLLBACK_WRITERS_QUIESCED=true
```

The live launch binding is the target-bound compose state. The frozen predecessor start binding remains:

```text
PREDECESSOR_START_LAUNCH_SHA256=67877cffd28b1c94de17f6b8eecabd1b579649f7e282fdfc65e4bcfcfd5fdc26
PREDECESSOR_HOMEASSISTANT=local/n3w-homeassistant:2026.10.4-5881590f
PREDECESSOR_HOMEASSISTANT_ID=sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365
MANAGER=local/greenhouse-manager:fresh-1cae18039eee
MANAGER_ID=sha256:c4bcb441de0554ebb20e3feb2b98a65cc435750539a2c951eb7be710ff191221
BROKER=local/n3w-mosquitto:2.1.2-3184566d
BROKER_ID=sha256:df265f1e2b2e3dc35d5eb194e698c598e01c5ebca370da307b34332f9bf0a563
```

## Recovery media and image state

```text
PREDECESSOR_IMAGE_PRESENT=false
PREDECESSOR_IMAGE_ID=absent
USB_MOUNT_TARGET=/mnt/n3w-ha-r8-predecessor
LIVE_MUTATION=false
INSTALL_REPLAY=false
RESULT=R8V13_07_U10_LIVE_REPAIR_READONLY_PREFLIGHT_PASS
```

This proves the exact predecessor image capacity release has already occurred, the target image is resident and bound, and the application writers are quiesced. Recovery must therefore continue the same durable transaction; INSTALL must not be replayed and a second transaction must not be created.

## Next gate

The next source task is to bind an exact U10 live-repair/recovery executor to the values above.

The executor may be implemented, tested, CI-sealed and independently reviewed under the existing source/test/CI/archive continuation authority. It must not be executed on the spare T1 until the live physical mutation scope is explicitly authorized.

Expected mutation scope after approval:

1. verify the exact transaction, env, image, USB and recovery-owner state above;
2. verify the successor recovery pyz artifact before publication;
3. atomically replace only `/opt/n3w-t1-core-updater/ha-recovery.pyz`;
4. invoke the existing `n3w-t1-ha-recovery-retry.service` against the same transaction;
5. require terminal recovery and healthy predecessor runtime;
6. never submit INSTALL, issue a new INSTALL authority, create a second transaction, format/delete USB data, perform Broker OTA, reboot the host, merge, release, or enter R8V13-08.

```text
PHYSICAL_PREFLIGHT=PASS
LIVE_REPAIR_MUTATION_AUTHORIZED=false
INSTALL_REPLAY_ALLOWED=false
SECOND_TRANSACTION_ALLOWED=false
R8V13_08_AUTO_ADVANCE=false
```
