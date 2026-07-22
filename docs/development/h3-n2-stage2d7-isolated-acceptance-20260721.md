# H3/N2 Stage 2D-7 Isolated Acceptance Package

## Status

Base main:

`b8cc4f68d29393cdf9da7d00fdfeef28ee147c7b`

Development branch:

`feature/h3-n2-stage2d7-isolated-acceptance-package-20260721-v55`

Stage 2D-7 prepares a source-only, compile-only acceptance package for a later
reversible isolated-board test. It does not create the Stage 2D-8 physical
driver and performs no live operation.

## Deliverables

- host-only command state machine;
- abstract isolated driver interface;
- RAM-only, erasable test persistence key provider;
- one-shot generation-bound authorization gate for prepare, activate, and
  cleanup writes;
- redacted evidence object and sink;
- deterministic host fault matrix;
- dedicated ESP32-C6 compile-only target with Wi-Fi disabled at boot;
- full F1.0-RC2 product-PCB compatibility compile-only overlay;
- isolated Broker, fault matrix, evidence, and cleanup protocol;
- boundary gate and CI.

## Safety model

The package starts in `cold`. It does not call the driver until the explicit
`inspect_read_only` command. The Stage 2D-7 ESPHome component creates no object
and exposes no action, button, switch, script, service, serial command, or
startup hook.

All persistent writes remain inside the abstract driver and are impossible
without a fresh one-shot authorization for the exact operation and generation
pair. Activation additionally requires the driver to consume the existing
Stage 2D-6 `ProfileLifecycleMutationAuthorizer` grant. Success without grant
consumption is treated as an authority violation and closes to
`reboot_required`.

## Key provider boundary

`VolatileTestPersistenceKeyProvider` has no compiled key. It accepts a nonzero
32-byte key only at runtime, refuses derivation before loading, and zeroizes the
key on cleanup, reconfiguration, reboot closure, and destruction.

It is test-only. Production eFuse-HMAC remains compile-only and is not selected
or invoked by Stage 2D-7.

## Compile targets

Dedicated target:

`firmware/esphome_rc/board_lab/h3_profile_isolated_acceptance/greenhouse_profile_isolated_acceptance_board_lab_20260721_v55.yml`

- uses ephemeral CI Wi-Fi values;
- Wi-Fi `enable_on_boot: false`;
- has no `mqtt:` component;
- contains no NVS backend, Broker, key, command transport, or startup hook.

Product-PCB compatibility overlay:

`firmware/esphome_rc/f1_0_rc2/f1_0_rc2_h3_profile_isolated_acceptance_board_lab_20260721_v55.yml`

This overlay exists only to compile the new component beside the existing RC2
product packages. It is not an acceptance image and must not be flashed.

## Host coverage

The deterministic host matrix proves:

- startup inspection is offline and causes no package write;
- missing test key blocks configuration;
- no default or all-zero key is accepted;
- PREPARED write requires its own exact one-shot grant;
- validation and activation cannot be skipped;
- stale generations fail closed;
- activation cannot bypass authorizer consumption;
- marker-last evidence is mandatory;
- evidence excludes Broker, CA, password, key, nonce, and authorization values;
- evidence export failure is retryable;
- cleanup requires prior evidence and a separate grant;
- cleanup destroys test key and in-memory candidate material;
- reboot closure clears authorization and key material.

## Explicitly not implemented

- physical NVS open/read/write;
- ESP-MQTT client creation or start;
- temporary Broker deployment;
- Wi-Fi enable command;
- serial, API, web, BLE, or GPIO control entry;
- real candidate conversion to `RamCredentialBundle`;
- Stage 2D-8 device driver;
- eFuse read or write;
- firmware flashing;
- Home Assistant or greenhouse-manager integration;
- production startup wiring.

## Protected paths

Stage 2D-7 must not modify:

- `firmware/esphome_rc/f1_0_rc2/f1_0_rc2.yml`;
- `firmware/esphome_rc/f1_0_rc2/packages/**`;
- Stage 2D-6 component, test, workflow, protocol, or compile targets.

The CI boundary gate compares the protected production paths against the exact
Stage 2D-7 base commit.

## Next decision gate

After all CI checks pass and the Draft PR remains reviewable, Stage 2D-8 still
requires explicit authorization covering:

- the exact isolated ESP32-C6 board;
- the exact temporary Broker and ACL;
- the physical test NVS namespace and erase procedure;
- runtime command transport;
- firmware artifact digest;
- reversible flashing and recovery commands;
- a selected subset of the frozen physical fault matrix.
