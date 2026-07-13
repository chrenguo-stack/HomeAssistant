# T1 Manager Identity Execution Transaction Gate v1

## Purpose

This M2.4g-6k gate sits after a verified 6j authorization and before any authorization claim or production manager-only migration transaction.

It verifies that the authorization, fresh rollback package, saved live-runtime gate, current live-runtime gate, production driver contract and manager preparation still describe the same real T1 state. It then emits a second exact operator confirmation phrase.

The gate is read-only. It cannot claim or consume authorization, install a production driver, write manager credentials, edit Compose, recreate a container, publish MQTT traffic or apply the migration.

## Inputs

The gate binds:

- one unclaimed, unconsumed and currently valid `manager-execution-authorization-*` file;
- the exact still-fresh `greenhouse-manager-execution-preparation-*` directory;
- the exact production manager driver-contract file;
- the exact manager migration-preparation directory;
- the fresh rollback archive and manifest;
- the saved and newly rebuilt real-T1 live-runtime gate;
- adapter, driver, runtime, live-binding, preparation and execution-plan SHA-256 values.

## Validation sequence

1. Verify the private authorization file and all 6j bindings.
2. Re-run 6j authorization verification, including a real read-only `docker inspect greenhouse-manager` gate.
3. Verify the complete 6i execution-preparation package and freshness window.
4. Verify the manager preparation record set and production driver logical contract.
5. Rebuild the live-runtime gate again and require it to equal the gate saved with the rollback package.
6. Require both authorization and rollback package to remain unexpired.
7. Emit the second confirmation phrase.

## Exact second confirmation

```text
EXECUTE-M2-MANAGER-MIGRATION:<authorization-id>:<execution-manifest-16>:<rollback-16>:<live-binding-16>
```

The phrase authorizes no action by itself. A later production transaction module must independently require it, atomically claim the single-use authorization before the first write, maintain a phase journal, limit recreation to `greenhouse-manager`, run postactivation checks and perform mandatory rollback on any post-claim failure.

## Mandatory safety state

A passing report must retain:

```text
transaction_gate_ready=true
authorization_valid=true
authorization_single_use=true
operator_decision_required=true
second_operator_confirmation_present=false
authorization_claim_required=true
authorization_claimed=false
claim_enabled=false
production_manager_driver_installed=false
production_executor_available=false
execution_enabled=false
apply_enabled=false
operator_action_authorized=true
ready_for_manager_migration_apply=false
manager_identity_migrated=false
node_credentials_delivered=false
current_services_modified=false
preserve_anonymous=true
anonymous_closure_enabled=false
rollback_mandatory_on_any_post_claim_failure=true
postactivation_audit_mandatory=true
```

## Prohibited actions

This gate must not:

- claim, consume, rename or modify the authorization file;
- create an active manager secret root or password;
- edit Compose files or `.env`;
- restart or recreate `greenhouse-manager`;
- modify Mosquitto, Home Assistant or any node;
- publish, subscribe or probe through MQTT;
- close anonymous compatibility;
- set `execution_enabled`, `apply_enabled` or `ready_for_manager_migration_apply` true.

## CLI

```bash
python3 \
  host/greenhouse-manager/tools/run_t1_manager_identity_migration_execution_transaction_gate.py \
  AUTHORIZATION_FILE \
  EXECUTION_PREPARATION_DIRECTORY \
  DRIVER_CONTRACT_FILE \
  MANAGER_PREPARATION_DIRECTORY
```

The normal report contains no authorization token, secret value or raw host path.
