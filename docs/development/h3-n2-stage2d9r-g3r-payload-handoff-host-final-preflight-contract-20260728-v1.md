# H3/N2 Stage 2D-9R G3R payload-handoff repaired host-final preflight contract

## Accepted boundary

This successor layer is based exactly on Draft PR #190 HEAD
`261f24dc7e01fe9eaaf0a607a2868cd4411286bf` and public repair Artifact
`8682468219` / `418827f2d0f931ee459c1b2204c8396dd71b98d5731dd7c072fb9abaf3d2caa4`.

The retired physical D2
`D2-H3N2-STAGE2D9R-G3R-REPAIRED-PHYSICAL-20260728-01` remains permanently
`CONSUMED_FAILED` with `IMMUTABLE_PAYLOAD_INVALID`. It is never replayed or
reinterpreted as unclaimed.

## Purpose

The layer freezes a new host-only final-preflight review package after the
shell/Python payload handoff repair. It validates the exact repair Artifact,
constructs a final physical execution package with a new D2 identity, and
provides an inert host probe for a later independently authorized offline
preflight.

## Preserved execution behavior

- immutable and recovery TAR bytes remain unchanged;
- the original TAR files and fresh empty extraction roots remain separate;
- macOS path aliases are normalized using real paths;
- authorization-created failures before the inner claim are consumed as
  `CONSUMED_FAILED_PRECLAIM` and are non-replayable;
- normal execution continues through the frozen executor core;
- locked recovery remains test-partition-only `read -> erase_region -> read`;
- whole-chip recovery erase and recovery `write_flash` remain prohibited.

## Host-only preflight

The host probe is inert unless invoked with a new exact one-shot H2
authorization. An authorized run may only:

1. validate the public review package and exact hashes;
2. hash Python, OpenSSL, esptool, pyserial and Mosquitto toolchain files;
3. validate the existing `tlsvalid03` private custody entirely offline;
4. emit an `authorized=false` physical-D2 request draft.

It does not enumerate USB or serial devices, open a port, invoke esptool, start
a Broker, access a board, read or write Flash/NVS, or execute PREPARE/VERIFY.

## Current authorization state

The source review, deterministic package build and public Artifact are allowed.
Host-preflight execution and physical execution remain separately unauthorized.
