# N3W KF-089 Board B ID03 host toolchain rebind — 2026-09-11

## Current state

The ID03 physical workflow has not been claimed and Board B has not been opened.

```text
AUTHORIZATION_ID=N3W_KF089_BOARD_B_EXISTING_APP0_RECOVERY_TO_SLOT0_IDENTITY_R1_20260911_03
AUTHORIZATION_GRANTED=true
AUTHORIZATION_CLAIMED=false
PHYSICAL_DEVICE_OPEN_OCCURRED=false
FLASH_READ=false
FLASH_WRITE=false
OTADATA_MUTATION=false
```

The latest STOP occurred during host-only command preflight because the Python interpreter selected for execution could not import the already-verified esptool 5.2.0 runtime. No package installation or upgrade is permitted.

## Important historical fact

The earlier P0R1 host-only remediation already proved that one existing local Python 3.11.9 interpreter could execute the Guard and import the exact esptool 5.2.0 runtime with the reviewed ESP-IDF v5.5.4 wrapper. Therefore the immediate task is not to install esptool. It is to recover and rebind the exact previously proven local interpreter/runtime from private P0R1 evidence.

## Required host-only remediation

Before creating ID03 claim or opening Board B:

1. Recover from private P0R1 evidence the exact Python executable path that produced:
   - `LOCAL_PYTHON_VERSION=3.11.9`
   - `EXACT_PYTHON_SELF_BINDING=PASS`
   - `LOCAL_ESPTOOL_VERSION=5.2.0`
   - `LOCAL_ESPTOOL_RUNTIME_BINDING=PASS`
   - `LOCAL_GUARD_CHECK_TOOLCHAIN=PASS`
2. Using that exact executable only, run host-only probes which do not enumerate or open USB/serial:
   - print `sys.executable` and Python version;
   - import `esptool`, `esptool.cmds`, `esptool.loader`, `esptool.targets.esp32c6`;
   - require `esptool.__version__ == 5.2.0`;
   - record module paths/hashes privately and compare them with the prior P0R1 private evidence if available.
3. Use the exact detached repair worktree at `af2ed8d5a62e84a83d4ba4593cf2442be3dff97d` and run the repair binding check under that same Python executable.
4. Run the Guard host-only `check-toolchain` using that same Python executable and the exact reviewed ESP-IDF wrapper.
5. Only if all checks PASS may the executor build the final recovery command, create the ID03 claim, and immediately execute it.

If the exact P0R1 interpreter path no longer exists or no longer imports the same esptool 5.2.0 runtime, STOP as `LOCAL_TOOLCHAIN_DRIFT`. Do not install, upgrade, create a new environment, or substitute a different interpreter inside this gate. A different pre-existing interpreter would require a separate host-only toolchain rebind/adjudication before physical use.

## Safety

Until all host-only checks pass:

```text
USB_ENUMERATION=false
SERIAL_OPEN=false
BOARD_ACCESS=false
FLASH_READ=false
FLASH_WRITE=false
OTADATA_WRITE=false
ID03_CLAIM=false
```

No new user authorization is required while ID03 remains unclaimed.
