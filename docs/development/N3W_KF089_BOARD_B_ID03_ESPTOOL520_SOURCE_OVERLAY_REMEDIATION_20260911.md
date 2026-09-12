# N3W KF-089 Board B ID03 esptool 5.2.0 source-overlay remediation — 2026-09-11

## Situation

The isolated `pip --target` attempt for esptool 5.2.0 stopped while building a cryptography dependency because the host could not create a Rust cache lock. ID03 was not claimed and Board B was not opened.

This does not prove an esptool 5.2.0 defect. It is a packaging/build-environment problem.

## Remediation decision

Do not install or build esptool 5.2.0 or any dependency.

Instead, materialize the exact official esptool 5.2.0 source tree and prepend that source root to `PYTHONPATH` for the Guard process tree. The exact recovered Python 3.11.9 remains the interpreter. Existing already-working dependency modules from that Python environment may be used, but the imported `esptool` package and its `cmds`, `loader`, and `targets.esp32c6` modules must all resolve from the exact official source tree.

## Frozen esptool source authority

```text
UPSTREAM_REPOSITORY=espressif/esptool
UPSTREAM_TAG=v5.2.0
UPSTREAM_COMMIT=ff4aa4af5c9dbf190dcf3889d1d8ecfb3e8de876
EXPECTED_ESPTOOL_VERSION=5.2.0
```

The upstream commit records the version change to 5.2.0. The package source itself declares `__version__ = "5.2.0"`.

## Host-only procedure

Before any ID03 claim or Board B access:

1. Create a fresh private temporary source directory outside every HomeAssistant worktree.
2. Materialize `espressif/esptool` exactly at commit `ff4aa4af5c9dbf190dcf3889d1d8ecfb3e8de876` (for example with a shallow clone of tag `v5.2.0`, followed by exact `rev-parse HEAD` verification).
3. Require the esptool source checkout to be clean and exact at that commit.
4. Do not run pip install, build, wheel, setup, cargo, or Rust.
5. Using the already recovered exact Python 3.11.9, start a clean process with `PYTHONPATH=<exact-esptool-source-root>` and verify:
   - `sys.executable` is the recovered exact Python;
   - `esptool.__version__ == 5.2.0`;
   - `esptool.__file__`, `esptool.cmds.__file__`, `esptool.loader.__file__`, and `esptool.targets.esp32c6.__file__` all resolve under the exact source root;
   - the imported dependency set is sufficient for those imports without modifying packages.
6. Under the same environment, run the R1 repair binding check from exact HomeAssistant commit `af2ed8d5a62e84a83d4ba4593cf2442be3dff97d`.
7. Under the same environment, run Guard `check-toolchain` with the frozen ESP-IDF v5.5.4 wrapper. It must prove esptool 5.2.0 plus the reviewed retry and geometry constants.
8. Verify the frozen Schema-v5 firmware, private expected Board B identity, fresh empty evidence root, and the final recovery command.
9. Only after every host-only check passes may ID03 claim be created, immediately followed by the already-preconstructed recovery command under the identical environment.

## Important environment rule

Do not blindly set `PYTHONNOUSERSITE=1` if doing so hides dependencies already used by the recovered Python environment. The authoritative requirement is that all `esptool*` modules come from the exact 5.2.0 source tree, while no global package is modified.

The Guard read subprocess inherits the parent environment, so the same `PYTHONPATH` must remain set throughout the complete physical recovery workflow.

## Current authorization state

```text
AUTHORIZATION_ID=N3W_KF089_BOARD_B_EXISTING_APP0_RECOVERY_TO_SLOT0_IDENTITY_R1_20260911_03
AUTHORIZATION_GRANTED=true
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
BOARD_ACCESS=false
```

No new authorization is required while ID03 remains unclaimed.

## Failure behavior

Any failure before claim remains host-only. Stop without opening Board B and keep ID03 unclaimed. Do not fall back to global esptool 5.3.1 and do not install/build dependencies.
