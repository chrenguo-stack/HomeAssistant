# R6 TLS bootstrap implementation progress — 2026-10-27

Gate: `N3W_SCAN_TRIGGERED_FIRST_PAIRING_R6_TLS_BOOTSTRAP_SOURCE_IMPLEMENTATION_20261027_01`

## Bound source

- Baseline main: `2fbd0e9c2d3bf8a513ac318034e249511ffb6a2e`
- R5 merged PR: #694; merge `32c4eef68bce48ff7a379381ab0bfad60557ef57`
- R6 design/preflight: draft PR #696, head `de1cb7a07e3424182e460569e5b379a0992a572b`
- No T1/Board access; no live changes; no merge.

## First implementation increment

New files:

- `n3w_registration_bootstrap_client.h/.cpp`: pure confirm request/response boundary.
- `tests/n3w_registration/test_r6_confirm_parser_source_contract.py`: focused source checks (not executable native parser vectors).

Scope implemented:
- build exact `gh.registration.confirm/1` request from selected candidate and node-owned identity/secret;
- response rejects manager/system mismatch, invalid 47112 port/path, missing/invalid TTL, and malformed responses;
- terminal expired/replay result requires terminal disposition before signaling renewal;
- other rejected outcomes retain same pairing ID.

## NOT implemented / no PASS claim

1. ESP32 TLS transport with pre-body leaf DER fingerprint pinning. **Must prove no Setup Secret bytes are emitted before exact match.**
2. Current-STA-subnet validation for returned pairing_host, redirect prevention, bounded TLS/HTTP I/O.
3. Wiring R5 selection through confirmation into `SimplePairingClient` without invoking legacy background discovery.
4. Actual reuse of HMAC/HKDF/credential delivery/final ACK in the new selected-target flow.
5. New self-contained pending-ACK durable record, legacy compatibility, 47110 status, exact candidate relocation, reboot-safe TERMINAL_CLEANUP.
6. Strict session/node/consumed final ACK validation.
7. Native C++ tests, actual firmware compile, simulation/E2E, LCD R7 integration.

Important: source contract checks only inspect code; they cannot prove TLS or runtime correctness. They do not justify an R6 PASS.

## Next internal stop

Next source increment should first establish the concrete ESP-IDF TLS certificate verification API and a genuine pre-body no-secret-write test before wiring any Setup Secret into an HTTP transport. If it cannot be shown that fingerprint matching happens prior to request write, STOP rather than fall back to insecure HTTPS.

Branch remains separate from main. PR remains unmerged.
