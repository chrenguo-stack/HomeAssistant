# N3W KF-089 Board B ID03 isolated esptool 5.2.0 runtime materialization — 2026-09-11

## Why this gate exists

The previously recovered Python 3.11.9 executable now imports esptool 5.3.1. This is a host-toolchain drift. ID03 has not been claimed and Board B has not been opened.

The original P0 specification prohibited package installation *inside P0*. It also required STOP when no compatible existing environment was available. We are now in a separate host-only remediation gate, so the correct next step is to materialize a disposable, isolated esptool 5.2.0 runtime without changing the global Python environment.

## Safety model

```text
HOST_ONLY=true
ID03_CLAIMED=false
BOARD_ACCESS=false
GLOBAL_PYTHON_MUTATION=false
GLOBAL_PACKAGE_UNINSTALL=false
GLOBAL_PACKAGE_DOWNGRADE=false
```

Use the already recovered Python 3.11.9 executable as the process interpreter. Install the exact esptool 5.2.0 package and its dependencies into a fresh private temporary `--target` directory. Launch Guard with that directory prepended through `PYTHONPATH`. This preserves the exact interpreter while shadowing the drifted global esptool 5.3.1 only for this process tree.

## esptool source authority

Official PyPI esptool 5.2.0 source distribution:

```text
PACKAGE=esptool
VERSION=5.2.0
SDIST=esptool-5.2.0.tar.gz
SDIST_SHA256=9c355b7d6331cc92979cc710ae5c41f59830d1ea29ec24c467c6005a092c06d6
UPSTREAM_TAG=v5.2.0
UPSTREAM_COMMIT=ff4aa4af5c9dbf190dcf3889d1d8ecfb3e8de876
```

The exact package source requires Python >=3.10 and declares dependencies including bitstring, cryptography, pyserial, reedsolo, PyYAML, intelhex, rich_click and click.

## Required host-only procedure

1. Create a new private temporary root outside every Git worktree.
2. Recover the exact previously bound Python 3.11.9 executable.
3. Download only `esptool==5.2.0` source distribution without installing it globally.
4. Verify the downloaded sdist SHA-256 exactly matches the frozen value above.
5. Install the verified sdist plus dependencies into a fresh private `--target` directory only.
6. Start a clean Python process with `PYTHONPATH=<target-dir>` and prove:
   - `sys.executable` is the recovered exact Python 3.11.9;
   - imported `esptool.__version__ == 5.2.0`;
   - esptool package path is inside the isolated target directory;
   - `esptool.cmds`, `esptool.loader`, and `esptool.targets.esp32c6` import from the same isolated package root.
7. Run the identity repair binding check from detached commit `af2ed8d5a62e84a83d4ba4593cf2442be3dff97d` under the same `PYTHONPATH`.
8. Run Guard `check-toolchain` under the same `PYTHONPATH` with the frozen ESP-IDF wrapper. It must prove esptool 5.2.0 and all reviewed retry/geometry constants.
9. Verify the frozen firmware artifact and private Board B identity, and preconstruct the final recovery command.
10. Only after every host-only check passes may ID03 claim be created and the already-preconstructed recovery command be executed with the identical environment.

## Failure behavior

Any failure before ID03 claim is host-only and does not retire ID03. Do not access Board B. Do not install/downgrade/uninstall the global esptool 5.3.1 package.

## Physical limits after host-only PASS

Unchanged: no app0 reflash, verify existing app0 first, at most one 32-byte otadata mutation, no mutation retry, no automatic rollback, no Board A access, no T1 mutation.
