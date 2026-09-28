# N3-W KF-098 Private Evidence Traceability Alignment — 2026-09-28

Status: `PUBLIC_SAFE_TRACEABILITY_RECORDED`

## Purpose

This record closes the remaining KF-098 evidence-traceability follow-up without publishing the private raw packet capture.

The raw capture remains outside the public repository. This file records only the public-safe digest, time window, exact Manager runtime image, hashed Board/pairing identifiers, observed protocol markers, HTTP status codes, and the exact simplified-pairing error code.

## Private capture authority

```text
OBSERVATION_STARTED_AT=2026-09-28T07:21:20.662424Z
OBSERVATION_ENDED_AT=2026-09-28T07:22:00.684536Z
OBSERVATION_SECONDS=40

CAPTURE_BYTES=74347
CAPTURE_SHA256=bdfd0b66c303b3e16755f999dbf12886bdb1f3de2c182ca3ffb2ab22cd2db5ab
CAPTURED_PACKET_COUNT=208

MANAGER_IMAGE=sha256:b806e7c8b97cc757965161a989f954df09427aa7d2700a6503e56e49cc8f9e4f
MANAGER_STARTED_AT=2026-09-28T04:11:52.251251149Z

BOARD_IP_SHA256=89e267e1a72636e700eece9f743c384362591e7eb224911fc36f728bac53eaee
HARDWARE_ID_SHA256=cd90494824273fb6050c29989370690984487f7cdaea89ac4ff8b5eebc4371b0
PAIRING_ID_SHA256=142d1e0c9fc035645ce38e4681add39ba3ed5b3b0d60e14a4a1dfa398ab2472e
```

The capture file itself is deliberately not committed because it contains private network and device identifiers. Future evidence reconciliation must bind any private copy by the exact `CAPTURE_SHA256` and byte count above.

## Observed protocol markers

```text
DISCOVERY_QUERY=true
DISCOVERY_RESPONSE=true
HELLO_REQUEST=true
HELLO_RESULT=true
REPAIR_INTENT_REQUIRED=true
TRANSACTION_CONTINUE=true
BEGIN_REQUEST=true
SIMPLE_ERROR=true

HTTP_CODES=200,403
HELLO_STATUS=rejected
BEGIN_ERROR=setup_secret_unavailable
```

This supplements the earlier public-safe closure record. The previous live capture established that discovery returned the current route-selected T1 address and that Board B connected to current T1 TCP/47112. This follow-up capture binds the later application-level rejection to the exact error payload.

## Interpretation

The exact observed sequence is:

```text
/v2/pairing/hello
-> HTTP 200
-> gh.pair.simple-hello-result/1
-> status=rejected
-> reason=repair_intent_required
-> transaction_disposition=continue

/v2/pairing/begin
-> HTTP 403
-> gh.pair.simple-error/1
-> error=setup_secret_unavailable
```

The `403` is no longer interpreted from status code alone. The observed application error is explicitly `setup_secret_unavailable`.

The Manager-side rejection is fail-closed and correctly preserves the existing durable identity. The capture also exposed an unnecessary client control-flow step: the firmware treated every wire-level `transaction_disposition=continue` as permission to enter `/begin`, even when `status=rejected`. That produced a predictable `setup_secret_unavailable` request before a repair transaction had been accepted.

PR #500 repairs the client interpretation without changing the Manager wire schema: a `rejected + continue` hello keeps the same pairing ID and returns the firmware to its bounded retry loop without calling `/begin`; successful non-rejected `continue` results may proceed; terminal `expired` or `replay_detected` results still renew the random pairing ID.

## Follow-up closure

```text
PRIVATE_RAW_CAPTURE_PUBLISHED=false
PUBLIC_SAFE_CAPTURE_DIGEST_RECORDED=true
OBSERVATION_WINDOW_RECORDED=true
BOARD_BINDING_HASH_RECORDED=true
MANAGER_IMAGE_BINDING_RECORDED=true
BEGIN_EXACT_ERROR_RECORDED=true
REJECTED_CONTINUE_CLIENT_FLOW_DEFECT_IDENTIFIED=true
REJECTED_CONTINUE_CLIENT_FLOW_REPAIR_PR=500

KF098_REOPEN=false
KF098_ROUTE_STATUS=CLOSED_PASS
KF098_KNOWN_FAILURE_STATUS=GUARDED
```
