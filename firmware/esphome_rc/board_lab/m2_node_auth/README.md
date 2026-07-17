# M2 ESP32-C6 node-auth board lab

This directory contains the public, non-production harness for the first real
ESP32-C6 runtime fault matrix. It must never be pointed at the production T1,
production Mosquitto, production Home Assistant, or a production monitoring
node.

## Safety boundary

The board lab keeps anonymous MQTT enabled and uses only these fixed test
identities:

- candidate username: `ghn_lab-board`
- candidate Client ID: `lab-board`
- anonymous Client ID: `lab-board-anon`
- observer username: `gho_lab-observer`

The tooling rejects globally routable Broker bind addresses. It does not read
Home Assistant `.storage`, does not call Dynamic Security control topics, does
not create production credentials, and cannot close anonymous access.

## Public files and private files

Committed files:

- `greenhouse_mqtt_auth_board_lab.yml`: ESP32-C6 ESP-IDF board target.
- `secrets.example.yaml`: placeholder-only example.
- `.gitignore`: prevents the local secret file, logs, matrix records, and build
  directory from being committed.

Private runtime files are generated under an operator-selected mode `0700`
workspace. They include random non-production passwords, `secrets.yaml`, the
Mosquitto password file, captures, and the editable matrix record set. They
must not be copied into the repository.

## Preparation sequence

The commands below are examples. Replace `<private-workspace>` and
`<non-global-lab-ip>` locally. The bind IP must be a literal IPv4 address that
is loopback, private, link-local, or reserved; a global address and `0.0.0.0`
are rejected.

```bash
greenhouse-manager-node-mqtt-board-lab plan \
  --workspace <private-workspace> \
  --bind-host <non-global-lab-ip> \
  --port 18883

greenhouse-manager-node-mqtt-board-lab create \
  --workspace <private-workspace> \
  --bind-host <non-global-lab-ip> \
  --port 18883 \
  --confirmation M2-NONPRODUCTION-BOARD-LAB
```

`create` performs all of the following:

1. creates a mode `0700` workspace;
2. generates random candidate and observer passwords;
3. writes only fingerprints to the public report;
4. converts the Mosquitto password file in-place with `mosquitto_passwd -U`;
5. writes a private `secrets.yaml` for the board target;
6. starts pinned `eclipse-mosquitto:2.0.22` on the selected non-global host IP;
7. preserves anonymous access.

Before compilation, edit only the private `secrets.yaml` Wi-Fi placeholders.
Do not copy secrets to the repository.

## Non-board Broker checks

Run these before attaching a test board:

```bash
greenhouse-manager-node-mqtt-board-lab smoke-valid \
  --workspace <private-workspace>

greenhouse-manager-node-mqtt-board-lab invalidate-candidate \
  --workspace <private-workspace>

greenhouse-manager-node-mqtt-board-lab smoke-invalid \
  --workspace <private-workspace>

greenhouse-manager-node-mqtt-board-lab restore-candidate \
  --workspace <private-workspace>
```

The invalid-candidate check may state only that the isolated Broker rejected
the probe. The ESP32-C6 firmware itself must continue to classify its public
disconnect callback as `generic_candidate_connection_failure`.

## Build and first USB flash

Copy the board YAML and the generated private `secrets.yaml` into the same
private build directory, preserving the relative path to the repository
component directory, or invoke ESPHome from this directory with a private
secret file supplied locally.

```bash
esphome config greenhouse_mqtt_auth_board_lab.yml
esphome compile greenhouse_mqtt_auth_board_lab.yml
esphome run greenhouse_mqtt_auth_board_lab.yml --device <serial-device>
```

The first USB flash, physical power cycling, Wi-Fi interruption, Broker
stop/start operations, and LCD/sensor/RS485 observations require the operator.
Do not perform them on the production node.

## Observation and control

Capture redacted heartbeats:

```bash
greenhouse-manager-node-mqtt-board-lab observe \
  --workspace <private-workspace> \
  --duration 30 \
  --output <private-workspace>/heartbeats.jsonl
```

Publish a non-production control message:

```bash
greenhouse-manager-node-mqtt-board-lab control \
  --workspace <private-workspace> \
  --control-command activate \
  --confirmation M2-NONPRODUCTION-BOARD-LAB
```

Supported control commands are `activate`, `observe-success`,
`observe-failure`, `commit`, `rollback`, `hold-reboot-anonymous`,
`release-reboot-anonymous`, `hold-reboot-candidate`, and
`release-reboot-candidate`. `commit` remains a separate operator action and is
never sent automatically.

The reboot-hold commands are deterministic board-lab fault-injection hooks.
They are RAM-only, are not stored in NVS, and pause the next adapter-requested
reboot only after the desired profile has been persisted. Use them to create a
repeatable power-cut point after candidate staging, fallback selection, or
rollback selection. Releasing the hold performs the pending safe reboot.

GPIO9 is an internal, active-low offline rollback input in this board target.
Press it only after normal boot; holding it during reset may select the chip's
boot mode. The input exists so rollback can be requested while Wi-Fi or the
Broker is unavailable. It must not be enabled unchanged in production YAML.

## Serial secret check

```bash
greenhouse-manager-node-mqtt-board-lab check-serial-log \
  --workspace <private-workspace> \
  --log <private-workspace>/serial.log
```

The check fails closed when any generated candidate, observer, or configured
Wi-Fi secret appears verbatim.

## Fault matrix records

Initialize one blocked record for every required case:

```bash
greenhouse-manager-node-mqtt-board-lab init-matrix \
  --output <private-workspace>/fault-matrix.jsonl
```

After each physical test, edit only the corresponding private JSON line. A
case may be marked `pass` only when `operator_observed=true` and at least one
non-secret evidence fingerprint is present.

Summarize:

```bash
greenhouse-manager-node-mqtt-board-lab summarize \
  --records <private-workspace>/fault-matrix.jsonl
```

The summary exits nonzero until every required case passes, every evidence
field is present, no duplicate case exists, and all production-safety flags
remain false.

## Cleanup

```bash
greenhouse-manager-node-mqtt-board-lab destroy \
  --workspace <private-workspace>
```

The command removes only a workspace whose marker and manifest binding match.
It does not claim secure erasure of flash, NVS, SSD blocks, or backups.
