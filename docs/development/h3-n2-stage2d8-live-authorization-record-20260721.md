# H3/N2 Stage 2D-8 Live Authorization Record

## Authorization status

The operator confirmed authorization to begin Stage 2D-8 development and to prepare a later isolated-device acceptance run.

This confirmation authorizes:

- creation of a new Stage 2D-8 development branch from the accepted Stage 2D-7 head;
- source, host model, compile-only firmware, CI, protocol, evidence, recovery, and operator-command development;
- preparation of read-only inspection commands for one dedicated test board;
- preparation of a temporary isolated Broker and test-only NVS plan.

It does not act as a blanket persistent-write grant.

The following operations still require separate one-shot, generation-bound authorization after read-only inspection has produced exact generations:

1. `PREPARE_CANDIDATE`;
2. `ACTIVATE_PROFILE`;
3. `CLEANUP_TEST_STATE`.

Each operation must bind the exact active generation, exact candidate generation, operation name, test run identifier, firmware commit, configuration digest, Broker configuration digest, and a unique authorization-record digest.

## Development base

- Stage 2D-7 accepted head: `ab04d31032403869379d976cd9f250fb3f144f7d`
- Stage 2D-8 branch: to be created separately; Stage 2D-7 remains unchanged.

## Live execution prerequisites

Before any real-board connection, NVS open, Broker connection, flash, or runtime write, the execution record must identify:

- dedicated test board identifier;
- serial port or physical connection path;
- isolated Wi-Fi/AP identity;
- temporary Broker configuration digest and local secret-file locations;
- test-only NVS partition label and namespace;
- rollback firmware image and digest;
- test firmware image and digest;
- initial read-only persistent state;
- exact active and candidate generations;
- operator authorization record for the next single write.

No production Home Assistant, Mosquitto, greenhouse-manager, M401A, T1, node topics, credentials, NVS namespace, or eFuse key may be used.
