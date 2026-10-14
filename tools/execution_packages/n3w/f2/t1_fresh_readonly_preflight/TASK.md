# F2 Fresh T1 Read-only Preflight Execution Package

Gate:

N3W_T1_PER_DEVICE_FRESH_ARMBIAN_AUTOMATED_DEPLOYMENT_F2_FRESH_T1_READONLY_PREFLIGHT_20261014_01

This package is the versioned Mac-side executor for the fresh-T1 F2 read-only gate.

It does not authorize F3, product deployment, package installation, service activation, or any board operation.

## What F2 proves

F2 must prove, on the selected T1 and before any deployment mutation:

- the exact approved Armbian/Ubuntu release and ARM64 architecture;
- first-boot operational readiness: synchronized machine-id, SSH host keys, SSH/NetworkManager state, and completed Armbian firstrun service;
- default route, DNS resolution and synchronized time;
- Docker/Compose is either already ready, or the exact Ubuntu resolute/universe source is configured for the later F3 baseline-install step; when a fresh host has no local APT index yet, F2 records that state without running apt update and defers candidate resolution to the separately authorized F3 mutation gate;
- product containers/images/volumes/networks/paths/units/listeners are absent;
- old provisioning transaction, F3 authorization ledger and fresh-bootstrap staging residue are absent;
- the exact deployable artifact is bound to the expected artifact source head;
- the F1B one-image-at-a-time transport capacity model passes on the real target.

F2 PASS means only that F3 authorization may be requested later.

## Read-only transport

The OS-identity probe and F2 supplement are streamed over SSH stdin into sudo noninteractive Python with bytecode writes disabled. No probe file is copied to T1.

The exact confirmation is:

READONLY FRESH T1 PREFLIGHT: YES

## Evidence boundary

Private evidence is written only to an operator-selected local directory outside the repository:

- directory mode: 0700;
- evidence files: exclusive-create regular files, mode 0600;
- public result contains a SHA-256 of the SSH target, not the raw target;
- secret values are not intentionally collected.

## Execution authority

The executor requires the exact F2 source head and the exact deployable artifact authority at execution time. The artifact source must be an ancestor of the F2 executor source head, allowing this F2-only package to stay in a small PR while using the exact deployable artifact built from the merged product-source base.

Current boundary:

T1_ACCESS=false
T1_MUTATION=false
T1_FILE_WRITE=false
LIVE_RUNTIME_MUTATION=false
SYSTEMD_LIVE_MUTATION=false
PRODUCTION_SERVICE_START=false
AUTHORIZATION_CLAIM=false
F3_AUTHORIZED=false
BOARD_ACCESS=false
MERGE=false
