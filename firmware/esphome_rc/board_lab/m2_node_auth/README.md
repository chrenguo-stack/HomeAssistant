# M2 ESP32-C6 node-auth board lab

This directory contains the public, non-production harness for the first real
ESP32-C6 runtime fault matrix. It must never be pointed at the production T1,
production Mosquitto, production Home Assistant, or a production monitoring
node.

The development-mode and local Broker decisions are frozen in:

```text
docs/decisions/M2-ADR-001-hybrid-development-and-private-mosquitto.md
```

The project uses a hybrid workflow:

- local Mac for fast tests, cached ESP32-C6 builds, USB, serial and physical observations;
- GitHub or isolated Linux for clean-environment, Docker and required gates;
- a dedicated non-production PCB for real-board tests;
- a separate, explicitly authorized T1 gate for any later production operation.

Pure-cloud validation cannot replace USB, LCD, sensor, RS485, Wi-Fi, GPIO or
power-interruption evidence.

## Safety boundary

The board lab keeps anonymous MQTT enabled and uses only these fixed test
identities:

- candidate username: `ghn_lab-board`;
- candidate Client ID: `lab-board`;
- anonymous Client ID: `lab-board-anon`;
- observer username: `gho_lab-observer`.

The tooling rejects globally routable Broker bind addresses. It does not read
Home Assistant `.storage`, does not call Dynamic Security control topics, does
not create production credentials, and cannot close anonymous access.

The Homebrew `mosquitto` formula and `brew services start mosquitto` are not
project dependencies. The local board lab uses the verified project-private
Mosquitto build described below. Existing Homebrew CMake and OpenSSL packages
may be used only as build prerequisites.

## Public targets and private files

Committed board targets:

- `greenhouse_mqtt_auth_board_lab.yml`: minimal ESP32-C6 authentication-only
  harness for generic compile and protocol checks. It does **not** contain the
  product LCD, environmental sensors, or RS485 packages and therefore cannot
  satisfy the local-continuity cases in the physical fault matrix.
- `../../f1_0_rc2/f1_0_rc2_m2_node_auth_board_lab.yml`: full product-PCB target.
  It includes the F1.0-RC2 core, LCD, sensor, battery and RS485 packages plus
  `packages/control_m2_board_lab.yml`. It preserves SCD30 updates every
  11 seconds; one 15-second soil warm-up after boot or low-battery recovery;
  continuously powered soil hardware after warm-up; and normal Modbus reads
  every 20 seconds. This is the only target permitted for the 50-case
  product-board runtime matrix.
- `secrets.example.yaml`: placeholder-only example.
- `.gitignore`: prevents local secrets, logs, matrix records and local build
  state from being committed.

Private runtime files must remain outside Git in a mode-`0700` directory. They
include random non-production passwords, `secrets.yaml`, the Mosquitto password
file, captures, serial logs and the editable fault-matrix record set.

Do not copy runtime evidence, local paths, Wi-Fi values, generated MQTT values,
serial logs or the hand-edited matrix into the public repository.

The full product target is a source-level test derivative. It is not evidence
that any deployed field firmware has been upgraded or is byte-identical. Never
use a production node as the test board.

## Frozen project-private Mosquitto

Fixed source contract:

```text
version=2.0.21
source=https://mosquitto.org/files/source/mosquitto-2.0.21.tar.gz
sha256=7ad5e84caeb8d2bb6ed0c04614b2a7042def961af82d87f688ba33db857b899d
websockets=off
clients=off
plugins=off
documentation=off
tls=on
```

The private build installs only:

```text
mosquitto
mosquitto_passwd
```

The public builder entrypoint is:

```text
greenhouse-manager-node-mqtt-private-mosquitto
```

Supported commands:

```text
plan
build
verify
```

Example for Intel macOS:

```bash
set -euo pipefail

cache_root="$HOME/.cache/greenhouse-mosquitto"
cmake_bin="$(command -v cmake)"
openssl_root="$(brew --prefix openssl@3)"
source_archive="<verified-official-mosquitto-2.0.21.tar.gz>"

greenhouse-manager-node-mqtt-private-mosquitto plan \
  --cache-root "$cache_root" \
  --cmake-bin "$cmake_bin" \
  --openssl-root "$openssl_root"

greenhouse-manager-node-mqtt-private-mosquitto build \
  --cache-root "$cache_root" \
  --source-archive "$source_archive" \
  --cmake-bin "$cmake_bin" \
  --openssl-root "$openssl_root" \
  --jobs 2 \
  --confirmation M2-NONPRODUCTION-PRIVATE-MOSQUITTO

private_manifest="$cache_root/2.0.21/darwin-x86_64/manifest.json"

greenhouse-manager-node-mqtt-private-mosquitto verify \
  --manifest "$private_manifest"
```

The source archive is accepted only after the frozen SHA-256 matches. The
manifest binds the platform, architecture, build recipe, exact source hash,
final executable paths and both binary hashes. Public reports omit absolute
paths.

## Native Broker preparation

The native board-lab entrypoint is:

```text
greenhouse-manager-node-mqtt-board-lab-native
```

Use a private workspace outside Git whose path contains no whitespace. For a
multi-step board matrix, use a persistent private state directory rather than a
short-lived compile directory.

```bash
set -euo pipefail

workspace="$HOME/.local/state/greenhouse-board-lab/<private-run-id>"
private_manifest="$HOME/.cache/greenhouse-mosquitto/2.0.21/darwin-x86_64/manifest.json"
lab_ip="<literal-private-LAN-IPv4>"

mkdir -p "$workspace"
chmod 700 "$workspace"

greenhouse-manager-node-mqtt-board-lab-native plan \
  --workspace "$workspace" \
  --private-mosquitto-manifest "$private_manifest" \
  --bind-host "$lab_ip" \
  --port 18883

greenhouse-manager-node-mqtt-board-lab-native create \
  --workspace "$workspace" \
  --private-mosquitto-manifest "$private_manifest" \
  --bind-host "$lab_ip" \
  --port 18883 \
  --confirmation M2-NONPRODUCTION-BOARD-LAB
```

The selected address must be reachable from the dedicated board, must not be a
production service address, and must not be `0.0.0.0` or globally routable.

`create`:

1. creates and binds a private runtime workspace;
2. generates random candidate and observer passwords;
3. hashes the Broker password file in place;
4. writes a private `secrets.yaml` containing Broker and candidate values;
5. starts only the workspace-bound private Mosquitto process;
6. preserves anonymous access;
7. writes redacted public reports only.

Edit only the Wi-Fi placeholders in the private workspace `secrets.yaml`. Do
not paste Wi-Fi or MQTT secrets into GitHub, chat, logs or shell command
history.

## Non-board Broker checks

Complete these before attaching or flashing a test board:

```bash
set -euo pipefail

greenhouse-manager-node-mqtt-board-lab-native smoke-valid \
  --workspace "$workspace"

greenhouse-manager-node-mqtt-board-lab-native invalidate-candidate \
  --workspace "$workspace"

greenhouse-manager-node-mqtt-board-lab-native smoke-invalid \
  --workspace "$workspace"

greenhouse-manager-node-mqtt-board-lab-native restore-candidate \
  --workspace "$workspace"

greenhouse-manager-node-mqtt-board-lab-native smoke-valid \
  --workspace "$workspace"

greenhouse-manager-node-mqtt-board-lab-native stop \
  --workspace "$workspace"

greenhouse-manager-node-mqtt-board-lab-native start \
  --workspace "$workspace"

greenhouse-manager-node-mqtt-board-lab-native smoke-valid \
  --workspace "$workspace"
```

The invalid-candidate check proves only that the Broker rejected the probe and
anonymous continuity remained available. The ESP32-C6 firmware must continue
to classify its public disconnect callback conservatively as
`generic_candidate_connection_failure`.

## Isolated source worktree for the physical run

Use a dedicated detached worktree bound to the exact tested repository commit.
Do not place board-lab secrets in the normal development worktree.

```bash
set -euo pipefail

source_repo="$HOME/HomeAssistant-local-test"
board_worktree="$HOME/.local/state/greenhouse-board-lab/<private-run-id>/source"
required_commit="<tested-main-commit>"

mkdir -p "$(dirname "$board_worktree")"
git -C "$source_repo" worktree add --detach "$board_worktree" "$required_commit"

install -m 600 "$workspace/secrets.yaml" \
  "$board_worktree/firmware/esphome_rc/f1_0_rc2/secrets.yaml"
```

The source worktree, runtime workspace and fault-matrix records remain private
local state. They are removed only by the final cleanup procedure after all
required evidence has been reviewed.

## Build targets

### Minimal authentication-only target

This target is useful only for generic ESP32-C6 compile or protocol debugging.
It must not be used to claim LCD, sensor or RS485 continuity.

```bash
set -euo pipefail

install -m 600 "$workspace/secrets.yaml" \
  "$board_worktree/firmware/esphome_rc/board_lab/m2_node_auth/secrets.yaml"

cd "$board_worktree/firmware/esphome_rc/board_lab/m2_node_auth"
esphome config greenhouse_mqtt_auth_board_lab.yml
esphome compile greenhouse_mqtt_auth_board_lab.yml
```

### Full product-PCB target

Use only this target for the physical fault matrix on a dedicated greenhouse
PCB:

```bash
set -euo pipefail

cd "$board_worktree/firmware/esphome_rc/f1_0_rc2"

RC2_CONFIG=f1_0_rc2_m2_node_auth_board_lab.yml \
  bash tools/rc2.sh config

RC2_CONFIG=f1_0_rc2_m2_node_auth_board_lab.yml \
  bash tools/rc2.sh compile

RC2_CONFIG=f1_0_rc2_m2_node_auth_board_lab.yml \
  bash tools/rc2.sh run --device <serial-device>
```

Before the first USB flash, verify all of the following:

- the selected PCB is dedicated to this non-production test;
- it is not a deployed or production monitoring node;
- its GPIO, LCD, SCD30, SHT30, GY30/BH1750, RS485 soil sensor and power wiring
  match the RC2 product target;
- GPIO9 remains untouched; it is not a runtime test input;
- the board and Mac are on the intended isolated/private laboratory network;
- the project-private Broker is running and reachable;
- no T1, production Mosquitto or production Home Assistant endpoint is used.

The first USB flash, reset, power cuts, Wi-Fi interruption, Broker stop/start,
candidate-lease observation and LCD/sensor/RS485 observations are operator actions. They
must not be automated against an unidentified board.

After boot:

- the first soil read follows the 15-second warm-up;
- soil sensor power remains on during normal operation;
- later soil query attempts follow the frozen 20-second cadence;
- SCD30 updates follow the frozen 11-second cadence;
- local display and sensor functions continue without Broker availability.

Any cadence drift blocks the local-continuity cases.

## Observation and control

Capture redacted heartbeats:

```bash
set -euo pipefail

greenhouse-manager-node-mqtt-board-lab-native observe \
  --workspace "$workspace" \
  --duration 30 \
  --output "$workspace/heartbeats.jsonl"
```

The full target heartbeat provides non-secret runtime fields for local loop
progress, battery mode, soil counters and whether air, CO2, light and soil
entities have produced states. LCD appearance and sensor plausibility remain
operator observations; heartbeat booleans do not replace them.

Publish a non-production control message:

```bash
set -euo pipefail

greenhouse-manager-node-mqtt-board-lab-native control \
  --workspace "$workspace" \
  --control-command activate \
  --confirmation M2-NONPRODUCTION-BOARD-LAB
```

Supported commands:

```text
activate
observe-success
observe-failure
commit
rollback
hold-reboot-anonymous
release-reboot-anonymous
hold-reboot-candidate
release-reboot-candidate
```

`commit` remains a separate operator action and is never sent automatically.
The reboot-hold commands are RAM-only deterministic fault-injection hooks. They
pause the next adapter-requested reboot only after the selected profile has
been persisted. Releasing the hold performs the pending safe reboot.

An uncommitted candidate has a 10-minute lease. If it is not committed before
expiry, the adapter persists anonymous and safely reboots. If the board starts
again after the first uncommitted candidate boot, it selects anonymous before
MQTT initialization. The matrix observes these automatic paths; it does not
request a physical rollback input.

GPIO9 is reserved solely for factory/R&D or authorized-service ROM USB
download. Do not press it during this matrix. End-user OTA recovery must never
instruct a user to open the enclosure, touch the PCB, or press GPIO9. Automatic
firmware-image OTA rollback remains a separate product gate until its
bootloader, first-boot health confirmation, A/B images, and physical-board
evidence are complete; USB ROM reflash is a service last resort.

## Serial secret check

```bash
set -euo pipefail

greenhouse-manager-node-mqtt-board-lab-native check-serial-log \
  --workspace "$workspace" \
  --log "$workspace/serial.log"
```

The check fails closed if a generated candidate password, observer password or
configured Wi-Fi secret appears verbatim.

## Fault-matrix records

Initialize one blocked record for every required case:

```bash
set -euo pipefail

greenhouse-manager-node-mqtt-board-lab-native init-matrix \
  --output "$workspace/fault-matrix.jsonl"
```

After each physical test, edit only the corresponding private JSON line. A case
may be marked `pass` only when `operator_observed=true` and at least one
non-secret evidence fingerprint is present.

Summarize:

```bash
set -euo pipefail

greenhouse-manager-node-mqtt-board-lab-native summarize \
  --records "$workspace/fault-matrix.jsonl"
```

The summary exits nonzero until every required case passes, every evidence
field is present, no duplicate case exists, and all production-safety flags
remain false.

## Cleanup

Cleanup is a separate final action after all private records have been reviewed.

```bash
set -euo pipefail

greenhouse-manager-node-mqtt-board-lab-native destroy \
  --workspace "$workspace"

git -C "$source_repo" worktree remove "$board_worktree"
```

Remove ignored local `secrets.yaml` copies before removing the worktree. The
destroy command stops only the process bound to the matching workspace marker,
manifest and configuration. It does not remove the verified private Mosquitto
binary cache and does not claim secure erasure of flash, NVS, SSD blocks or
backups.

A successful local matrix does not authorize production migration, production
credential generation, T1 mutation or anonymous MQTT closure.
