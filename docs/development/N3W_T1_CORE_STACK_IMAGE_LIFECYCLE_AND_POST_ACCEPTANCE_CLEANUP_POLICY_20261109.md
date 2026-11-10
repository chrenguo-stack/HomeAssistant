> **2026-11-10 source implementation update**
>
> \`SOURCE_IMPLEMENTATION=COMPLETE\`; \`FOCUSED_CI_FINAL_RESULT=PENDING\`.
> Generic V2 now has an explicit post-acceptance \`finalize\` primitive for Manager/Broker, exact image-ID deletion guards, retained cleanup metadata, rollback-window closure after acceptance, and a Generic V2 successor-apply cleanup guard. Home Assistant remains on the mandatory-USB lifecycle; the historical R7A HA-USB exact-source files are intentionally unchanged. A separate pre-transfer storage policy now binds exact staged bytes + exact Docker-save import worst case + a fresh derived post-peak reserve; broad prune remains forbidden. No live T1 image deletion is authorized or executed by this source update.
>
> Implementation archive: \`docs/development/N3W_T1_STORAGE_HEADROOM_AND_IMAGE_LIFECYCLE_SOURCE_IMPLEMENTATION_PROGRESS_20261110.md\`.

# N3-W T1 Core Stack image lifecycle and post-acceptance cleanup policy — 2026-11-09

~~~text
STATUS=DESIGN_FROZEN_SOURCE_IMPLEMENTATION_PENDING
SCOPE=Manager;HomeAssistant;Broker
TARGET_HARDWARE=16GB-class T1
STEADY_STATE_INTERNAL_GENERATION_COUNT_PER_COMPONENT=1
BROAD_DOCKER_PRUNE=false
~~~

## 1. Decision

The T1 internal Docker image store is runtime storage, not a long-term release archive.

For Manager, Home Assistant and Broker, the normal accepted steady state is exactly one internal image generation: the currently accepted version.

An immediate predecessor may exist only inside an active upgrade/acceptance rollback window. Once the target has passed the component-specific independent product acceptance gate, the predecessor image is no longer a required local rollback asset and must be removed by an exact, bounded cleanup operation.

No component keeps a permanent local previous version merely for convenience.

Release identity, transaction history and rollback provenance remain durable metadata. They are not represented by retaining old Docker image bytes indefinitely.

## 2. Meaning of upgrade successful

Generic V2 COMMITTED is not the final cleanup boundary.

Current A2 architecture defines COMMITTED as technical transaction success plus minimum runtime health. It explicitly requires an independent post-upgrade product acceptance gate.

Therefore:

~~~text
APPLY
-> COMMITTED
-> PREDECESSOR_ROLLBACK_HELD
-> INDEPENDENT_PRODUCT_ACCEPTANCE
-> ACCEPTED
-> FINALIZE_CLEANUP
-> PREDECESSOR_IMAGE_REMOVED
-> STEADY_STATE_ONE_GENERATION
~~~

Generic V2 already permits explicit rollback from COMMITTED. The predecessor must remain available until independent product acceptance passes.

If product acceptance fails while the predecessor is retained, rollback remains the preferred recovery path.

## 3. Manager lifecycle

During Manager upgrade:

- retain the exact predecessor Manager image;
- load/verify the exact target Manager image;
- activate target through the existing Manager + Home Assistant owner boundary;
- keep predecessor through Generic V2 COMMITTED;
- run independent Manager product acceptance: Manager runtime, MQTT authentication, relevant business path, peer continuity and required health checks;
- on acceptance PASS, finalize and delete the exact predecessor Manager image;
- on acceptance FAIL, rollback to the retained predecessor.

After finalization:

~~~text
INTERNAL_MANAGER_GENERATION_COUNT=1
AUTOMATIC_ROLLBACK_TO_PREVIOUS_MANAGER_AFTER_FINALIZE=false
~~~

A later problem after finalization is a new maintenance/update incident, not continuation of the completed rollback window.

## 4. Broker lifecycle

Broker uses the same lifecycle policy.

During Broker upgrade:

- retain the exact predecessor Broker image;
- activate only the target Broker binding through the controlled Broker owner sequence;
- restore Manager + Home Assistant and verify authenticated reconnection;
- keep predecessor through COMMITTED;
- run independent Broker product acceptance: TLS/listeners, DynSec structural contract, Manager/HA reauthentication and required node path where applicable;
- on acceptance PASS, finalize and delete the exact predecessor Broker image;
- on acceptance FAIL, rollback to the retained predecessor.

After finalization:

~~~text
INTERNAL_BROKER_GENERATION_COUNT=1
AUTOMATIC_ROLLBACK_TO_PREVIOUS_BROKER_AFTER_FINALIZE=false
~~~

The current Broker product-upgrade path is not yet fully product-validated; implementation must apply this policy when that path is completed.

## 5. Home Assistant lifecycle

Home Assistant keeps the already frozen mandatory-USB V1.1 model.

Normal steady state:

~~~text
INTERNAL_HA_GENERATION_COUNT=1
~~~

The USB contains the exact target, predecessor recovery image and HA data recovery point during the destructive upgrade/rollback window.

After target health acceptance and durable successful commit, the user may remove the USB. At that point the product does not promise automatic rollback to the previous Home Assistant version.

Therefore Home Assistant and Manager/Broker share the same high-level product rule:

rollback assets are temporary transaction assets, not permanent local historical generations.

The storage location differs:
- Home Assistant recovery assets live on the bound USB during the transaction;
- Manager/Broker immediate predecessor images remain internally only until product acceptance/finalization.

## 6. Exact cleanup rules

No broad cleanup command is allowed.

Forbidden:

~~~text
docker system prune
docker image prune -a
wildcard image deletion
delete-by-age
delete-all-unused
~~~

Finalization may remove only an exact predecessor image that is proven by all of:

1. transaction status is COMMITTED;
2. component-specific independent product acceptance is PASS;
3. current binding is the exact accepted target;
4. target runtime is healthy;
5. predecessor image reference and T1-local image ID match the transaction record;
6. no current container references the predecessor image;
7. predecessor is not the current image of any product component;
8. no active/non-terminal upgrade or HA-USB transaction requires it;
9. removal command targets the exact image ID;
10. post-removal current target and peer health remain PASS.

Failure to satisfy any condition stops cleanup without deleting the image.

## 7. Staging artifacts

Image archive staging is temporary transport state.

For Manager/Broker Generic V2:

- after the target image is loaded and exact portable identity/runtime identity verification passes, the staged target archive is no longer a rollback asset;
- remove the staged archive as soon as its remaining use is complete;
- do not retain old tar files in /var/tmp after closure.

For Home Assistant mandatory-USB:

- target/predecessor/data recovery assets follow the USB transaction contract;
- no full Home Assistant target archive is staged on the internal root filesystem.

## 8. Transaction metadata

Do not delete transaction/history metadata merely because image bytes are removed.

Retain public-safe durable records sufficient to prove:

- predecessor identity;
- target identity;
- authorization consumption;
- apply result;
- rollback result if any;
- product acceptance result;
- cleanup result;
- exact image ID removed;
- cleanup timestamp/state.

A later audit must be able to distinguish:

~~~text
COMMITTED_ROLLBACK_HELD
ACCEPTED_CLEANUP_PENDING
ACCEPTED_CLEANUP_COMPLETE
ROLLED_BACK
CLEANUP_STOPPED
~~~

These may be represented as cleanup metadata without changing Generic V2 terminal transaction semantics if implementation can remain bounded.

## 9. Product storage invariant

After all upgrade/acceptance work is closed:

~~~text
EXPECTED_PRODUCT_IMAGE_GENERATIONS=
  Manager:1
  HomeAssistant:1
  Broker:1
~~~

Historical development/test images must not accumulate indefinitely on production T1 devices.

A storage-health check should classify unexpected extra product generations and low free space before a new upgrade begins.

## 10. Current T1 implication

The current T1 inventory is not an accepted steady state.

Current evidence shows:

- active/current Manager generation plus multiple historical unused Manager generations;
- active Home Assistant 2026.10.0 plus unused internal Home Assistant 2026.10.4;
- active Broker generation;
- root filesystem effectively full.

The unused internal Home Assistant 2026.10.4 image is a historical pre-mandatory-USB/P5 residue and conflicts with the one-internal-HA-generation steady-state policy.

Current cleanup remains a separate live-mutation gate. This design document does not authorize Docker image deletion.

## 11. Source implementation delta

A bounded successor implementation should add a post-acceptance finalization primitive to T1_Core_Updater rather than rewriting Generic V2.

Required conceptual operation:

~~~text
finalize(component, accepted_target, acceptance_authority)
~~~

It must:

- accept only a COMMITTED transaction whose target is still current and healthy;
- bind an explicit product-acceptance authority;
- recheck no conflicting active transaction;
- exact-delete only the predecessor image;
- record cleanup state atomically;
- recheck target/peer health;
- fail closed on ambiguity.

Manager gets this first because its product path already exists.
Broker must use the same primitive when Broker product validation is completed.
Home Assistant continues to use its mandatory-USB-specific U10/U13 lifecycle.

## 12. Frozen decision

~~~text
MANAGER_PERMANENT_PREDECESSOR_RETENTION=false
BROKER_PERMANENT_PREDECESSOR_RETENTION=false
HOMEASSISTANT_PERMANENT_PREDECESSOR_RETENTION=false

MANAGER_PREDECESSOR_RETAIN_UNTIL_PRODUCT_ACCEPTANCE=true
BROKER_PREDECESSOR_RETAIN_UNTIL_PRODUCT_ACCEPTANCE=true
HOMEASSISTANT_RECOVERY_RETAIN_UNTIL_TRANSACTION_ACCEPTANCE=true

POST_ACCEPTANCE_EXACT_CLEANUP_REQUIRED=true
STEADY_STATE_ONE_IMAGE_GENERATION_PER_COMPONENT=true
BROAD_PRUNE_FORBIDDEN=true
~~~
