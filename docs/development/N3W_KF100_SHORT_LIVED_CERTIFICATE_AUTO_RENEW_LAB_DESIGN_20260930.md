# N3-W KF-100 Short-Lived Certificate Auto-Renew Lab Design — 2026-09-30

Status: `SOURCE_PREPARED_PENDING_CI_AND_LIVE_LAB`  
Base main: `2209615229fe74a4bbef18542803ecef125bdc16`  
Branch: `lab/n3w-kf100-short-lived-certificate-auto-renew-20260930`

## 1. Goal

Run the production certificate lifecycle implementation against an isolated short-lived TLS certificate and prove the real renewal path end to end without modifying the production Broker certificate, production CA, production server key, production lifecycle status, or production timer.

The lab covers two paths:

```text
A. successful automatic renewal
B. forced post-renew verification failure followed by automatic rollback
```

## 2. Why the lab runs on T1

The lab uses the real T1 Docker runtime and the same Broker image as production, but creates a separate temporary Broker container with:

- a separate temporary CA;
- a separate temporary server private key;
- a one-day server certificate;
- a separate loopback-only dynamically allocated port;
- a separate temporary status directory;
- no production volumes.

This gives production-like file-replacement, container restart and live TLS behavior without changing production TLS material.

## 3. Short-lived certificate trigger

The lab server certificate is signed for one day.

The production lifecycle policy treats a certificate with <=30 days remaining as `CRITICAL`, which requires renewal.

No production policy constants are changed.

The exact installed production lifecycle executable is used:

```text
/usr/local/sbin/n3w-broker-certificate-lifecycle
git blob=65187b27a2ddd8f57221500a7019486e02bca101
```

The expected successful result is:

```text
action=renew_server_certificate
result=renewed
renewal_attempted=true
rollback_attempted=false
server_state=HEALTHY
```

The renewed certificate must:

- have a different fingerprint;
- have a later validity end;
- keep the same server private key;
- keep the same test CA;
- be the certificate actually served by the isolated TLS endpoint.

## 4. Activation isolation

The production lifecycle program intentionally accepts only:

```text
n3wfc4-broker-activation.service
```

The lab must not restart that production service.

To preserve the exact production lifecycle code while preventing production activation, the executor prepends a private temporary `systemctl` shim to `PATH`.

Only inside the lab process, calls for the expected activation unit are redirected to the isolated test Broker container.

The shim supports only:

```text
systemctl is-active --quiet n3wfc4-broker-activation.service
systemctl restart n3wfc4-broker-activation.service
```

and maps them to the isolated lab container.

It does not call the production systemd unit.

## 5. Successful renewal path

The lab:

1. generates a temporary CA and server key;
2. signs a one-day server certificate;
3. starts an isolated Broker using the current production Broker image;
4. verifies the old certificate over live TLS;
5. runs the exact production lifecycle tool in `auto-renew` mode;
6. allows the lifecycle tool to generate and atomically replace the certificate;
7. redirects the activation restart to the test Broker;
8. verifies that live TLS presents the new certificate;
9. verifies server key and CA continuity.

## 6. Rollback path

A second independent lab case starts from a fresh one-day certificate.

The private activation shim deliberately substitutes a different valid test certificate during the first post-renew restart.

This makes the production lifecycle tool see a live TLS fingerprint that does not match the certificate it just generated.

The expected production behavior is:

```text
renewal_attempted=true
rollback_attempted=true
result=renewal_failed_rolled_back
```

The lab then requires:

- the original short-lived certificate to be restored on disk;
- the isolated Broker to serve that original certificate again;
- the server private key to remain unchanged;
- the test CA to remain unchanged.

This exercises the actual rollback branch rather than only unit-test mocks.

## 7. Production guard

Before creating the lab, the executor freezes:

- production Broker container identity;
- production Broker StartedAt;
- production server certificate SHA-256;
- production server key SHA-256;
- production FC4 CA SHA-256;
- production lifecycle status SHA-256;
- production timer enabled/active state;
- live production TLS fingerprint.

After both lab cases and before PASS, all of those values must still match.

The production lifecycle service must not be active/activating.

## 8. Cleanup

The lab containers and temporary CA/key/certificate/status files are deleted before the executor exits.

No test CA or test private key becomes a production authority.

## 9. Source authority

```text
tools/n3w_kf100_short_lived_certificate_auto_renew_lab.py
source/test head=49497128e451a5d1648cabba4427227a8bb087fb
git blob=16c1d1f3afedf18580a1096e92357f62380f2a53
```

Focused tests are in:

```text
tests/tools/test_n3w_kf100_short_lived_certificate_auto_renew_lab.py
```

## 10. Current boundary

```text
KF100_ROUTE_STATUS=CLOSED_PASS
KF100_REOPEN=false

SHORT_LIVED_RENEWAL_LAB_SOURCE=PREPARED
LIVE_LAB=false

PRODUCTION_CERTIFICATE_MUTATION=false
PRODUCTION_BROKER_RESTART=false
PRODUCTION_TIMER_MUTATION=false

NEXT_ONE_GATE=N3W_KF100_SHORT_LIVED_CERTIFICATE_AUTO_RENEW_LAB_EXECUTION_20260930_01
```
