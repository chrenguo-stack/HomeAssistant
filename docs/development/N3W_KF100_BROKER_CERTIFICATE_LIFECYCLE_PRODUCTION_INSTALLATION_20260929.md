# N3-W KF-100 Broker Certificate Lifecycle Production Installation — 2026-09-29

Status: `SOURCE_PREPARED_PENDING_CI_AND_LIVE_INSTALL`  
Base main: `bc13f7c21a4441ef06261f69b08cb7937e2ab613`  
Installation branch: `exec/n3w-kf100-broker-certificate-lifecycle-production-installation-20260929`  
Predecessor: KF-100 production deployment read-only preflight PASS

## 1. Gate goal

Install the already-merged certificate lifecycle source onto the production T1 without starting or enabling any certificate lifecycle action.

This gate is installation-only.

Allowed mutation:

```text
install lifecycle executable
install lifecycle systemd service unit
install lifecycle systemd timer unit
materialize private lifecycle environment file
create private lifecycle status directory
systemctl daemon-reload
```

Forbidden mutation:

```text
systemctl enable lifecycle timer
systemctl start lifecycle timer
systemctl start lifecycle service
systemctl restart Broker
certificate renewal
certificate replacement
server private-key replacement
FC4 CA replacement
Manager restart
Home Assistant restart
node re-pairing
```

## 2. Exact source authority

The install executor accepts only these exact Git blob identities from merged main:

```text
tools/n3w_broker_certificate_lifecycle.py
blob=65187b27a2ddd8f57221500a7019486e02bca101

infra/n3w-t1/systemd/n3wfc4-broker-certificate-lifecycle.service
blob=fa13967ef0ffb0a271fcb7122febd83b83079deb

infra/n3w-t1/systemd/n3wfc4-broker-certificate-lifecycle.timer
blob=65b0365c5ea5f5d3c896a133adc0d689bb2deced

tools/n3w_broker_certificate_lifecycle_deployment_preflight.py
blob=8f3a09fee5cdad1d60dd76406e3dd03c7aa510ed
```

Any staged-source drift stops before installation.

## 3. Fresh pre-mutation rebind

The installation executor imports and re-runs the exact reviewed deployment preflight immediately before the first write.

Therefore the installation itself requires a fresh PASS for:

- active Broker identity;
- active CA/server certificate fingerprints;
- current server cert/key match;
- live TLS/8883 verification for `armbian`;
- current Mosquitto/server-key ownership binding;
- unique root-owned FC4 CA signing key;
- System CA identity;
- ingress guard active + enabled;
- Broker activation active + enabled;
- lifecycle timer still not active/enabled;
- lifecycle deployment targets still absent.

If the preflight fails, installation does not start.

## 4. Installation targets

```text
/usr/local/sbin/n3w-broker-certificate-lifecycle
root:root 0755

/etc/systemd/system/n3wfc4-broker-certificate-lifecycle.service
root:root 0644

/etc/systemd/system/n3wfc4-broker-certificate-lifecycle.timer
root:root 0644

/etc/n3wfc4/broker-certificate-lifecycle.env
root:root 0600

/var/lib/n3wfc4-certificate-lifecycle/
root:root 0700
```

The status JSON is not created in this gate. It is first created by the later explicit audit gate.

## 5. Private environment authority

The environment file is generated on T1 from current runtime-resolved authority.

It contains the private absolute paths required by the lifecycle service, but those paths are not emitted into public output or committed to GitHub.

It binds:

```text
current Broker server certificate
current Broker server private key
current FC4 CA certificate
current unique FC4 CA signing private key
current H0/H1 System CA
server name=armbian
private status path
FC4 allowed root
System CA allowed root
```

The unique FC4 CA key must remain inside the active persistent FC4 authority root. If it moves to a different authority root, installation stops instead of broadening the lifecycle service's allowed path boundary.

## 6. No implicit persistence activation

The existing combined persistence installer is not called.

The installation executor contains no:

```text
systemctl enable
systemctl start
systemctl restart
systemctl stop
docker restart
docker exec
docker compose
auto-renew invocation
```

Only `systemctl daemon-reload` is permitted.

After daemon-reload:

- lifecycle timer must remain not enabled;
- lifecycle timer must remain inactive;
- lifecycle service must remain inactive.

## 7. Runtime continuity checks

Before installation the executor captures the active Broker container identity and start timestamp, plus hashes of the active server certificate, server private key and FC4 CA certificate.

After installation it requires:

```text
Broker container identity unchanged
Broker StartedAt unchanged
server certificate hash unchanged
server private-key hash unchanged
FC4 CA certificate hash unchanged
live TLS/8883 still verifies
served server fingerprint unchanged
```

Any failure after the first installation write triggers rollback of the newly created lifecycle targets and another `daemon-reload`.

Because the read-only preflight proved every lifecycle deployment target absent before installation, rollback never overwrites or restores unknown prior lifecycle files.

## 8. Rollback contract

If installation fails after mutation begins:

```text
remove newly installed env/unit/tool files
remove newly created status directory if empty
systemctl daemon-reload
```

The result is:

```text
installation_rollback=PASS
```

only if cleanup and daemon-reload both succeed.

Otherwise:

```text
installation_rollback=UNPROVEN
```

and the gate stops for manual read-only forensic inspection.

## 9. Success boundary

A PASS proves only that lifecycle source is installed but dormant.

Expected post-install state:

```text
lifecycle tool installed=true
lifecycle service installed=true
lifecycle timer installed=true
private environment installed=true
status directory created=true

timer enabled != enabled
timer active != active
lifecycle service active != active

certificate mutation=false
Broker restart=false
auto-renew start=false
```

The next gate is an explicit first `audit` invocation. That later audit is allowed to create only the lifecycle lock/status files and must still not enter certificate renewal.

## 10. Current disposition

```text
PR507_MERGED=true
PR507_MERGE_COMMIT=bc13f7c21a4441ef06261f69b08cb7937e2ab613
PRODUCTION_READONLY_PREFLIGHT=PASS

INSTALLATION_EXECUTOR_SOURCE=PREPARED
INSTALLATION_EXECUTOR_TESTS=PREPARED
LIVE_INSTALLATION=false
CERTIFICATE_MUTATION=false
TIMER_ENABLEMENT=false

NEXT_ONE_GATE=N3W_KF100_BROKER_CERTIFICATE_LIFECYCLE_PRODUCTION_INSTALLATION_EXECUTION_20260929_01
```
