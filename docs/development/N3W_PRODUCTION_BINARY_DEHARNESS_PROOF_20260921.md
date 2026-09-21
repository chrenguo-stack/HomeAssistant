# N3-W production binary de-harness proof

Updated: 2026-09-21  
Status: PROOF_CI_PREPARED

```text
GATE=N3W_PRODUCTION_BINARY_DEHARNESS_PROOF_20260921_01
SOURCE_HEAD=c1b3d9d016d06c21c9ff7070c0043163739565ca
FROZEN_PR437_SOURCE_HEAD=4270f24a92a87dd5239d781ebba624c2f34b7fc2
TARGET=firmware/esphome_rc/f1_0_rc2/f1_0_rc2_n3w_target.yml
```

The proof compiles the exact production target, then inspects three independent
surfaces:

1. demangled symbols from `firmware.elf`;
2. the linker `firmware.map`;
3. printable strings from the actual flashable `firmware.bin`.

Forbidden markers are taken from the frozen PR #437 lab-only implementation,
including `Phase4PhysicalHarness`, `N3wLabDiagnostics`,
`N3wRtcBreadcrumb`, `gh_n3w_diag`, the three retired lab source names,
and Phase4 lab telemetry/config markers.

The test also has positive controls. The ELF must contain
`GreenhouseN3wCore` and `SimpleProductComponent`; the binary must contain
`gh.telemetry/1` and `air_temperature_c`. This prevents an empty or
non-N3-W image from passing merely because no lab strings are present.

This gate does not publish or bind a release artifact and does not flash a
board.
