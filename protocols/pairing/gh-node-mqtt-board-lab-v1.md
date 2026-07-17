# Greenhouse M2 ESP32-C6 node MQTT board-lab contract v1

## Status

- Scope: non-production, dedicated ESP32-C6 test board.
- Production node migration: prohibited.
- Production credential generation or delivery: prohibited.
- Anonymous closure: prohibited.
- Home Assistant `.storage` access: prohibited.
- Dynamic Security control operations: prohibited.

## Purpose

The isolated host Broker matrix proves credential and anonymous continuity at
the protocol level, but it cannot prove ESP32-C6 reboot ordering, ESP-IDF MQTT
callbacks, NVS persistence, power-loss recovery, or local sensor/LCD/RS485
continuity. This contract defines the first physical-board evidence gate.

## Fixed non-production identities

| Role | Value |
|---|---|
| candidate username | `ghn_lab-board` |
| candidate Client ID | `lab-board` |
| anonymous Client ID | `lab-board-anon` |
| observer username | `gho_lab-observer` |
| Broker image | `eclipse-mosquitto:2.0.22` |

None of these values may be reused as a production identity.

## Private workspace contract

The workspace is mode `0700`; generated files are mode `0600`. Raw passwords
are stored only in the private workspace. The Mosquitto password file is
converted in place with `mosquitto_passwd -U`; passwords are not supplied in
process arguments. Public reports contain fingerprints only and exclude the
absolute workspace path.

The host bind address must be a literal non-global IPv4 address. Unspecified,
multicast, hostname, and globally routable values fail closed.

## Firmware contract

The board targets use ESPHome `2026.4.3`, ESP32-C6, ESP-IDF, and the existing
`greenhouse_mqtt_auth` boot-profile adapter.

Two targets have intentionally different evidence scopes:

- `greenhouse_mqtt_auth_board_lab.yml` is the minimal authentication-only
  target. It proves generic ESP32-C6 compilation and adapter behavior but does
  not contain product LCD, environmental sensor, battery, or RS485 packages.
- `f1_0_rc2_m2_node_auth_board_lab.yml` is the full product-PCB target. It
  includes the repository F1.0-RC2 core, control, bus, sensor, and display
  packages and is the only permitted target for the physical 50-case matrix.

A compile of the minimal target cannot be used as evidence for local
continuity. Neither target authorizes flashing a production node.

Identity switching remains:

```text
persist desired_profile
→ safe reboot
→ select credentials and Client ID before MQTT setup
→ initialize the ESP-IDF MQTT backend once
```

No runtime `disable()/enable()` credential swap is considered valid evidence.

For deterministic power-cut testing, the component exposes a board-lab-only,
RAM-only reboot hold. It pauses the next scheduled safe reboot after the
redacted desired profile state has been persisted. The hold flag is not added
to `PersistedState`, is not restored after power loss, and must not be called
from production YAML. A separate release action performs the pending reboot.

The board targets also map an active-low GPIO9 input to anonymous rollback so
an operator can request rollback while Wi-Fi or the Broker is unavailable.
The button must be pressed only after boot and is not a production interface.

The common board heartbeat publishes only redacted state:

- active profile and phase;
- MQTT connected state;
- failure and observation counters;
- ready-for-commit state;
- candidate generation and secret fingerprint;
- generic failure class;
- local loop count and uptime;
- `secret_values_included=false`.

The full product target additionally publishes non-secret evidence that the
air, CO2, light, and soil entities have produced states, plus soil query and
success counters and low-battery mode. These fields do not replace the
operator's LCD, sensor-plausibility, RS485, and local-calculation observations.

## Failure classification

A host-side invalid-credential smoke test may prove that the non-production
Broker rejected a connection. The ESP32-C6 public callback cannot prove the
specific reason and must record only
`generic_candidate_connection_failure`. Wi-Fi loss, Broker outage, TCP loss,
and authentication rejection must not be mislabeled as a proven password
error.

## Control contract

The observer identity may publish only to the non-production `lab/control/#`
namespace. Candidate activation and commit require the literal board-lab
confirmation gate. Commit is never automatic. Rollback selects anonymous,
persists the state, and reboots. Rollback does not claim secure erasure of the
candidate secret.

## Evidence record contract

Each JSONL observation conforms to
`gh.m2.node-mqtt-board-lab-observation/1`. Every required case starts as
`blocked`. A passed case requires:

- `operator_observed=true`;
- at least one evidence fingerprint;
- all production-safety flags false;
- `secret_values_included=false`;
- `secure_erase_claimed=false`;
- redacted notes only.

The summarizer fails closed for missing, failed, blocked, duplicate,
unsafe, or evidence-free cases. A successful summary proves only completion
of the dedicated board matrix. It does not authorize production credential
generation, production firmware deployment, or anonymous closure.

## Physical matrix groups

1. first anonymous boot and offline local operation;
2. valid candidate activation, fixed Client ID, observation, and commit gate;
3. invalid candidate, persistent generic failure count, reboot, and anonymous fallback;
4. Wi-Fi and Broker loss/recovery under both profiles;
5. seven power-loss/NVS cut points;
6. rollback before and after commit, including Broker-unreachable rollback;
7. ESPHome config, compile, serial, heartbeat, preferences, OTA, and crash-log secret checks;
8. LCD, sensors, local calculations, low-power behavior, and RS485 continuity.
