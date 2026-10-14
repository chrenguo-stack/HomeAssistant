# N3-W T1 Golden Master R2A/R2B Host Tooling Source Repair（2026-10-13）

TASK=
`N3W_T1_GOLDEN_MASTER_R2A_R2B_HOST_TOOLING_SOURCE_REPAIR_20261013_01`

## Result target

This source package closes the repository-only A2 gap identified by the focused review:

- add a deployable Golden Master build host wrapper;
- add a public-safe release manifest bound to exact payload/source/images/public tree;
- add a Golden Master-specific one-shot authorization ledger;
- add a host-side public Seal audit wrapper;
- keep real target-Armbian OS identity mutation blocked until R2C evidence.

The historical R8 authorization identity and apply path remain unchanged.

## Safety boundary

```text
SOURCE_MUTATION=true
T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
MERGE=false

R2C_TARGET_IDENTITY_ADAPTER_READY=false
REAL_SEAL_MUTATION_EXECUTABLE=false
```

The new Seal host wrapper deliberately refuses `seal` with
`target_identity_adapter_required`; it cannot consume a Seal authorization before the
target-specific adapter exists.
