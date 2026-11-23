# N3-W T1 Core Stack OTA V1.3 — fresh HA 10.4 → 10.0 PREPARE pre-execution

Date: 2026-11-23

## 0. Authorization

```text
GATE=N3W_T1_V1_3_FRESH_HA_PREPARE_10_4_TO_10_0_20261123_01
AUTHORIZATION_STATUS=APPROVED
SCOPE=FRESH_PREPARE_ONLY
FRESH_TRANSACTION_CREATE=true
FRESH_CANDIDATE_MATERIALIZATION=true
FRESH_PREPARE_AUTHORITY=true
PREPARE_TO_U4=true
INSTALL_INTENT=false
INSTALL_AUTHORITY=false
HA_INSTALL_OR_CUTOVER=false
BROKER_OTA=false
REBOOT=false
MERGE=false
RELEASE=false
```

The previously failed KF-144 transaction is terminal historical evidence and is not reused. This gate creates a new ordinary HA U0-U13 transaction through the existing privileged maintenance entry and stops at a fresh U4 READY_TO_INSTALL.

## 1. Entry live authority

The immediately preceding KF-144 live repair closed with:

```text
OLD_HA_TRANSACTION_STATUS=ROLLED_BACK
OLD_HA_TRANSACTION_PHASE=U4_READY_TO_INSTALL
OLD_HA_TRANSACTION_SHA256=0ea710421e8067b7f8a6c26827b561f220876ed45b97650c6b94e338533698cf
OLD_HA_TRANSACTION_ID_SHA256=760dc8bdab1c9ceee2b0d3dfb2797111f24e69a9e7569efb6907bc64325d71fe

LIVE_HOMEASSISTANT=local/n3w-homeassistant:2026.10.4-5881590f
LIVE_HOMEASSISTANT_IMAGE_ID=sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365
LIVE_MANAGER=local/greenhouse-manager:fresh-1cae18039eee
LIVE_MANAGER_IMAGE_ID=sha256:c4bcb441de0554ebb20e3feb2b98a65cc435750539a2c951eb7be710ff191221
LIVE_BROKER=local/n3w-mosquitto:2.1.2-3184566d
LIVE_BROKER_IMAGE_ID=sha256:df265f1e2b2e3dc35d5eb194e698c598e01c5ebca370da307b34332f9bf0a563

MANAGER_TRANSACTION_SHA256=32e0dd5e19d9d49576bb135e74ec1cb85cb8f6eca2265acaeab32b5d0c82f784
MANAGER_RUNTIME_CLASS=TARGET_BOUND_RUNNING
MANAGER_HEALTH_STATE=HEALTHY
MONITORING_SELF_TEST_SHA256=5a0ea7132529ca096cc18363765cb96a40352036e0902df343b86675d02be3c1
INSTALLED_HA_VERSION_BINDING=2026.10.4
```

Fresh execution must re-prove this state before mutation.

## 2. Exact reverse-preparation authority

Executable source:

```text
EXECUTABLE_SOURCE_HEAD=1fbe674e25edb4c6fb1a3740042778adc55def68
TARGET_MANIFEST=infra/n3w-t1/upgrades/homeassistant-2026.10.0-r8-predecessor-preparation.json
TARGET_MANIFEST_GIT_BLOB_SHA1=e5adcd18867330f82381c96ee5fe1084bf2b64ba
RELEASE_IDENTITY=homeassistant-r8-predecessor-2026.10.0
```

Target:

```text
TARGET_IMAGE=local/n3w-homeassistant:2026.10.0-0c73235a
EXPECTED_PREDECESSOR=local/n3w-homeassistant:2026.10.4-5881590f
TARGET_ARCHIVE_SIZE_BYTES=2448553472
TARGET_ARCHIVE_SHA256=e52d12779f7562d3f37a265d622fbaf31e758deba5998e40cafb5a33a118b663
TARGET_PLATFORM=linux/arm64
TARGET_IMAGE_CONFIG_ID=sha256:b0e1ee82adfb19fa1ff3049034535633b1c4f0df6606721c0e77383854b99879
```

Artifact:

```text
ARTIFACT_RUN_ID=41275979177
ARTIFACT_ID=13070404405
ARTIFACT_NAME=n3w-t1-fresh-exact-arm64-24382caae4a1f5d459297f86e8d18f10a848ca64
ARTIFACT_DIGEST_SHA256=99eae7602eb2f8318bb7c0fff29d71fa61471071902b854a90666d4beb931b93
ARTIFACT_SOURCE_HEAD=24382caae4a1f5d459297f86e8d18f10a848ca64
```

The focused R8 regression defines the approved envelope as schema `gh.n3w-t1-ota-approved-manifest/1`, release identity `homeassistant-r8-predecessor-2026.10.0`, version `2026.10.0`, target archive size 2448553472, and the exact target document above.

## 3. Candidate-source optimization

The terminal KF-144 transaction already has an exact verified/fsynced 10.0 `target.tar` on the bound USB. The new execution may use that old USB file only as an **external byte source** for fresh candidate materialization after re-proving:

- old transaction exact terminal identity;
- target recovery record exact SHA/size/image and verified+fsynced flags;
- original USB UUID mounted uniquely as ext4/rw;
- source is a root-owned, mode-0600, single-link regular file under the old transaction directory.

Product `materialize_candidate()` independently re-hashes and parses the complete 2.45-GB source while creating the deterministic internal candidate spool. This avoids a network redownload and does not reuse the old transaction journal/material records.

The fresh PREPARE then writes and verifies new target/predecessor archives under the new transaction directory. Existing product logic retires only the updater-owned internal spool after the new USB copies are exact and fsynced.

## 4. Bounded execution

```text
READONLY_REBIND
→ VERIFY_ACTIVE_CANDIDATE_MONITORING_RUNTIME
→ MATERIALIZE_EXACT_REVERSE_CANDIDATE
→ CREATE_FRESH_U1_TRANSACTION
→ ISSUE_FRESH_SCHEMA_V2_PREPARE_AUTHORITY
→ RESUME_PREPARE
→ FRESH_U4_READY_TO_INSTALL
→ STOP
```

The fresh prepare authority is bound to the new transaction ID, current USB filesystem UUID, exact deterministic internal target source, current launch binding and a new future expiry. Historical expired authorities are not replayed.

Expected terminal state for this gate:

```text
FRESH_TRANSACTION_STATUS=ACTIVE
FRESH_TRANSACTION_PHASE=U4_READY_TO_INSTALL
CURRENT_IMAGE=local/n3w-homeassistant:2026.10.4-5881590f
TARGET_IMAGE=local/n3w-homeassistant:2026.10.0-0c73235a
TARGET_ARTIFACT_VERIFIED=true
PREPARED_TARGET_SHA256=e52d12779f7562d3f37a265d622fbaf31e758deba5998e40cafb5a33a118b663
PREPARED_TARGET_SIZE=2448553472
PREPARED_PREDECESSOR=local/n3w-homeassistant:2026.10.4-5881590f
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
INSTALL_AUTHORITY_PRESENT=false
TARGET_10_0_DOCKER_IMAGE_LOADED=false
HA_INSTALL_OR_CUTOVER=false
```

## 5. Operator executor binding

```text
EXECUTOR=N3W_T1_V1_3_FRESH_HA_PREPARE_10_4_TO_10_0_20261123_01.sh
EXECUTOR_SHA256=4f987e40875e633d3c996c8c56477aa1b7bfab5cf14984af09767ffbc140faf3
EMBEDDED_REMOTE_PYTHON_COMPILE=PASS
```

The operator copy contains the private T1 locator and is not committed to the public repository.

## 6. STOP conditions

STOP without install/cutover on any source/artifact/runtime/transaction/USB/candidate-monitoring drift; any target 10.0 Docker image preexistence; unexpected active authority; materialization failure; fresh transaction mismatch; prepare-authority mismatch; capacity failure; archive mismatch; predecessor export mismatch; or any state other than exact fresh U4 after preparation.

On failure, the private remote staging directory is preserved. Do not automatically replay an already-created fresh transaction; continue only from its durable state after classification.

