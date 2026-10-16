# N3-W T1 F4 Stopped Runtime Acceptance Recovery — Postexecution Read-Only Closure

Date: 2026-10-16

~~~text
TASK=N3W_T1_F4_STOPPED_RUNTIME_ACCEPTANCE_RECOVERY_POSTEXECUTION_READONLY_CLOSURE_20261016_01
READONLY_RESULT=PASS
DOWNSTREAM_SOURCE_BLOCKER=OPEN

REAL_T1_STAGE=PREPARED
TRANSACTION_SHA256=bd1e69c2bce2291e835e8bd341434ad889fbdae8630d9bf897a7fdb27dade1ad

SOURCE_HEAD=f0bcc2ac50326b9a988405af8a2aad4c51694810
PACKAGE_MANIFEST_SHA256=37c620daf57a3f49614a4c2824c55b7e20413ef63593cd1781e4f359fb4729b5
INSTALLED_LAUNCHER_SHA256=eaf28175909479007d6d1df7522811d032890dcaa2a2280228c93e6dce128bb3
INSTALLED_LAUNCHER_SIZE=177919

RECOVERY_AUTHORIZATION_ID=N3W_T1_F4_STOPPED_RUNTIME_ACCEPTANCE_RECOVERY_LIVE_20261016_01
RECOVERY_AUTHORIZATION_CLAIMED=true
RECOVERY_AUTHORIZATION_CONSUMED=true
RECOVERY_AUTHORIZATION_REPLAY_ALLOWED=false

ACTIVATION_RETRY_ELIGIBLE=true
RUNTIME_ACCEPTANCE_RETRY_ELIGIBLE=true

PRODUCTION_SERVICE_START=false
RUNNING_SERVICES=[]
PRODUCT_LISTENER_PORTS=[]
~~~

## 1. Durable recovery poststate

Fresh read-only evidence independently confirmed the recovery result is durable:

~~~text
stage=PREPARED
transaction_sha256_match=true
installed_material_binding_pass=true
runtime_acceptance_recovery_passed=true

broker_ready=false
runtime_started=false
runtime_acceptance_required=true
runtime_acceptance_passed=false

production_service_start=false
persistence_enabled=false
certificate_timer_enabled_recorded=false

docker_probe=PASS
running_services=[]
listener_probe=PASS
product_listener_ports=[]

broker_active=inactive
broker_enabled=disabled
services_active=failed
services_enabled=disabled
certificate_service_active=inactive
certificate_timer_active=inactive
certificate_timer_enabled_runtime=disabled
guard_active=active
runtime_acceptance_report_present=false
~~~

## 2. Authorization ledger evidence

The fresh transaction contains:

~~~text
activation_authorization_id=N3W_T1_F4_ACTIVATE_TO_RUNTIME_STARTED_LIVE_R2_20261015_01
activation_authorization_claimed=true
activation_authorization_consumed=true
activation_authorization_replay_allowed=false

activation_authorization_history=[
  N3W_T1_F4_ACTIVATE_TO_RUNTIME_STARTED_LIVE_20261015_01
]

runtime_acceptance_authorization_id=N3W_T1_F4_RUNTIME_ACCEPTANCE_LIVE_20261015_01
runtime_acceptance_authorization_claimed=true
runtime_acceptance_authorization_consumed=true
runtime_acceptance_authorization_replay_allowed=false

runtime_acceptance_authorization_history=null
~~~

The null runtime-acceptance history is direct live evidence.

## 3. Newly exposed source blocker

At source `f0bcc2ac50326b9a988405af8a2aad4c51694810`, `_all_prior_authorization_ids()`
requires both authorization-history fields to be lists.

The current durable transaction value
`runtime_acceptance_authorization_history=null` therefore causes
`runtime_acceptance_authorization_history_invalid` before a successor activation authorization can be evaluated,
because `_activate()` calls `_activation_prior_authorization_ids()`, which delegates to
`_all_prior_authorization_ids()`.

The same null value would also block the later successor `accept-runtime` path.

~~~text
SUCCESSOR_ACTIVATION_SAFE_TO_EXECUTE=false
SUCCESSOR_RUNTIME_ACCEPTANCE_SAFE_TO_EXECUTE=false
DOWNSTREAM_SOURCE_BLOCKER=OPEN
~~~

No successor activation authorization is granted.

## 4. Root cause and repair direction

Recovery tests modeled `runtime_acceptance_authorization_history=[]`, while the real pre-recovery transaction carried
the field as null. The recovery path preserved null when returning to PREPARED.

The repair must not weaken generic malformed-history rejection. It must add a dedicated exact PREPARED-state repair
bound to the current source/manifest/launcher, accept only this known null representation, normalize it to `[]`,
preserve failed-acceptance/recovery evidence, replace only the launcher with an exact successor, stay PREPARED, and
consume a distinct one-shot repair authorization before replacement.

## 5. Gate closure

~~~text
POSTEXECUTION_READONLY_RESULT=PASS
POSTEXECUTION_DURABLE_PREPARED=PASS
AUTHORIZATION_LEDGER_CAPTURE=PASS

DOWNSTREAM_SOURCE_BLOCKER=OPEN
LIVE_MUTATION_AFTER_DISCOVERY=false

NEXT_ONE_GATE=N3W_T1_F4_PREPARED_AUTHORIZATION_HISTORY_NULL_SOURCE_REPAIR_20261016_01
AUTO_EXECUTE_SOURCE_REPAIR=true
AUTO_EXECUTE_LIVE_REPAIR=false
~~~
