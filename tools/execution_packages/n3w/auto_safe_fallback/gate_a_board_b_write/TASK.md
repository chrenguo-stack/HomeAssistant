# N3-W auto safe fallback Gate A Board B exact write gate

## Purpose

Bind the physical Gate A test to the exact private application produced on 2026-09-29.

Frozen target:

- Board B public hardware identity SHA256: `3603345fb73de6f9286dc66db9f246ff73c42382b553af63b8d5813a933b69ee`
- partition-table SHA256: `6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca`
- application SHA256: `77b0fd6a98c3e837d3543eebdd30b86354790847d0c78cdab7e96f0d7d66a8ad`
- otadata SHA256: `7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f`

## Commands

`preflight` is read-only with respect to flash contents. It may reset Board B while using ROM/esptool probes. It verifies:

- exact private bundle manifest and application/otadata hashes;
- ESP32-C6 target;
- frozen Board B identity;
- 8 MB flash;
- Secure Boot disabled;
- Flash Encryption disabled;
- exact partition-table readback hash;
- esptool major version 5.

`write` requires a fresh preflight no older than 15 minutes and exact confirmation:

`N3W_GATE_A_BOARD_B_WRITE_AUTHORIZED`

The preflight is claimed and consumed before flash mutation. Replay is prohibited.

## Write scope

Only two regions may be written:

- `0x9000`: exact `ota_data_initial.bin`;
- `0x10000`: exact Gate A `firmware.bin`.

Explicitly prohibited:

- bootloader write;
- partition-table write;
- product NVS write;
- full flash erase;
- T1 mutation.

## Rollback boundary

This package intentionally does not perform rollback.

The currently available rollback authority remains the exact KF-099 artifact:

- artifact ID `10959875986`;
- archive SHA256 `56abb5267ee1786f77930837d6a660745ee64f320d1c6ad64aac7c852aa115cb`;
- application SHA256 `d0875ca692f7bd4349fd7d8bcdab69318e6c8b737b69a48f667b6e72cb89cb60`;
- otadata SHA256 `7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f`.

Rollback requires a new, separately reviewed and separately authorized one-shot write gate. Historical KF-099 write authorization must not be replayed.

## Sequencing

Repository/CI completion does not authorize Board B write.

Physical order remains:

1. T1 isolated-lab read-only preflight PASS;
2. T1 isolated-lab activation under explicit authorization;
3. Board B exact read-only preflight;
4. Board B Gate A write under explicit one-shot authorization;
5. Gate A timing sequence;
6. T1 isolated-lab cleanup;
7. separately authorized exact KF-099 rollback;
8. post-rollback evidence that the prior KF-099 pairing-WAIT baseline is restored.
