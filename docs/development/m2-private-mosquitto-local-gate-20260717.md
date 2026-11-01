# M2 project-private Mosquitto local gate — 2026-07-17

## Status

The operator-local Intel macOS board-lab prerequisite gate completed successfully against repository commit:

```text
d29d8adc78ad3a7c213b2f6cbb1c53f0f91826df
```

Verified public-safe state:

```text
status=private_mosquitto_macos_preboard_succeeded
manager_version=0.4.94
private_mosquitto_version=2.0.21
private_mosquitto_source_sha256=7ad5e84caeb8d2bb6ed0c04614b2a7042def961af82d87f688ba33db857b899d
private_build_status=private_mosquitto_built
report_count=14
local_mac_private_mosquitto_build_complete=true
local_mac_native_preboard_matrix_complete=true
private_manifest_present=true
private_cache_preserved=true
runtime_workspace_removed=true
hybrid_development_mode_frozen=true
homebrew_mosquitto_required=false
homebrew_install_invoked=false
homebrew_service_action_invoked=false
production_system_modified=false
production_endpoint_used=false
node_credentials_generated=false
board_flashing_performed=false
anonymous_closure_enabled=false
real_board_runtime_fault_matrix_complete=false
ready_for_live_apply=false
ready_for_anonymous_closure=false
```

## Evidence boundary

The private runtime reports, manifest path, local LAN address, Wi-Fi values, generated non-production MQTT values, serial logs and physical fault-matrix records remain outside the public repository.

This record confirms only that the frozen Mosquitto `2.0.21` source archive was verified and built locally, and that the native non-production Broker valid/invalid/restore/stop/start pre-board sequence passed. It does not claim real ESP32-C6 validation, production migration readiness, node credential readiness or anonymous MQTT closure readiness.

## Next gate

The next gate requires a dedicated non-production ESP32-C6 product PCB and operator-controlled physical actions:

- USB identification and first flash of `f1_0_rc2_m2_node_auth_board_lab.yml`;
- LCD, SCD30, SHT30, GY30/BH1750 and RS485 soil-sensor observations;
- Wi-Fi and Broker interruption/recovery;
- GPIO9 offline rollback after normal boot;
- controlled reset, power and NVS fault points;
- completion of the private 50-case physical-board matrix.

Production T1, production Mosquitto, Home Assistant and deployed monitoring nodes remain out of scope.
