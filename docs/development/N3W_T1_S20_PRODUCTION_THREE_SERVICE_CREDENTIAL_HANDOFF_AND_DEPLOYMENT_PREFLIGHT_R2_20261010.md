# N3-W T1 S20 production three-service credential handoff and deployment preflight R2

Date: 2026-10-10
Status: FAIL_CLOSED / SOURCE
Repository: chrenguo-stack/HomeAssistant
PR: #541, OPEN DRAFT
REVIEW_BASE=d423211b6196c2f2f0f01dff072c4f877fbe58ee
REVIEW_HEAD=5baa36cac8297d16205864bb2d2adf5eb0a4b5be
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
MERGE=false

## Scope

This gate re-entered the S20 production three-service credential handoff/deployment preflight after Home Assistant automatic MQTT bootstrap isolated runtime acceptance closed PASS.

The gate is source + T1 read-only only. Per project rule, source is checked first and execution stops at the first substantive mismatch. No live T1 read-only probe is performed if the final source deployment authority is not yet coherent enough to bind against runtime.

## Frozen upstream PASS

- S19 isolated service identity and ACL acceptance remains CLOSED_PASS.
- Home Assistant automatic MQTT bootstrap isolated runtime is CLOSED_PASS at exact source `0412d6009c963bf80eb7ce2e21e3fefac69e09a2`, run `38039664411`.
- clean credential bundle source defines exactly manager / provisioning / homeassistant credentials and zero node precreation.
- Manager runtime source supports distinct `GH_MQTT_PASSWORD_FILE` and `GH_N3W_PROVISIONING_PASSWORD_FILE`.
- Home Assistant source consumes private password + bootstrap metadata and uses official MQTT config-flow without direct .storage edits.
- fresh Broker source defines authenticated 1883 and TLS/8883 listeners.
- the clean-product deployment validator rejects non-loopback host 1883 and enforces the expected three-service / two-network contract.

## First substantive mismatch

The repository still has no final clean-product production Compose/deployment package that actually materializes the contract validated by `tools/n3w_t1_clean_product_deployment_gate.py`.

At review head, `infra/compose/t1/` contains only:

- `.env.example`
- `README.md`
- `docker-compose.manager.yml`

These files are byte-identical to main for this path.

The actual `docker-compose.manager.yml` is the historical N1 lab deployment. It contains only `greenhouse-manager` and currently has, among other properties:

- local build + image `greenhouse-manager:n1`;
- `GH_MQTT_HOST=mosquitto`;
- `GH_MQTT_PORT=1883`;
- inline `GH_MQTT_PASSWORD`;
- `GH_MQTT_TLS=false`;
- client ID `greenhouse-manager`;
- bridge attachment to external `ha_docker_default`;
- restart `unless-stopped`.

It does not materialize the current clean-product contract:

- no exact three-service manager/broker/homeassistant deployment document;
- Manager is not `network_mode=host`;
- Manager does not bind the separate manager and provisioning read-only secret files;
- no Provisioning environment binding;
- no Home Assistant private password/bootstrap mounts;
- no Broker `127.0.0.1:1883` publication;
- no Broker `0.0.0.0:8883` TLS publication in this final deployment source;
- no exact `n3wfc4-private` / `n3wfc4-services` network set.

The clean credential bundle currently emits secret fragments, but fragments are not a final rendered deployment authority.

The deployment gate test currently feeds a synthetic in-memory `rendered_compose()` fixture with the desired contract. Therefore CI PASS proves that the validator accepts/rejects the intended schema; it does not prove that a repository production Compose file renders to that schema.

## Additional unbound source items

The following remain unbound at this source stop:

- final Manager production image reference and digest;
- Manager production runtime UID/GID binding;
- Home Assistant OCI digest and ARM64 image binding;
- exact final production Compose startup/dependency ordering;
- exact source-to-host paths for the final clean deployment package.

These items must be closed in source before a meaningful fresh T1 read-only source-to-runtime bind can be performed.

## Classification

```text
EXECUTION_ID=N3W_T1_S20_PRODUCTION_THREE_SERVICE_CREDENTIAL_HANDOFF_AND_DEPLOYMENT_PREFLIGHT_R2_20261010_01
AUTHORIZATION=SOURCE_AND_T1_READ_ONLY
SOURCE_REBIND=PASS
MAIN_EXACT=d423211b6196c2f2f0f01dff072c4f877fbe58ee
PR541_REVIEW_HEAD=5baa36cac8297d16205864bb2d2adf5eb0a4b5be
S19_ISOLATED_IDENTITY_AND_ACL_ACCEPTANCE=CLOSED_PASS
S20_HA_AUTOMATIC_BOOTSTRAP_ISOLATED_RUNTIME=CLOSED_PASS
FINAL_CLEAN_PRODUCT_PRODUCTION_COMPOSE=SOURCE_GAP
DEPLOYMENT_GATE_REAL_REPOSITORY_COMPOSE_BINDING=UNPROVEN
MANAGER_PRODUCTION_IMAGE=UNBOUND
MANAGER_RUNTIME_UID_GID=UNBOUND
HOMEASSISTANT_OCI_DIGEST=UNBOUND
HOMEASSISTANT_ARM64_IMAGE_BINDING=UNPROVEN
T1_FRESH_READONLY_REBIND=NOT_EXECUTED_SOURCE_GAP_STOP
PRODUCTION_CLIENT_CREATION=false
PRODUCTION_BROKER_STARTED=false
HOST_1883_PUBLICATION=false
HOST_8883_PUBLICATION=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
S20_PREFLIGHT_R2_RESULT=FAIL_CLOSED
S20_FAILURE_CLASS=SOURCE_DEPLOYMENT_BINDING
READY_FOR_REAL_SERVICE_IDENTITY_AUTHORIZATION=false
STOP=true
```

## Next gate

```text
NEXT_ONE_GATE=N3W_T1_S20_FINAL_PRODUCTION_COMPOSE_AND_IMAGE_BINDING_SOURCE_REPAIR_20261010_01
```

Required scope:

- create one final clean-product production Compose/deployment source authority;
- consume the existing three-service credential fragments without plaintext secrets;
- freeze Manager and Home Assistant production image refs/digests and target ARM64 availability evidence;
- bind Manager runtime UID/GID policy without hard-coding a historical live UID;
- bind Broker 1883/8883 publications and exact two-network topology;
- encode Broker-authenticated-readiness-before-HA startup ordering;
- make deployment gate CI validate the actual repository production Compose/rendered output, not only a synthetic fixture;
- retain zero-node-precreation and all S19/KF-097 security boundaries.

No T1 live mutation, production account creation, Broker start, host port opening, board access, or PR merge is authorized by this closure.
