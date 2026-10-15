# N3-W T1 F4 Real-T1 Read-only Preauthorization Closure — 2026-10-15

~~~text
TASK=N3W_T1_F4_REAL_T1_READONLY_PREAUTH_20261015_01
RESULT=CLOSED_PASS_READY_FOR_EXPLICIT_F4_LIVE_AUTHORIZATION_DECISION

SOURCE_HEAD=ad65bf7d10db76f12a09e19b337f4a0c7782894a
EXACT_CONTROL_PACKAGE_ARTIFACT_ID=11967018401
EXACT_CONTROL_PACKAGE_ZIP_SHA256=6308fdc64347949d463f251713c359571b40f067182cfd4d686ba4495d6d162f
CONTROL_TAR_SHA256=13ecd035890dc88731bac6909ed1cb13ca33afd86b04d5d147d24003afbcf9f7
PACKAGE_MANIFEST_SHA256=9ed2ce124fbe0e621b4443a655c1cb78285db79b30489e2d41bcf73f4ee5e230

T1_ACCESS=true:READ_ONLY
LIVE_RUNTIME_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
LIVE_F4_AUTHORIZATION=NOT_GRANTED
MERGE=false
~~~

## 1. Closure result

The real T1 was inspected read-only at the F3/F4 boundary.

The first aggregate result was `STOP` only because the preauthorization oracle incorrectly required the
ingress-guard systemd unit to already be active. Repository source proves the staged F3 installer enables the guard
without starting it, while the F4 activation owner explicitly starts and verifies the guard immediately before
Broker startup.

Therefore:

~~~text
INITIAL_AGGREGATE_STOP=FALSE_NEGATIVE_ORACLE
PRODUCT_DEFECT=false
SOURCE_DEFECT=false
PREAUTH_CONTRACT_DEFECT=true:DOCS_ORACLE_ONLY
CORRECTED_RESULT=PASS
REPEAT_SAME_READONLY_PROBE_REQUIRED=false
~~~

## 2. Real T1 evidence

Provisioning / release:

~~~text
PROVISION_VERIFY_RC=0
PROVISION_STATUS=PASS
PROVISION_STATE=DEVICE_READY
PROVISION_RELEASE_ID=6ac82ae0872b05644e59470ffef7307dad14d359
RELEASE_SCHEMA=gh.n3w-t1-fresh-release/1
RELEASE_ID=6ac82ae0872b05644e59470ffef7307dad14d359
RELEASE_SOURCE_HEAD=6ac82ae0872b05644e59470ffef7307dad14d359
PROVISION_PRODUCTION_SERVICE_START=false
PROVISION_TRANSACTION_PRESENT=true
FIRSTBOOT_COMPLETE_PRESENT=true
~~~

Public-safe identity binding:

~~~text
HOST_INSTANCE_ID_SHA256=7e13110518a0b7f0d0f230574d9e06c9ccefce76bb58b1cc1facddf13d937a75
SYSTEM_ID_SHA256=874d76cf8e68ea7236a30612c15a47ebb0b6841de75c426866a6cf7aa2546a1e
~~~

F4 lifecycle prestate:

~~~text
FACTORY_ACCEPTED_PRESENT=false
F4_TRANSACTION_PRESENT=false
F4_RUNTIME_ACCEPTANCE_PRESENT=false

F4_CANONICAL_CONTROL_TARGETS_ABSENT=true
F4_CANONICAL_TARGET_EXISTING_COUNT=0
CERTIFICATE_STATUS_ROOT_ABSENT_OR_EMPTY=true
~~~

Product runtime prestate:

~~~text
PRODUCT_CONTAINER_COUNT=0
PRODUCT_LISTENER_COUNT=0
PRODUCT_LISTENER_PORTS=[]
PRODUCTION_SERVICE_START=false

BROKER_ACTIVATION_ACTIVE=inactive
BROKER_ACTIVATION_ENABLED=not-found
SERVICES_ACTIVATION_ACTIVE=inactive
SERVICES_ACTIVATION_ENABLED=not-found
CERTIFICATE_TIMER_ACTIVE=inactive
CERTIFICATE_TIMER_ENABLED=not-found
~~~

Staged predecessor units:

~~~text
INGRESS_GUARD_ENABLED=enabled
INGRESS_GUARD_ACTIVE=inactive
INGRESS_GUARD_ACTIVE_CLASSIFICATION=VALID_PRE_F4_STOPPED_BOUNDARY
PROVISION_RESUME_ENABLED=enabled
~~~

Product material:

~~~text
PRODUCT_IMAGE_COUNT=3
EXACT_THREE_PRODUCT_IMAGES_PRESENT=true
PUBLIC_PRODUCT_SOURCE_PRESENT=true
PER_DEVICE_IDENTITY_PRESENT=true
PER_DEVICE_SERVICE_CREDENTIALS_PRESENT=true
PER_DEVICE_TLS_PRESENT=true
ROOT_FREE_BYTES=6305845248
~~~

## 3. Ingress-guard oracle correction

Repository authority:

~~~text
infra/n3w-t1/install-systemd-staged.sh
  systemctl enable n3wfc4-broker-ingress-guard.service
  no systemctl start

infra/n3w-t1/systemd/n3wfc4-broker-ingress-guard.service
  Type=oneshot
  RemainAfterExit=yes
  WantedBy=docker.service

tools/n3w_t1_f4_activation_host.py
  F4 activate explicitly starts guard
  then requires guard active
  then proceeds to Broker start
~~~

Consequently the correct read-only pre-F4 contract is:

~~~text
INGRESS_GUARD_ENABLED=true
INGRESS_GUARD_ACTIVE=OBSERVE_ONLY
VALID_ACTIVE_STATES_FOR_PREAUTH=active|inactive
F4_ACTIVATE_MUST_START_AND_VERIFY_ACTIVE=true
~~~

No remote repair was required or performed.

## 4. Capacity result

Exact F4 control tar:

~~~text
CONTROL_TAR_BYTES=174080
ROOT_FREE_BYTES=6305845248
~~~

The target has far more free space than the exact F4 control transfer plus extracted package/canonical copy and
bounded lifecycle metadata require. No arbitrary multi-gigabyte reserve is introduced for this small F4 control
package.

~~~text
F4_CONTROL_PACKAGE_CAPACITY=PASS
~~~

## 5. Preauthorization closure

After correcting only the invalid ingress-guard active-state oracle, every required preauthorization condition is
PASS:

~~~text
DEVICE_READY=PASS
DEPLOYED_RELEASE_BINDING=PASS
CURRENT_HOST_BINDING=PASS
CURRENT_SYSTEM_BINDING=PASS

F4_CLAIM_ABSENT=PASS
F4_RUNTIME_ACCEPTANCE_ABSENT=PASS
ZERO_PRODUCT_CONTAINERS=PASS
ZERO_PRODUCT_LISTENERS=PASS

INGRESS_GUARD_ENABLEMENT=PASS
PROVISION_RESUME_ENABLEMENT=PASS
ACTIVATION_UNITS_STOPPED=PASS
ACTIVATION_PERSISTENCE_NOT_ENABLED=PASS

CANONICAL_F4_TARGETS_ABSENT=PASS
CERTIFICATE_STATUS_PRESTATE=PASS

EXACT_PRODUCT_IMAGES_PRESENT=PASS
PUBLIC_PRODUCT_SOURCE_PRESENT=PASS
PER_DEVICE_IDENTITY_PRESENT=PASS
PER_DEVICE_SERVICE_CREDENTIALS_PRESENT=PASS
PER_DEVICE_TLS_PRESENT=PASS
F4_CONTROL_PACKAGE_CAPACITY=PASS

BOARD_ACCESS=false
LIVE_RUNTIME_MUTATION=false
PRODUCTION_SERVICE_START=false
~~~

## 6. Authorization boundary

This read-only PASS does not grant live F4 mutation.

A new explicit authorization is required for the successor live gate.

Proposed exact successor authorization:

~~~text
N3W_T1_F4_EXACT_CONTROL_PACKAGE_TRANSFER_AND_PREPARE_LIVE_20261015_01
~~~

That gate is bounded to:

~~~text
verified package transfer to transaction-owned staging
remote tar SHA256 verification
safe extraction + exact package validation
one durable F4 transaction claim
FACTORY_ACCEPTED creation
canonical F4 control material installation
PREPARED
STOP
~~~

It does not authorize:

~~~text
Broker start
Manager start
Home Assistant start
RUNTIME_STARTED
RUNTIME_ACCEPTED
persistence enablement
certificate audit
certificate timer enablement
reboot
board access
~~~

## 7. Current STOP

~~~text
REAL_T1_READONLY_PREAUTH=CLOSED_PASS
LIVE_F4_AUTHORIZATION=NOT_GRANTED
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false

CURRENT_STOP_POINT=AFTER_REAL_T1_READONLY_PREAUTH_BEFORE_EXPLICIT_F4_LIVE_PREPARE_AUTHORIZATION

NEXT_ONE_GATE=N3W_T1_F4_EXACT_CONTROL_PACKAGE_TRANSFER_AND_PREPARE_LIVE_20261015_01
AUTO_EXECUTE_NEXT_GATE=false
~~~
