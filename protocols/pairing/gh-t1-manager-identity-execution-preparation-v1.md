# T1 Manager Identity Execution Preparation v1

## Purpose

This package is the 6i bridge between the successful real-T1 manager live-runtime gate and a later, separately authorized manager-only migration transaction.

It captures and verifies a fresh rollback archive, binds the current runtime and Compose state, and emits a short-lived execution-preparation packet. It does not create an authorization and cannot apply the migration.

## Inputs

- Current manager production driver contract
- Current manager identity migration preparation directory
- Private output directory whose name starts with `greenhouse-m2-manager-execution-preparations`
- Freshness period between 60 and 1800 seconds

## Read-only and rollback behavior

The tool:

1. Re-runs the real-T1 manager live-runtime gate.
2. Verifies the running manager identity and Compose binding have not drifted.
3. Captures the exact current manager Compose files and optional `.env` into a private rollback archive.
4. Records that the future manager password target is still absent.
5. Binds the rollback manifest to `manager_only=true`, `preserve_anonymous=true`, and `anonymous_closure_enabled=false`.
6. Verifies archive members, modes, ownership, sizes, SHA-256 values, and the anonymous-compatibility safety binding.
7. Re-runs the live-runtime gate and rejects any drift during capture.
8. Creates a short-lived, non-executable preparation package.

The tool does not:

- write the active manager password
- edit Compose or `.env`
- recreate any container
- modify Mosquitto or Home Assistant
- deliver node credentials
- close anonymous compatibility
- create or claim an operator authorization

## Output

Schema:

`gh.m2.t1-manager-identity-execution-preparation/1`

Each private package contains:

- `fresh-manager-rollback.tar.gz`
- `fresh-rollback-manifest.json`
- `live-runtime-gate.json`
- `execution-plan.json`
- `operator-runbook.txt`
- `manifest.json`

The normal stdout report contains no secret values or source paths.

## Required safety state

The report must include:

- `fresh_rollback_captured=true`
- `fresh_rollback_verified=true`
- `execution_preparation_ready=true`
- `read_only_live_services=true`
- `current_services_modified=false`
- `authorization_created=false`
- `authorization_claimed=false`
- `production_manager_driver_installed=false`
- `production_executor_available=false`
- `execution_enabled=false`
- `apply_enabled=false`
- `operator_action_authorized=false`
- `manager_identity_migrated=false`
- `node_credentials_delivered=false`
- `ready_for_manager_migration_authorization=true`
- `ready_for_manager_migration_apply=false`
- `preserve_anonymous=true`
- `anonymous_closure_enabled=false`

The same three target-scope and compatibility fields must also be present in the fresh rollback manifest:

- `manager_only=true`
- `preserve_anonymous=true`
- `anonymous_closure_enabled=false`

A missing or contradictory rollback safety field invalidates the execution preparation before authorization claim.

## CLI

```bash
python3 \
  host/greenhouse-manager/tools/run_t1_manager_identity_migration_execution_preparation.py \
  DRIVER_CONTRACT_FILE \
  MANAGER_PREPARATION_DIRECTORY \
  --output PRIVATE_OUTPUT_DIRECTORY \
  --freshness-seconds 900
```

The package expires at `expires_at`. A later authorization must bind to a still-fresh package and must not reuse an expired rollback capture.
