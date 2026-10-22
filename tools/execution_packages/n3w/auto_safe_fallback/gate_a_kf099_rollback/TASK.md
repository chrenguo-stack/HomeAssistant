# N3-W Gate A exact KF-099 rollback gate

## Purpose

Restore Board B from the temporary Gate A firmware to the exact KF-099 repaired image after the physical timing test.

This package exists because the historical KF-099 write authorization is already consumed and must never be replayed.

Frozen rollback authority:

- artifact ID: `10959875986`
- artifact name: `n3w-kf099-c578bcb-boardb-exact-source`
- ZIP SHA256: `56abb5267ee1786f77930837d6a660745ee64f320d1c6ad64aac7c852aa115cb`
- application SHA256: `d0875ca692f7bd4349fd7d8bcdab69318e6c8b737b69a48f667b6e72cb89cb60`
- otadata SHA256: `7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f`
- Board B hardware identity SHA256: `3603345fb73de6f9286dc66db9f246ff73c42382b553af63b8d5813a933b69ee`
- partition-table SHA256: `6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca`

## Commands

`preflight` validates the exact rollback ZIP and performs read-only ROM/flash identity checks. It may reset the board but does not write flash.

`write` requires a fresh preflight and exact one-shot confirmation:

`N3W_GATE_A_KF099_ROLLBACK_WRITE_AUTHORIZED`

Historical token `KF099_C578BCB_BOARD_B_WRITE_AUTHORIZED` is not accepted.

## Write scope

Only:

- `0x9000` exact KF-099 otadata;
- `0x10000` exact KF-099 application.

Never:

- bootloader;
- partition table;
- product NVS;
- full-chip erase;
- T1.

## Post-rollback acceptance

The expected restored baseline is the previously observed KF-099 pairing WAIT / `repair_intent_required` state, not an assumed normal Direct MQTT product baseline.

After rollback, evidence must show the exact image/Board binding and the prior pairing-WAIT behavior without creating a new pairing session or changing durable registration/credential state.
