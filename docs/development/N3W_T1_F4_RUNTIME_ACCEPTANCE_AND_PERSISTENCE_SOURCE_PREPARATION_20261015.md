# N3-W T1 F4 Runtime Acceptance and Persistence Source Preparation — 2026-10-15

~~~text
TASK=N3W_T1_F4_RUNTIME_ACCEPTANCE_AND_PERSISTENCE_SOURCE_PREPARATION_20261015_01
RESULT=CLOSED_PASS_SOURCE_PREPARATION

PREPARATION_BASE=9cfd7459abe90054fe4657f5925da252f003f95a
TRANSITION_EXECUTABLE_REVIEW_HEAD=be14b74e6c74cc8ac036e41cc99b49439a2fc20c
TRANSITION_EXACT_HEAD_CI=13_SUCCESS_0_FAILURE_0_PENDING

LIVE_PRODUCT_RELEASE_ID=6ac82ae0872b05644e59470ffef7307dad14d359
LIVE_PRODUCT_STATE=DEVICE_READY

T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
MERGE=false
~~~

## 1. Purpose

The previous gate closed the F3 → F4 transition controller only through:

~~~text
DEVICE_READY
→ FACTORY_ACCEPTED
→ exact F4 control package installed
→ Broker start/readiness
→ Manager + Home Assistant start
→ RUNTIME_STARTED
→ STOP
~~~

This preparation freezes the remaining pre-reboot F4 authority:

~~~text
RUNTIME_STARTED
→ runtime acceptance
→ RUNTIME_ACCEPTED
→ Broker/Services reboot persistence enable
→ first certificate lifecycle audit
→ certificate timer enable
→ PRE_REBOOT_READY
→ STOP
~~~

Reboot remains a later separately authorized live gate.

## 2. One F4 authorization, one bounded continuation

The future live F4 authorization is one exact authorization ID.

It is claimed and consumed once by F4 prepare. Later F4 commands are continuation steps and must require the same
authorization ID from the durable transaction. They do not create a second authorization and they cannot invoke
provisioning start.

~~~text
F4_PREPARE              claims one-shot authorization
F4_ACTIVATE             same authorization ID
F4_ACCEPT_RUNTIME       same authorization ID
F4_ENABLE_PERSISTENCE   same authorization ID
F4_CERTIFICATE_AUDIT    same authorization ID
F4_ENABLE_CERT_TIMER    same authorization ID
REBOOT                  separate later authorization
~~~

A failed mutation path must never be made retryable by deleting the F4 transaction or FACTORY_ACCEPTED record.

## 3. Durable state model

The existing main transaction stages remain sufficient for the pre-reboot route:

~~~text
RUNTIME_STARTED
RUNTIME_ACCEPTED
PERSISTENCE_ENABLED
~~~

Do not add a later stage solely for certificate audit/timer enablement, because Broker and Services restart
eligibility is already bound through PERSISTENCE_ENABLED.

After PERSISTENCE_ENABLED, record additional exact flags instead:

~~~text
runtime_acceptance_passed=true
runtime_acceptance_report_sha256=<public-safe report hash>

broker_services_persistence_enabled=true

certificate_first_audit_passed=true
certificate_status_sha256=<durable status file hash>
certificate_server_state=HEALTHY
certificate_ca_state=HEALTHY
certificate_system_ca_state=HEALTHY

certificate_timer_enabled=true
certificate_timer_active_before_reboot=false

pre_reboot_ready=true
~~~

The transaction remains the single F4 continuation authority.

## 4. Runtime acceptance owner

The current repository-owned F4 host remains the top-level owner:

~~~text
tools/n3w_t1_f4_activation_host.py
~~~

The next source repair should extend it with bounded commands:

~~~text
accept-runtime
enable-persistence
certificate-audit
enable-certificate-timer
~~~

No second independent activation state machine should be introduced.

## 5. Runtime acceptance contract

Runtime acceptance must be based on direct runtime state and functional probes. Missing log text alone is never a
failure oracle.

### 5.1 Global runtime binding

Before component-specific acceptance:

~~~text
transaction_stage=RUNTIME_STARTED
FACTORY_ACCEPTED=exact
authorization_id=exact
installed_F4_control_material=exact
release_id=exact live F3 release
running_service_set=broker,manager,homeassistant exactly
unexpected_product_container_count=0
rendered_compose_gate=PASS
board_access=false
~~~

Each running container must be rebound to the exact image authority already stored in the deployed fresh release.
The cross-Docker-store image binding logic already used by the fresh installer should be reused rather than
reintroducing raw Docker Image-ID equality.

### 5.2 Broker acceptance

Required PASS evidence:

~~~text
BROKER_EXACT_IMAGE_BINDING=true
BROKER_PROJECT_NETWORK_SET_EXACT=true

TCP_1883_BIND=127.0.0.1_ONLY
TCP_8883_BIND=IPV4_WILDCARD_ONLY
BROKER_PUBLICATION_OWNER_EXACT=true

INGRESS_GUARD_ACTIVE=true
INGRESS_GUARD_ENABLED=true
INGRESS_GUARD_EFFECTIVE=true

TLS_CA_VERIFY=true
TLS_SERVER_NAME_VERIFY=armbian
LIVE_TLS_ENDPOINT=127.0.0.1:8883
LIVE_CERT_MATCHES_BOUND_SERVER_CERT=true

DYNSEC_DEFAULT_DENY_EXACT=true
SERVICE_CLIENT_COUNT=3
SERVICE_ROLE_COUNT=3
NODE_CLIENT_COUNT=0
NODE_ROLE_COUNT=0

MANAGER_EXACT_CREDENTIAL_AUTH=true
PROVISIONING_EXACT_CREDENTIAL_AUTH=true
HOMEASSISTANT_EXACT_CREDENTIAL_AUTH=true

MANAGER_WRONG_CLIENT_ID_REJECTED=true
PROVISIONING_WRONG_CLIENT_ID_REJECTED=true
HOMEASSISTANT_WRONG_CLIENT_ID_REJECTED=true
ANONYMOUS_REJECTED=true
~~~

The existing S20 service-handoff probe logic is a reusable semantic reference for positive authentication,
wrong-client-ID rejection and anonymous rejection. The historical S20 transaction executor itself is not the F4
owner and must not be replayed.

Probe secrets must be consumed from the existing per-device secret files and never placed in command-line output,
public JSON, GitHub evidence or logs.

### 5.3 Manager acceptance

The Manager acceptance must prove both exact runtime configuration and a real functional process boundary:

~~~text
MANAGER_EXACT_IMAGE_BINDING=true
MANAGER_RUNTIME_UID_GID=999:999
MANAGER_ROOTFS_READ_ONLY=true
MANAGER_EXPECTED_WRITABLE_MOUNTS_EXACT=true

MANAGER_PASSWORD_FILE_READ_ONLY=true
PROVISIONING_PASSWORD_FILE_READ_ONLY=true
MANAGER_AND_PROVISIONING_IDENTITY_DISTINCT=true

MANAGER_HEALTH_HTTP=PASS
MANAGER_HEALTH_SCHEMA=gh.pair.simple-health/1
MANAGER_HEALTH_STATUS=ok

MANAGER_HOST_NETWORK_BROKER_TLS_NAMESPACE_PROBE=PASS
MANAGER_BROKER_SERVER_NAME=armbian

MANAGER_BUSINESS_STATE_EMPTY=true
PAIRING_REGISTRATION_COUNT=0
NODE_CREDENTIAL_COUNT=0
REPLAY_STATE_EMPTY=true
RELAY_AUTHORIZATION_STATE_EMPTY=true
RELAY_KEY_STATE_EMPTY=true
GH_N3W_PRODUCT_PAIRING_ENABLED=false
~~~

The current simplified Manager health endpoint is the functional health oracle. Broker logs may be supporting
evidence only; absence of a log line is not a failure oracle.

The Manager empty-state verification should reuse the fresh-state audit semantics already used by F3 instead of
inventing a new database interpretation.

### 5.4 Home Assistant acceptance

Required PASS evidence:

~~~text
HOMEASSISTANT_EXACT_IMAGE_BINDING=true
HOMEASSISTANT_RUNTIME_READY=true

HA_MQTT_ENTRY_COUNT=1
HA_ENABLED_MQTT_ENTRY_COUNT=1
HA_MQTT_ENTRY_MATCHES_BOOTSTRAP_METADATA=true
HA_MQTT_PASSWORD_MATCHES_PRIVATE_FILE_IN_MEMORY=true
HA_MQTT_ENTRY_ID_FINGERPRINT_PRESENT=true

HA_MQTT_BOOTSTRAP_OFFICIAL_CONFIG_FLOW_ONLY=true
HA_DIRECT_STORAGE_EDIT=false
HA_DUPLICATE_MQTT_ENTRY=false

HA_NODE_ENTITY_CREATION_BEFORE_BOARD_PAIRING=0
~~~

The acceptance helper may read Home Assistant core.config_entries only inside the private runtime boundary. Raw
storage JSON, raw entry ID, MQTT password and other secret-bearing values must never be emitted. The public report
contains counts, booleans and a one-way fingerprint only.

The current isolated HA acceptance at source 0412d6009c963bf80eb7ce2e21e3fefac69e09a2 proved the bootstrap semantics
(created → recreate → existing_match with one stable entry). F4 must now prove the corresponding real production
T1 state; the isolated result is supporting source evidence, not a substitute.

## 6. RUNTIME_ACCEPTED durable transition

Only after every runtime check passes may the host write:

~~~text
stage=RUNTIME_ACCEPTED
runtime_acceptance_passed=true
runtime_acceptance_report_sha256=<sha256>
production_service_start=true
persistence_enabled=false
certificate_timer_enabled=false
~~~

The runtime acceptance report must be a root-owned mode-0600 public-safe JSON object under the F4 transaction root.
It must contain no raw secrets, raw SYSTEM_ID, raw host identity, raw Home Assistant entry ID or private T1 locator.

An acceptance failure must not advance to RUNTIME_ACCEPTED.

The acceptance implementation gets a bounded readiness window rather than a single immediate sample. When the
window expires or a security check fails, the F4 owner must stop Services and Broker and record either:

~~~text
STOPPED_RUNTIME_ACCEPTANCE
~~~

or:

~~~text
STOPPED_RUNTIME_ACCEPTANCE_ROLLBACK_UNPROVEN
~~~

No blind continuation is permitted.

## 7. Persistence enablement contract

The historical helper:

~~~text
infra/n3w-t1/activate-systemd-production.sh
~~~

must not be used unchanged for the fresh route because it enables Broker, Services **and the certificate timer in
one operation**.

Fresh F4 needs separate persistence ownership.

From RUNTIME_ACCEPTED:

~~~text
systemctl enable n3wfc4-broker-activation.service
systemctl enable n3wfc4-services-activation.service
~~~

Requirements:

~~~text
NO_--NOW=true
NO_START=true
NO_RESTART=true
BROKER_ENABLED=enabled
SERVICES_ENABLED=enabled
CERTIFICATE_TIMER_ENABLED!=enabled
CURRENT_RUNNING_CONTAINERS_UNCHANGED=true
CURRENT_RUNTIME_ACCEPTANCE_BINDING_UNCHANGED=true
~~~

Only after verification may transaction stage become:

~~~text
PERSISTENCE_ENABLED
~~~

If partial enablement occurs, rollback must disable both runtime units and prove both disabled. An unproven rollback
is a hard STOP and must not continue to certificate lifecycle.

## 8. First certificate lifecycle audit

The old fixed-fingerprint KF-100 first-audit wrapper must not be reused unchanged.

The reusable lower-level authority is:

~~~text
tools/n3w_broker_certificate_lifecycle.py
~~~

The F4 owner must invoke its audit mode with the fresh per-device environment already installed by the transition
package.

Important semantic correction: lifecycle audit does not replace certificates and does not restart Broker, but it
**does write** the lifecycle status file and lock. Therefore it is a bounded status mutation, not a purely
read-only host operation.

Before and after the audit, hash:

~~~text
Broker CA certificate
Broker CA private key
Broker server certificate
Broker server private key
System CA certificate
Broker container identity / StartedAt
~~~

Acceptance requires:

~~~text
action=audit
result=ok
server_state=HEALTHY
ca_state=HEALTHY
system_ca_state=HEALTHY
renewal_attempted=false
rollback_attempted=false

SERVER_CERT_UNCHANGED=true
SERVER_KEY_UNCHANGED=true
CA_CERT_UNCHANGED=true
CA_KEY_UNCHANGED=true
SYSTEM_CA_UNCHANGED=true
BROKER_CONTAINER_CONTINUITY=true
LIVE_TLS_VERIFIED=true
~~~

A WARNING/CRITICAL/EXPIRED state is not acceptable for first production activation even though the generic
lifecycle tool can represent monitoring warnings.

The lifecycle status directory must contain only the expected root-owned private lock/status authority.

## 9. Certificate timer enablement

Only after the first lifecycle audit PASS and while transaction stage remains PERSISTENCE_ENABLED:

~~~text
systemctl enable n3wfc4-broker-certificate-lifecycle.timer
~~~

Requirements:

~~~text
CERTIFICATE_TIMER_ENABLED=enabled
CERTIFICATE_TIMER_ACTIVE_BEFORE_REBOOT=false
CERTIFICATE_SERVICE_ACTIVE=false
NO_--NOW=true
NO_START=true
NO_CERTIFICATE_RENEWAL=true
~~~

Then persist:

~~~text
certificate_first_audit_passed=true
certificate_timer_enabled=true
pre_reboot_ready=true
~~~

The transaction stage remains PERSISTENCE_ENABLED so Broker and Services continue to satisfy their existing restart
eligibility guards.

## 10. Failure boundary after RUNTIME_ACCEPTED

Any downstream failure after RUNTIME_ACCEPTED must fail closed as one F4 transaction.

Required recovery order:

~~~text
disable certificate timer if enabled
disable Broker/Services persistence if enabled in this transaction
stop Services
stop Broker
prove no product listener/container remains
preserve FACTORY_ACCEPTED and consumed F4 transaction
record exact failure class and rollback_proven true/false
STOP
~~~

Do not delete acceptance/provisioning records to make a failed authorization reusable.

## 11. Reboot remains separate

This source gate ends at PRE_REBOOT_READY.

A later explicit reboot gate must prove:

~~~text
same host identity
same SYSTEM_ID binding
same F4 package/install binding
same FACTORY_ACCEPTED
same service credentials

guard before Broker publication
Broker automatic recovery
Manager automatic recovery
Home Assistant automatic recovery

HA MQTT entry count remains one
HA entry fingerprint unchanged
Manager business state remains fresh
certificate timer enabled and healthy
no board access
~~~

No reboot command belongs to the runtime-acceptance/persistence source repair.

## 12. Exact source-repair surface

The next implementation gate should remain narrow:

~~~text
MOD tools/n3w_t1_f4_activation_host.py
MOD tests/tools/test_n3w_t1_f4_activation_host.py

ADD only if needed:
  .github/workflows/n3w-t1-f4-control-package-ci.yml
  exact F4 package-builder helper/manifest tests

REUSE:
  tools/n3w_t1_broker_authenticated_readiness.py
  tools/n3w_broker_certificate_lifecycle.py
  fresh runtime-image binding logic
  fresh state/DynSec/service-credential audit logic
  current ingress-guard/deployment gates
~~~

Do not modify ESP32 firmware, pairing state machines, board NVS, RF code, the consumed provisioning transaction or
historical S20/KF-100 live executors.

## 13. Required tests

Minimum new source coverage:

~~~text
RUNTIME_ACCEPT_FROM_ONLY_RUNTIME_STARTED=true
RUNTIME_ACCEPT_EXACT_PACKAGE_AND_INSTALL_BINDING_REQUIRED=true
EXACT_THREE_RUNNING_SERVICES_REQUIRED=true
RUNTIME_IMAGE_BINDING_REQUIRED=true

BROKER_1883_LOOPBACK_ONLY=true
BROKER_8883_WILDCARD_ONLY=true
BROKER_TLS_VERIFIED=true
THREE_POSITIVE_SERVICE_AUTH=true
THREE_WRONG_CLIENT_ID_REJECTED=true
ANONYMOUS_REJECTED=true
ZERO_NODE_DYNSEC=true

MANAGER_RUNTIME_CONTRACT=true
MANAGER_HEALTH=true
MANAGER_NAMESPACE_TLS_PROBE=true
MANAGER_EMPTY_STATE=true
PAIRING_DISABLED=true

HA_ONE_MQTT_ENTRY=true
HA_ENTRY_PRIVATE_MATCH=true
HA_DUPLICATE_REJECTED=true
HA_SECRET_NOT_EMITTED=true

RUNTIME_ACCEPTANCE_FAILURE_DOES_NOT_ADVANCE=true
RUNTIME_ACCEPTANCE_FAILURE_ROLLBACK_PROVEN_OR_UNPROVEN=true

PERSISTENCE_ENABLE_ONLY_AFTER_RUNTIME_ACCEPTED=true
PERSISTENCE_DOES_NOT_ENABLE_TIMER=true
PERSISTENCE_PARTIAL_ENABLE_ROLLBACK=true

CERT_AUDIT_ONLY_AFTER_RUNTIME_ACCEPTED_OR_PERSISTENCE=true
CERT_FIRST_AUDIT_REQUIRES_HEALTHY=true
CERT_AUDIT_PROVES_NO_CERT_KEY_MUTATION=true
CERT_TIMER_ENABLE_ONLY_AFTER_AUDIT=true
CERT_TIMER_ENABLE_NO_NOW=true

REBOOT_NOT_EXECUTED=true
BOARD_ACCESS=false
PROVISIONING_START_REPLAY=false
~~~

## 14. Gate closure

~~~text
F4_RUNTIME_ACCEPTANCE_AND_PERSISTENCE_PREPARATION=CLOSED_PASS

RUNTIME_ACCEPTANCE_OWNER=FROZEN
RUNTIME_ACCEPTED_TRANSITION=FROZEN
BROKER_SERVICES_PERSISTENCE_ORDER=FROZEN
FRESH_CERT_FIRST_AUDIT_ORDER=FROZEN
CERT_TIMER_ENABLE_ORDER=FROZEN
FAILURE_ROLLBACK_BOUNDARY=FROZEN
REBOOT_BOUNDARY=SEPARATE

LIVE_F4_AUTHORIZATION=NOT_GRANTED
T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false

CURRENT_STOP_POINT=AFTER_RUNTIME_ACCEPTANCE_PERSISTENCE_PREPARATION_BEFORE_SOURCE_REPAIR
NEXT_ONE_GATE=N3W_T1_F4_RUNTIME_ACCEPTANCE_AND_PERSISTENCE_SOURCE_REPAIR_20261015_01
AUTO_EXECUTE_LIVE_F4=false
~~~
