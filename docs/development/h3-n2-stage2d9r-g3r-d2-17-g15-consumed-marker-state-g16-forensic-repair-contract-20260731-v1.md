# D2-17 G15 consumed marker-state drift and G16 forensic repair

## Frozen predecessor terminal

G15 returned `FAIL / TARGET_MAC_HOST_ONLY_FORENSIC_EXPORT_CONSUMED_FAILED`
with `G14_AUTHORIZATION_MARKER_STATE_DRIFT`.

- terminal record: `865f2955e26115bebacd13792e420ffb4166359ae525acb0cc854fd7ff6c0d05`;
- authorization record: `9307e9c122611c9242b23aec4ed5ef92d8d5f0e63fee02d5a16a81589308eb17`;
- authorization marker: `0e8c9e3750dcb15443fcd0e1c9a2d4874eb5e3a6fc39086af4ae04ff1c9d86bf`;
- private delivery binding: `7c59c984d513ff034dc669339d430b0cfb948db9e5cee8fbcc6cb91fd12e2bcd`;
- all physical-operation flags: `false`;
- G14 runtime mutated: `false`.

G15 is permanently consumed. Replay, package reuse, authorization reuse and
runtime mutation are forbidden.

G15 disposition binding:

`7bd04cf01416ce3a886c873a1a6054b2ab426f19edac38dfc88a9879e4cdd124`

## Deterministic root cause

G15 verified the exact bound G14 marker digest `223e4549c3f86c9a02e270f9672ccd056797b2e58175610e1d391ec46693a4f8` and then
separately required `marker.status == "CONSUMED_FAILED"`. The digest check
passed and the state assertion failed. The marker was authentic, but the
exporter made an unsupported state-value assumption.

The G15 terminal proves only that the exact marker state was not
`CONSUMED_FAILED`; it does not disclose the actual private marker state.

## G16 repair

G16 preserves all G15 validation by invoking the predecessor exporter while
bypassing only the named marker-state assertion. It then independently
revalidates the exact marker digest and accepts only this closed state set:

- `CLAIMED`;
- `CONSUMED_PASS`;
- `CONSUMED_FAILED`.

The actual state and its relation to the outer `CONSUMED_FAILED` terminal are
exported. All path, raw-log, command-material and secret exclusions remain.

G16 pending binding:

`6f772b70af1137c08480eeb1ae7af994f203a6fd2e4c665393aad22d02e73d54`

## Safety

G16 is host-only. It performs no board, USB, serial, esptool, Flash/NVS,
network, Broker, PREPARE, VERIFY, recovery, ACTIVATE or CLEANUP operation. It
does not mutate G14 or G15 runtime material.

A private G16 package requires the exact next decision gate and is one-shot.
