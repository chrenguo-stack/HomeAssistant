# H3/N2 Stage 2D-9R G3R D2-14 payload extraction ownership repair

## Decision

`D1-H3N2-STAGE2D9R-G3R-D2-14-PAYLOAD-EXTRACTION-OWNERSHIP-REPAIR-20260730-01`

## Failure disposition

D2-13 is permanently `CONSUMED_FAILED_PRECLAIM` with
`IMMUTABLE_PAYLOAD_INVALID_ROOT`. Its authorization was created and consumed,
but was never claimed. No board, USB, serial, esptool, Flash, network, PREPARE
or VERIFY operation occurred. D2-13 is not replayable and none of its request,
authorization, decision, execution closure or execution package identities may
be reused.

## Root cause

The private outer layer extracted immutable and recovery TAR members into the
runtime payload roots and copied the TAR files into those roots. The inherited
inner payload layer is the designated extraction owner and intentionally
requires both roots to be empty mode-0700 directories. The double ownership
therefore failed before claim with `IMMUTABLE_PAYLOAD_INVALID_ROOT`.

## Repair contract

1. The future private outer layer may create only the runtime directory and two
   empty mode-0700 payload roots.
2. It must not extract either payload TAR and must not copy either TAR into a
   payload root.
3. The inner D2-14 launcher normalizes the package root and preserves D2-13's
   deterministic TAR argument injection.
4. D2-14 verifies both roots are empty before invoking the inherited inner
   parser. The inherited payload layer performs exactly one safe extraction.
5. A host-only root-ownership check must use the real shell launcher, paths
   containing spaces, both immutable/recovery TARs, and the real safe extraction
   implementation.
6. Preclaim failures after authorization creation must emit a stable result and
   marker while all physical-operation flags remain false.

## Safety boundary

The public successor is unauthorized. It creates no private package or physical
execution authorization. It does not connect or enumerate a board, open USB or
serial, invoke esptool, modify Flash/NVS, start a Broker, send PREPARE/VERIFY,
run recovery, claim/consume authorization, mark Ready, merge, release, tag or
deploy.
