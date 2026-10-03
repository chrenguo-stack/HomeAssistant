# N3-W auto safe fallback Gate A isolated T1 lab transaction

## Purpose

Prepare and run the temporary TLS MQTT endpoint used only by Gate A timing validation.

This package is bound to the exact private Gate A build:

- application SHA256: `77b0fd6a98c3e837d3543eebdd30b86354790847d0c78cdab7e96f0d7d66a8ad`
- otadata SHA256: `7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f`
- broker port: `18883`
- TLS verification name: `n3w-gate-a.invalid`

Private IP addresses, MQTT credentials, TLS private material and local paths remain outside GitHub.

## Commands

`preflight` is read-only. It verifies the exact private bundle, the current T1 network binding, production Broker/Manager continuity, free TCP/18883, no pre-existing lab container, and that both candidate LAN addresses are still unassigned and unclaimed.

`activate` is a live T1 mutation and requires the exact confirmation:

`N3W_GATE_A_T1_LAB_MUTATION_AUTHORIZED`

It creates only a temporary private directory under `/run`, reuses the already-running production Broker image ID without modifying the production container, hashes the temporary lab password file, starts one labeled host-network Mosquitto container on TCP/18883, and adds only the bound temporary live alias. The blackhole address remains unassigned.

`cleanup` is a live T1 mutation and requires:

`N3W_GATE_A_T1_LAB_CLEANUP_AUTHORIZED`

It removes only the exact labeled Gate A container, removes only the exact bound live alias, deletes the exact `/run` lab directory, then verifies production Broker/Manager continuity and that TCP/18883 is gone.

## Safety boundary

The package must not:

- restart, recreate, stop, edit or reconfigure the production Broker;
- restart or modify Manager;
- touch Dynamic Security, Home Assistant, Compose authority or production TLS files;
- assign the blackhole address;
- write or access Board B;
- expose private profile values on stdout;
- reuse an activation preflight after it is claimed.

The production Broker and Manager restart counts are frozen by the read-only preflight and must remain unchanged through activation and cleanup.

## Physical sequencing

Repository/CI validation of this package does not authorize live mutation.

Required live order:

1. fresh `preflight`;
2. explicit activation authorization;
3. `activate`;
4. Board B Gate A write and timing test under its own authorization;
5. `cleanup`;
6. exact KF-099 rollback and post-rollback continuity check.

Any activation failure performs bounded best-effort cleanup before returning failure. A later cleanup run remains available for residue recovery but must still validate exact labels and private state.
