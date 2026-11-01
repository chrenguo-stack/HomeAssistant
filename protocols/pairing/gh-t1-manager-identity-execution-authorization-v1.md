# T1 Manager Identity Execution Authorization v1

## Purpose

This gate is the M2.4g-6j boundary between a verified, still-fresh manager execution-preparation package and any later production manager-only migration transaction.

It provides request, create and verify operations for a short-lived, single-use authorization. It does not claim the authorization, install the production manager driver, enable execution or apply the migration.

## Inputs

Every operation binds all of the following:

- the current `greenhouse-manager-execution-preparation-*` directory;
- the exact production manager driver-contract file used to create that package;
- the exact manager migration-preparation directory;
- the fresh manager-only rollback archive and manifest;
- the saved and newly rebuilt live-runtime gate;
- the adapter, driver, runtime, live-binding, preparation and execution-plan SHA-256 values.

## Request operation

The request operation:

1. verifies the complete execution-preparation package and fresh rollback;
2. requires at least 60 seconds of package freshness to remain;
3. rebuilds the real-T1 live-runtime gate using one read-only `docker inspect greenhouse-manager`;
4. requires the current gate to match the gate captured with the rollback package;
5. emits the exact confirmation phrase:

```text
AUTHORIZE-M2-MANAGER-EXECUTION:<execution-manifest-16>:<rollback-16>:<live-binding-16>
```

The request does not create an authorization.

## Create operation

The create operation requires the exact request confirmation. It repeats all package and live-runtime validation before writing one private authorization file.

Authorization rules:

- TTL is between 60 and 1800 seconds;
- authorization expiry must not exceed the execution-preparation expiry;
- the token is stored only in the mode-0600 authorization file;
- stdout contains only the derived authorization ID, hashes and safety flags;
- authorization is single-use and initially `consumed=false`;
- authorization remains unclaimed;
- no execution or apply capability is enabled.

## Verify operation

Verification repeats package freshness and live-runtime validation and rejects:

- expired or insufficiently fresh execution preparation;
- expired authorization;
- authorization that outlives the fresh rollback package;
- changed runtime, Compose, secret target, driver or preparation bindings;
- changed token/authorization-ID binding;
- `consumed=true` or any safety-flag drift.

## Safety state

A request must retain:

```text
authorization_created=false
operator_decision_required=true
operator_action_authorized=false
authorization_claimed=false
production_manager_driver_installed=false
production_executor_available=false
execution_enabled=false
apply_enabled=false
ready_for_manager_migration_apply=false
manager_identity_migrated=false
node_credentials_delivered=false
current_services_modified=false
preserve_anonymous=true
anonymous_closure_enabled=false
```

A created and verified authorization may set only:

```text
operator_action_authorized=true
```

It must still retain:

```text
consumed=false
authorization_claimed=false
production_manager_driver_installed=false
production_executor_available=false
execution_enabled=false
apply_enabled=false
ready_for_manager_migration_apply=false
manager_identity_migrated=false
node_credentials_delivered=false
current_services_modified=false
preserve_anonymous=true
anonymous_closure_enabled=false
```

## Prohibited actions

This gate does not:

- write the active manager password;
- edit Compose or `.env`;
- recreate or restart any container;
- modify Mosquitto or Home Assistant;
- publish or subscribe through MQTT;
- claim or consume the authorization;
- deliver node credentials;
- close anonymous compatibility.

## CLI

Request only:

```bash
python3 \
  host/greenhouse-manager/tools/run_t1_manager_identity_migration_execution_authorization.py \
  request \
  EXECUTION_PREPARATION_DIRECTORY \
  DRIVER_CONTRACT_FILE \
  MANAGER_PREPARATION_DIRECTORY
```

Create only after an explicit operator decision:

```bash
python3 \
  host/greenhouse-manager/tools/run_t1_manager_identity_migration_execution_authorization.py \
  create \
  EXECUTION_PREPARATION_DIRECTORY \
  DRIVER_CONTRACT_FILE \
  MANAGER_PREPARATION_DIRECTORY \
  PRIVATE_AUTHORIZATION_OUTPUT_DIRECTORY \
  --confirmation 'AUTHORIZE-M2-MANAGER-EXECUTION:...' \
  --ttl-seconds 600
```

Verification:

```bash
python3 \
  host/greenhouse-manager/tools/run_t1_manager_identity_migration_execution_authorization.py \
  verify \
  AUTHORIZATION_FILE \
  EXECUTION_PREPARATION_DIRECTORY \
  DRIVER_CONTRACT_FILE \
  MANAGER_PREPARATION_DIRECTORY
```

A later module must separately define authorization claim, production driver installation, exact execution confirmation, manager-only recreation, postactivation audit and mandatory rollback. This authorization gate cannot perform those actions.
