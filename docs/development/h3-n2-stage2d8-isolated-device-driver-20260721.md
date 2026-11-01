# H3/N2 Stage 2D-8 Isolated Device Driver

## Status

Accepted parent:

`ab04d31032403869379d976cd9f250fb3f144f7d`

Development branch:

`feature/h3-n2-stage2d8-isolated-device-driver-20260721-v56`

Stage 2D-8 converts the Stage 2D-7 abstract acceptance interface into a
compile-verified isolated-device driver. The current branch still performs no
live operation: the ESPHome component creates no object, Wi-Fi stays disabled
at boot, and no board, NVS partition or Broker is selected in the repository.

## Deliverables

- portable fail-closed driver core implementing `IsolatedAcceptanceDriver`;
- a second mirrored one-shot authorization gate at the physical-driver layer;
- an authorization binder that arms the package and driver together;
- ESP-IDF test-NVS port using the volatile Stage 2D-7 key provider;
- audited record and marker commits proving marker-last order;
- ESP-IDF MQTT port using only runtime-injected test credentials;
- test-only probe topics below the runtime-injected `gh-test/` root;
- rollback-before-authority-change and reboot-required ambiguity handling;
- deterministic host fault matrix;
- dedicated and product-PCB compile-only targets;
- isolated Broker templates, execution-manifest schema and safety gate;
- CI boundary, host, redaction and ESP32-C6 compile checks.

## Two-layer authorization

Stage 2D-7 consumes its own authorization before calling `prepare_candidate`
or `cleanup_test_state`, and passes its authorizer into activation. Stage 2D-8
adds `MirroredGenerationWriteAuthorization` inside the physical driver.

`IsolatedDeviceAuthorizationBinder` succeeds only when both layers accept the
same operation, active generation, candidate generation and authorization
record digest. If one layer rejects the grant, the other layer is cleared.

Activation consumes the Stage 2D-7 authorizer first and then the mirrored
driver grant. A mismatch after the package grant has been consumed is an
authority ambiguity: all sessions are quiesced and reboot recovery is required.

## Persistence model

The ESP32 port accepts only a runtime configuration whose partition label and
namespace both begin with `gh2d8_`, are at most 15 characters, and are distinct.
It cannot select the default `nvs` partition or a production namespace.

The port does not initialize, erase or repair a partition during component
construction. A later live harness must explicitly initialize the dedicated
partition under its execution manifest before calling the port.

Read-only inspection:

1. opens the dedicated namespace read-only;
2. treats an absent namespace as `empty`;
3. requires the RAM test key before decrypting an existing namespace;
4. recovers exact active and candidate generations;
5. proves the package caused no persistent commit;
6. closes the NVS handle before returning.

Write mode is opened only inside the three explicitly authorized operations.
The audited backend records successful commit keys. Activation is accepted only
when the final two commits are the candidate slot followed by `active` and a
fresh read-only recovery identifies the candidate generation as authoritative.

Cleanup erases only the named `gh2d8_` namespace, commits once, closes it and
then verifies `empty`. It does not erase a partition and never accesses eFuse.

## MQTT isolation

The ESP-IDF port does not use the production validator's `gh/v1` probe topics.
It builds the request and confirmation exchange under the runtime-injected
candidate `test_topic_root`:

- `<test_topic_root>/probe/request`
- `<test_topic_root>/probe/confirm`

Both topics must start with `gh-test/`; Home Assistant Discovery and production
node roots remain forbidden.

The old active test session may remain live while the independent probe and
activation candidate are verified. The candidate becomes authoritative only
after a successful test round trip and marker-last persistence commit. If a
pre-marker failure occurs, the candidate is destroyed and the old active test
session is retained. Any failure after the active marker is committed closes to
reboot-required rather than guessing authority.

## Current compile targets

Dedicated compile target:

`firmware/esphome_rc/board_lab/h3_profile_isolated_device_driver/greenhouse_profile_isolated_device_driver_board_lab_20260721_v56.yml`

Product-PCB compatibility overlay:

`firmware/esphome_rc/f1_0_rc2/f1_0_rc2_h3_profile_isolated_device_driver_board_lab_20260721_v56.yml`

Both targets are compile-only and must not be flashed. Neither target includes a
partition table, Broker, test key, runtime object, command transport, startup
hook or write authorization.

## Live execution gates not yet satisfied

A live firmware image cannot be assembled until an execution manifest fixes:

- dedicated board identifier and serial path;
- rollback image and digest;
- test image and digest;
- dedicated partition table and `gh2d8_` partition label;
- `gh2d8_` namespace;
- isolated Wi-Fi identity;
- temporary Broker certificate and configuration digests;
- unique run, client and topic identifiers;
- evidence output directory;
- physical recovery procedure.

After flashing, the first command is still read-only inspection. The exact
observed generations are then returned to the operator. `PREPARE_CANDIDATE`,
`ACTIVATE_PROFILE` and `CLEANUP_TEST_STATE` each require a separate later
one-shot approval and cannot inherit the current stage authorization.

## Explicit exclusions

This branch does not:

- instantiate the driver;
- initialize or open physical NVS at runtime;
- initialize a custom partition;
- connect Wi-Fi or MQTT;
- deploy or start Mosquitto;
- load a test key or credential;
- flash or run an ESP32-C6;
- read or burn eFuse;
- operate M401A, T1, Home Assistant, production Mosquitto or greenhouse-manager;
- modify `f1_0_rc2.yml` or existing product packages;
- modify Stage 2D-6 or Stage 2D-7 source paths.
