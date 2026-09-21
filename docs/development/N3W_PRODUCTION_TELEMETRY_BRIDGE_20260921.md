# N3-W production telemetry bridge

Updated: 2026-09-21  
Status: SOURCE_BRIDGE_CREATED

```text
GATE=N3W_PRODUCTION_TELEMETRY_BRIDGE_20260921_01
BASE_TARGET_HEAD=f77d533065d593e6fe7f4da7f74381172127be5e
FROZEN_PR437_SOURCE_HEAD=4270f24a92a87dd5239d781ebba624c2f34b7fc2
```

## Data ownership

The production bridge reuses the F1.0-RC2 N1 measurement vocabulary and quality
semantics, but does not reuse the old N1 boot ID, sequence generator, or direct
MQTT publisher.

```text
F1.0-RC2 real sensors / derived values
        |
        v
gh.telemetry/1 builder
        |
        +-- take_telemetry_identity()
        |
        v
submit_telemetry_json()
        |
        +-- Direct MQTT
        +-- Option-B queue
        +-- ESP-NOW Relay
```

The telemetry cadence remains the existing N1 production value of 60 seconds.
The existing N1 capability hash `sha256:fed2dec764f4146d` is reused because
the measurement capability set is unchanged.

## Measurement vocabulary

The bridge keeps all Home Assistant measurement keys already used by
`packages/mqtt_n1.yml`:

- air temperature / humidity;
- CO2 and illuminance;
- soil temperature / moisture / EC;
- VPD, dew point and absolute humidity;
- PPFD, DLI today and DLI yesterday;
- battery voltage and percentage.

Quality values remain `ok`, `warming`, `stale`, `fault`, and
`not_present`.

## Relay plaintext budget

N3-W accepts at most 1024 bytes of telemetry plaintext. The old MQTT-only
builder can approach or exceed that ceiling because it serializes every missing
measurement as `null` and duplicates battery values under both
`measurements` and `power`.

The production bridge therefore:

1. omits a missing numeric measurement while retaining its quality state;
2. rounds values to the precision already exposed by the F1.0-RC2 entities;
3. first builds the full semantic payload;
4. if necessary, removes duplicated battery fields from `power`;
5. if still necessary, removes optional `fw_version`;
6. refuses submission if the result still exceeds
   `kMaxCiphertextBytes`.

No Direct/Relay state-machine behavior is changed.

## Not proved by this gate

- ESPHome config/compile success for the bridge;
- final binary size/linkage;
- Manager live acceptance;
- physical sensor values on Board B;
- final production artifact identity.
