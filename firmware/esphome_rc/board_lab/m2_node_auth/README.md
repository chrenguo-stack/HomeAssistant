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

## Public targets and private files

Committed board targets:

- `greenhouse_mqtt_auth_board_lab.yml`: minimal ESP32-C6 authentication-only
  harness for generic compile and protocol checks. It does **not** contain the
  product LCD, environmental sensors, or RS485 packages and therefore cannot
  satisfy the local-continuity cases in the physical fault matrix.
- `../../f1_0_rc2/f1_0_rc2_m2_node_auth_board_lab.yml`: full product-PCB target.
  It preserves the repository F1.0-RC2 sensor, LCD, battery, RS485, and local
  control packages and adds the same non-production MQTT authentication
  harness. This is the only target permitted for the 50-case product-board
  runtime matrix.
- `secrets.example.yaml`: placeholder-only example.
- `.gitignore`: prevents the local secret file, logs, matrix records, and build
  directory from being committed.

Private runtime files are generated under an operator-selected mode `0700`
workspace. They include random non-production passwords, `secrets.yaml`, the
Mosquitto password file, captures, and the editable matrix record set. They
must not be copied into the repository.

The full product target is a source-level derivative of the repository RC2
baseline. It is not evidence that any currently deployed field firmware has
been upgraded or is byte-identical. Never use a production node as the test
board.

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
5. writes a private `secrets.yaml` for the board targets;
6. starts pinned `eclipse-mosquitto:2.0.22` on the selected non-global host IP;
7. preserves anonymous access.

Before compilation, edit only the private `secrets.yaml` Wi-Fi placeholders.
Do not paste Wi-Fi or MQTT secrets into GitHub, chat, logs, or command history.

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

## Build targets

### Minimal authentication-only target

This target is useful for generic ESP32-C6 compile or protocol debugging only.
It must not be used to claim LCD, sensor, or RS485 continuity.

```bash
install -m 600 <private-workspace>/secrets.yaml \
  firmware/esphome_rc/board_lab/m2_node_auth/secrets.yaml
cd firmware/esphome_rc/board_lab/m2_node_auth
esphome config greenhouse_mqtt_auth_board_lab.yml
esphome compile greenhouse_mqtt_auth_board_lab.yml
```

### Full product-PCB target

Use this target for the physical fault matrix on a dedicated greenhouse PCB.
The command keeps the private secret file ignored by Git and compiles the
complete RC2 product packages plus the board-lab adapter.

```bash
install -m 600 <private-workspace>/secrets.yaml \
  firmware/esphome_rc/f1_0_rc2/secrets.yaml
cd firmware/esphome_rc/f1_0_rc2
RC2_CONFIG=f1_0_rc2_m2_node_auth_board_lab.yml bash tools/rc2.sh config
RC2_CONFIG=f1_0_rc2_m2_node_auth_board_lab.yml bash tools/rc2.sh compile
RC2_CONFIG=f1_0_rc2_m2_node_auth_board_lab.yml bash tools/rc2.sh run \
  --device <serial-device>
```

The first USB flash, physical power cycling, Wi-Fi interruption, Broker
stop/start operations, and LCD/sensor/RS485 observations require the operator.
Do not perform them on the production node. Before the first flash, verify that
the selected board is a dedicated test board and that its GPIO wiring matches
the RC2 product target.

## Observation and control

Capture redacted heartbeats:

```bash
greenhouse-manager-node-mqtt-board-lab observe \
  --workspace <private-workspace> \
  --duration 30 \
  --output <private-workspace>/heartbeats.jsonl
```

The full product target heartbeat adds non-secret runtime evidence for local
loop progress, battery mode, soil query/success counters, and whether the air,
CO2, light, and soil entities have produced states. LCD appearance and actual
sensor plausibility remain operator-observed evidence; heartbeat booleans do
not replace those checks.

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

GPIO9 is an internal, active-low offline rollback input in both board-lab
targets. Press it only after normal boot; holding it during reset may select
the chip's boot mode. The input exists so rollback can be requested while
Wi-Fi or the Broker is unavailable. It must not be enabled unchanged in
production YAML.

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

Remove the ignored local `secrets.yaml` copies after the test. The destroy
command removes only a workspace whose marker and manifest binding match. It
does not claim secure erasure of flash, NVS, SSD blocks, or backups.
