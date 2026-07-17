# M2 ESP32-C6 node-auth native Broker board-lab contract V1

## 1. Purpose

This contract adds a native Mosquitto backend for the dedicated, non-production ESP32-C6 node-auth runtime fault matrix. It exists because the verified local macOS environment can run Python, ESPHome and ESP32-C6 builds but does not use Docker as a supported local capability.

The existing Docker backend remains the canonical isolated CI fixture. The native backend is an additional local execution path for a physical test board that must reach a Broker on the operator's local network.

This contract does not authorize production node migration, credential generation, T1 mutation, Dynamic Security production control, or anonymous MQTT closure.

## 2. Fixed safety boundary

The native backend must:

- bind only to a literal non-global IPv4 address;
- reject `0.0.0.0`, multicast and globally routable addresses;
- use Mosquitto from the explicitly supported `2.0.x` or `2.1.x` release families and record the exact observed version;
- preserve `allow_anonymous true`;
- use only the fixed board-lab candidate, anonymous and observer identities;
- create random non-production passwords only inside a mode-`0700` private workspace;
- keep private files mode `0600`;
- hash the Mosquitto password file in place with `mosquitto_passwd -U`;
- omit executable paths, workspace paths and raw secrets from public reports;
- bind PID validation to both the Mosquitto executable name and the private workspace configuration path before stopping a process;
- refuse to destroy a workspace whose marker and manifest do not match;
- keep all production, credential-delivery and anonymous-closure readiness flags false.

The native backend must not:

- connect to the production T1 or production Mosquitto;
- read Home Assistant `.storage`;
- invoke Dynamic Security control topics;
- create or deliver production node credentials;
- flash or migrate a production monitoring node;
- claim secure erasure of flash, NVS, SSD blocks or backups;
- claim that local or CI success completes the 50-case physical-board matrix.

## 3. Local task classification

| Work | Required environment |
|---|---|
| Python unit and contract tests | local `gh-local fast` or GitHub CI |
| ESPHome config and cached ESP32-C6 compile | local Mac or GitHub CI |
| Native Mosquitto lifecycle and MQTT smoke matrix | local Mac and clean Ubuntu CI |
| Docker-pinned Mosquitto regression | GitHub CI or supported Linux Docker environment |
| USB flash, LCD, sensors, RS485, Wi-Fi interruption and power cuts | dedicated physical ESP32-C6 test board |
| Any production T1 or node mutation | separate M2 live gate and precise authorization |

Native Broker success does not replace Docker regression, required GitHub checks, board observation or production gates.

## 4. Public CLI

The entrypoint is:

```text
greenhouse-manager-node-mqtt-board-lab-native
```

Lifecycle commands:

```text
plan
create
start
stop
invalidate-candidate
restore-candidate
destroy
```

The existing observation and matrix commands are also exposed:

```text
smoke-valid
smoke-invalid
observe
control
check-serial-log
init-matrix
summarize
```

`create` requires the exact non-production confirmation:

```text
M2-NONPRODUCTION-BOARD-LAB
```

## 5. Private workspace preparation

Use a path without whitespace. The path must not be inside the Git repository.

On macOS, the project uses the Homebrew Mosquitto package. The current Homebrew package is in the supported `2.1.x` family. Installation is an operator-local dependency change and must be completed before running the native lab; it does not start the Broker service automatically for this project workflow.

```bash
brew install mosquitto
```

The native lab starts its own workspace-bound process and must not use `brew services start mosquitto`.

```bash
set -euo pipefail
workspace="$(mktemp -d "${TMPDIR:-/tmp}/gh-m2-native-board-lab-XXXXXXX")"
chmod 700 "$workspace"

greenhouse-manager-node-mqtt-board-lab-native plan \
  --workspace "$workspace" \
  --bind-host <literal-non-global-lab-ip> \
  --port 18883

greenhouse-manager-node-mqtt-board-lab-native create \
  --workspace "$workspace" \
  --bind-host <literal-non-global-lab-ip> \
  --port 18883 \
  --confirmation M2-NONPRODUCTION-BOARD-LAB
```

The selected bind address must be reachable from the dedicated test board and must not be a production service address. The tool resolves the local `mosquitto` and `mosquitto_passwd` executables and rejects versions outside the explicitly supported `2.0.x` and `2.1.x` families.

## 6. Pre-board smoke sequence

Before connecting or flashing a board, complete:

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

Success proves only that the native non-production Broker accepts the valid candidate, rejects the invalid candidate, preserves anonymous continuity, restores credentials and survives a controlled stop/start cycle.

## 7. Physical-board boundary

Only the full product-PCB target may be used for the physical matrix:

```text
firmware/esphome_rc/f1_0_rc2/f1_0_rc2_m2_node_auth_board_lab.yml
```

The following require explicit operator actions and observations:

- selecting and confirming a dedicated non-production ESP32-C6 board;
- first USB flash;
- board reset and power interruption;
- Wi-Fi interruption and restoration;
- native Broker stop and restart while the board is running;
- GPIO9 offline rollback operation after normal boot;
- LCD five-page continuity;
- SCD30, SHT30, light and soil sensor plausibility;
- RS485 soil warm-up, power continuity and 20-second query cadence;
- low-battery and recovery behavior;
- serial, heartbeat, OTA and crash log evidence.

No production board may be used.

## 8. Evidence and cleanup

Public reports may contain fingerprints and non-secret state only. Physical observations remain in the private fault-matrix JSONL file.

Cleanup:

```bash
set -euo pipefail

greenhouse-manager-node-mqtt-board-lab-native destroy \
  --workspace "$workspace"
```

The destroy operation validates the private workspace binding and stops only the matching native Mosquitto process. It removes the workspace but does not claim secure erasure.

## 9. Gate state after implementation

Repository and CI completion may set:

```text
native_board_lab_source_complete=true
native_board_lab_clean_linux_integration_complete=true
local_mac_native_board_lab_pending=true
real_board_runtime_fault_matrix_pending=true
ready_for_node_credential_generation=false
ready_for_live_apply=false
ready_for_anonymous_closure=false
```

The next user interruption is permitted only when source, focused tests, GitHub native integration and Docker regression are complete, and the remaining action is a dedicated test-board or local-Mac operation.
