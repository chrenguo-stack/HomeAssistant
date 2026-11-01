# H3/N2 Stage 2D-5 Production MQTT and Persistence Adapters

## Status

Stage 2D-5 adds production-shaped ESP-IDF MQTT and persistence adapters while
keeping all repository validation compile-only.

Base main:

`f6c77ab15417a2c4d153ad43b668a5640265c3a2`

Development branch:

`feature/h3-n2-stage2d5-production-adapters-20260721-v53`

## Goal

Stage 2D-4 proved the full lifecycle with injected fake boundaries. Stage 2D-5
implements the concrete boundary layer needed by a later isolated device test:

```text
PairingPersistentStore
+ dedicated ESP-IDF candidate probe client
+ active MQTT session
+ activation candidate MQTT session
+ marker-last lifecycle coordinator
```

The code is intentionally not wired to startup or a production YAML action.

## MQTT implementation

`EspIdfProductionMqttSession` owns a dedicated `esp_mqtt_client_handle_t`, keeps
all credential strings alive for the lifetime of that client, enforces TLS, and
maps ESP-IDF events into the shared candidate validation contract.

The session:

- subscribes to the exact confirmation topic at QoS 1;
- publishes the telemetry probe at QoS 1 only after subscription acknowledgement;
- reconstructs fragmented MQTT payloads before exact comparison;
- distinguishes Broker connection refusal from general transport failure;
- provides bounded connection and round-trip waits;
- destroys the client and clears profile, exchange, and payload material.

`ProductionCandidateMqttTransport` connects this session to the Stage 2D-2
validator without sharing the active runtime client.

## Lifecycle runtime

`ProductionProfileLifecycleRuntime` owns two role-bound sessions:

- current active;
- activation candidate.

For rotation, the normal active session must first be explicitly bound with
`bind_active_profile()`. Recovery then proves the bound active profile exactly
matches the persistent active credential bundle before accepting a candidate.

On successful marker-last commit, `clear_candidate_material()` converts the
candidate profile into active material while preserving the coordinator's final
runtime observation. The caller must then invoke
`finalize_activation_promotion()` before starting another lifecycle. The method
swaps session roles so the newly committed connection becomes the next active
session and the stopped old session becomes the next candidate slot.

## Persistence adapter

Two composition layers are provided:

- `ProductionPersistenceAdapter` for injected host backends and deterministic
  tests;
- `EspIdfProductionPersistenceAdapter` for NVS plus eFuse-HMAC-derived envelope
  keys on ESP32-C6.

The ESP-IDF adapter defaults to read-only authorization. A read-write open is
rejected unless `allow_read_write=true` was explicitly supplied when configured.
No compile target constructs or opens this adapter.

## Host fault matrix

The deterministic matrix covers:

- candidate transport success and failure mapping;
- active profile binding;
- generation 1 to 2 rotation;
- explicit post-commit session-role promotion;
- a second rotation after promotion;
- first enrollment;
- stale candidate rejection;
- candidate start failure and old-active restoration;
- same-session configuration rejection;
- injected authenticated persistence composition and PREPARED recovery.

All persistence mutations in the host matrix use an in-memory backend.

## ESP32-C6 compile targets

Two disabled targets compile the concrete ESP-IDF classes:

- minimal ESP32-C6 DevKitM assembly;
- full F1.0-RC2 product-board assembly.

Both targets keep Wi-Fi disabled at boot and expose no component instance,
startup hook, action, button, switch, Broker address, credential, NVS namespace,
or eFuse key selection.

## Explicit execution boundary

本阶段只允许源码、主机故障矩阵和 ESP32-C6 compile-only 验证。

- 不得连接真实 Broker；
- 不得写入物理 NVS；
- 不得操作实板；
- 不得读取、烧写或 provisioning eFuse；
- 不得修改 M401A、T1、Home Assistant 或 Mosquitto；
- 不得修改生产 `f1_0_rc2.yml` 或现有产品 packages；
- 不得加入自动开机恢复或 profile activation。

Physical acceptance requires a separate explicit authorization and a dedicated
rollback-first test package.
