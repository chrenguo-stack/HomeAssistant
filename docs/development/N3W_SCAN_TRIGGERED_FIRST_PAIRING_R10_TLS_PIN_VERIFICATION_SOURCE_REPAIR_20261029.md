# N3-W R10 TLS pin verification source repair — 2026-10-29

## Gate

`N3W_SCAN_TRIGGERED_FIRST_PAIRING_R10_TLS_PIN_VERIFICATION_SOURCE_REPAIR_20261029_01`

This repair is stacked on PR #725 exact product/UI source head:

- `44d3320877a0a47c3dd728182fae2f209bffbc0f`

No T1 mutation, Board write/reset, NVS mutation, phone pairing retry, or merge is authorized by this source-repair gate.

## Physical failure evidence

Board D R10 physical acceptance reached the explicit user action `开始注册`, then the phone showed:

- `E02 主机不可用`

Read-only T1 state remained:

- `first_registration_attempts=[]`
- unresolved first registration = 0
- active registration count = 1
- TCP/47112 closed

T1-side LAN checks proved:

- TCP/47110 listening on `0.0.0.0:47110`
- trusted-product-LAN guard allowed `192.168.68.0/24`
- TLS 1.2 handshake from LAN passed
- served registration certificate SHA-256 matched the candidate-advertised pin
- the registration certificate is P-256 ECDSA with SHA-256 signature and serverAuth usage
- exactly one registration candidate was advertised, at `192.168.68.126:47110`

The one authorized forensic retry captured this exact ordering:

1. Board D -> T1 TCP SYN
2. T1 -> Board D SYN/ACK
3. Board D -> T1 ACK
4. Board D -> T1 TLS ClientHello
5. T1 -> Board D TLS ServerHello/server handshake flight
6. Board D -> T1 TLS Alert
7. Board D -> T1 RST

No HTTP confirm transaction became durable.

Therefore the failure is inside the Board D TLS verification path after TCP establishment and before the HTTP `/v1/registration/confirm` request.

## Exact mbedTLS root cause

ESP-IDF 5.5.4 binds the Espressif mbedTLS submodule at:

- `ffb280bb63c78bfec1e1ab55040671768c85c923`

In that exact source, `mbedtls_ssl_verify_certificate()` explicitly returns `MBEDTLS_ERR_SSL_CA_CHAIN_REQUIRED` when:

- auth mode is `MBEDTLS_SSL_VERIFY_REQUIRED`; and
- no CA chain or trusted-CA callback is configured.

The R10 firmware used:

- `MBEDTLS_SSL_VERIFY_REQUIRED`
- `mbedtls_ssl_conf_verify(... verify_pinned_leaf ...)`
- no `mbedtls_ssl_conf_ca_chain()`
- no trusted-CA callback

The design authority, however, is the exact leaf SHA-256 pin carried by the user-selected candidate, not a conventional CA chain.

## TLS repair

The repair changes the TLS configuration to:

- `MBEDTLS_SSL_VERIFY_OPTIONAL`
- no CA chain
- exact leaf SHA-256 pin callback remains mandatory
- pin mismatch is returned as `MBEDTLS_ERR_X509_FATAL_ERROR`
- post-handshake `leaf_seen && leaf_matched` remains mandatory
- HTTP request construction remains after the pin gate
- Setup Secret is never sent before exact pin success
- `MBEDTLS_SSL_VERIFY_NONE` remains forbidden

This is safe with the exact mbedTLS implementation because OPTIONAL only suppresses ordinary certificate-chain rejection; fatal errors returned by the verification callback remain fatal.

## 60-second user confirmation window

The previous 30-second candidate lifetime was too short for normal phone interaction.

The R10 repair uses two explicit 60-second windows:

1. discovery candidate lifetime:
   - Manager advertisement default/validation: 60 seconds
   - ESP32 candidate parser contract: 60 seconds
2. post-selection user-confirmation lifetime:
   - selecting a still-valid candidate starts a fresh 60-second device-side confirmation deadline
   - the first rendered button value is `开始注册（59s）`
   - the value then decrements once per second

The selected-candidate status exposes only a non-sensitive `expires_in_s` value. The countdown is derived from the device-side monotonic confirmation deadline rather than an independent phone timer.

At 0 seconds:

- the button is disabled;
- the page re-polls the device;
- the device-side expiry remains authoritative;
- stale selection resolves to E07;
- no bootstrap can begin after expiry.

Once `/api/v1/register/begin` is accepted inside that confirmation window, the irreversible user boundary has been crossed. The subsequent TLS/HTTP bootstrap is not invalidated merely because the earlier discovery-candidate TTL expires while the transaction is already starting.

No T1 locator, TLS pin, manager_id, system_id, Setup Secret, pairing ID, MQTT password, or other secret is exposed to the browser.

## Regression guards

Focused contracts are updated to require:

- pin-only TLS uses OPTIONAL, never REQUIRED or NONE;
- no CA chain/callback is configured in the pin-only transport;
- pin mismatch remains fatal;
- `leaf_seen && leaf_matched` is checked before HTTP construction;
- Manager and ESP32 both freeze candidate TTL at 60 seconds;
- candidate-selected status publishes `expires_in_s`;
- selection starts a fresh 60-second server-side confirmation deadline;
- the begin button starts at the `59s` presentation and uses the server-bound countdown;
- 0 seconds disables begin and rechecks the device;
- server-side begin still checks the selected confirmation deadline;
- accepted begin is not later cancelled by the discovery TTL.

## Physical revalidation requirement

Source/CI PASS is not sufficient to close this failure.

A new exact physical-acceptance artifact must be built from the repaired source, and Board D must be rewritten under a separate authorization.

The next physical run must prove at minimum:

1. candidate selection shows the countdown;
2. Board D completes the TLS handshake with the exact selected pin;
3. durable first-registration attempt is created;
4. 47112 opens only for the identity-bound transaction;
5. Manager COMMIT becomes durable;
6. 47112 closes after success;
7. phone shows `联机注册成功`;
8. LCD page 5 shows `已联机注册`;
9. normal MQTT/HA telemetry continuity is restored.

The failed R10 artifact remains evidence and must not be reused for another registration attempt.
