# N3W T1 F5-8 Current Release T1-B Read-only Preflight — Preexecution

Date: 2026-10-19

## Gate

~~~text
TASK=N3W_T1_F5_8_CURRENT_RELEASE_T1B_READONLY_PREFLIGHT_20261019_01
STATE=AUTHORIZED_READY_FOR_REAL_T1_READONLY_EXECUTION

USER_T1B_READONLY_AUTHORIZATION=GRANTED
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false

T1_ACCESS_AUTHORIZED=true
T1_MUTATION=false
LIVE_REBOOT=false
PRODUCT_SERVICE_START=false
BOARD_ACCESS=false
MERGE=false
~~~

## Current durable release authority

~~~text
PRODUCT_SOURCE_HEAD=4afd89b56e9925d7330b27f3f734ebcefc09182c
PRODUCT_SOURCE_TREE=da864ffb6c44de3efccb93516e5e786f16219cd9
RELEASE_BUILDER_HEAD=f30e5f74199bebcf1f189ee90b81ce5d19dc3df1

RELEASE_ID=c8a7e432722121b808a0d31ffbc3d049a64aa5b4f270a7be6f07b90891eecf69
RELEASE_SHA256=47f4f41cf1453642b889578bd7de906236b56ae34b9d7bbbc81412c78a48efbb
FILE_INDEX_SHA256=21a419ac843a3ef4c00fa2054435df403d0c5c16911bdf0f2e9dde3afb4b8ae9

WORKFLOW_RUN_ID=39259401930
ARTIFACT_ID=12190255517
ARTIFACT_ZIP_SHA256=c5928031d6813f91508eadd7bf79aca63e1fbe9c67e840f0a8277e8a09675f9f
DURABLE_MAC_ARCHIVE=CLOSED_PASS
~~~

The real-T1 read-only preflight must use the durable Mac copy above and the packaged
Mac orchestrator from that exact release. It must not use a later docs-only rebuild.

## Target trust boundary

Historical accepted T1-B trust evidence:

~~~text
HISTORICAL_T1B_SSH_HOST_KEY_SHA256=2e6cae2b43ba5d7d0818fa53b4175a6bf58442077b32caf44b0bf886e6e4a901
HISTORICAL_T1B_TARGET_BINDING_SHA256=280c06d1753dc676ca7c11b1967ae603a432bb3c996abb305a449c85cf5ca3b3
~~~

The host key remains an input trust anchor. The target binding must be freshly recomputed
from the live T1-B machine-id plus ED25519 host key during this gate; the historical target
binding is not accepted as a substitute for fresh evidence.

## Required acceptance

The packaged read-only path must establish one managed SSH epoch, perform identity,
host/network/time, product-absence, Docker/baseline, storage/capacity, package-policy and
exact-release binding checks, then close the SSH session.

Required public result:

~~~text
STATUS=PASS
READ_ONLY=true
MUTATION_PERFORMED=false
SESSION_CLOSED=true
SSH_HOST_KEY_SHA256=2e6cae2b43ba5d7d0818fa53b4175a6bf58442077b32caf44b0bf886e6e4a901
TARGET_BINDING_SHA256=FRESHLY_PROVEN
T1_MUTATION=false
LIVE_REBOOT=false
PRODUCT_SERVICE_START=false
BOARD_ACCESS=false
~~~

Private raw evidence remains on the production Mac and must not be committed.

## Stop rule

~~~text
CURRENT_STOP_POINT=WAIT_REAL_T1B_READONLY_PREFLIGHT_OUTPUT
NEXT_IF_PASS=RECORD_F5_8_CURRENT_RELEASE_CLOSURE_AND_PREPARE_EXPLICIT_F5_9_AUTHORIZATION_DECISION
NEXT_IF_STOP=CLASSIFY_READONLY_PREFLIGHT_FAILURE_NO_MUTATION
AUTO_EXECUTE_F5_9=false
NEW_F5_9_PRODUCTION_AUTHORIZATION=false
STOP=true
~~~
