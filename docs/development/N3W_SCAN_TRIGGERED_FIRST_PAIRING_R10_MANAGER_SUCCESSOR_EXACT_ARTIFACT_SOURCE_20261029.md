# N3-W R10 Manager successor exact-artifact source — 2026-10-29

## Gate

N3W_SCAN_TRIGGERED_FIRST_PAIRING_R10_MANAGER_SUCCESSOR_EXACT_ARTIFACT_SOURCE_IMPLEMENTATION_20261029_01

This gate is repository source/CI work only.

T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
BOARD_WRITE=false
LIVE_AUTHORIZATION_GRANTED=false
EXACT_ARTIFACT_PRODUCTION_ON_NORMAL_CI=false
MERGE_TO_MAIN=false

## Product authority

The Manager successor is bound to the integrated R10 product authority:

- product source: ff750b3801a282af1667b5fa63481e2333e301b3
- product tree: ee6ee5e362628fa725d57fbdf50c6608e9032b17
- predecessor source: e299c937a7b89bb8a7b9a7432186ba46a416cd44
- predecessor Manager image: local/greenhouse-manager:fresh-e299c937a7b8
- target Manager image: local/greenhouse-manager:fresh-ff750b3801a2

The production Manager source delta from predecessor to target is exactly one file:

host/greenhouse-manager/src/greenhouse_manager/runtime/n3w_registration_discovery.py

Required behavioral delta: predecessor candidate TTL 30 seconds -> target candidate TTL 60 seconds.

There is no infra/n3w-t1 delta, Dockerfile delta, Compose delta, database-schema delta, Broker image delta, or Home Assistant image delta.

## Why the old R10 candidate-upgrade package is not reused

The historical R10 T1 candidate-upgrade executor changed a wider surface: runtime files, F4 successor authority, registration TLS material and Manager image. Those changes were necessary when the registration runtime was first introduced, but are not required for this TTL-only Manager successor.

Replaying the old package would unnecessarily rotate registration TLS and rewrite historical deployment authority. It would also attempt to reuse an old one-shot upgrade route. This successor therefore uses a separate package schema, transaction file and authorization namespace.

## Package contents

The exact successor package contains exactly four files:

1. manifest.json
2. greenhouse-manager-arm64.tar
3. refresh-executor.py
4. manager-python-distributions.json

It contains no Broker image, Home Assistant image, registration TLS certificate/key, Compose file, MQTT password, Setup Secret, or Board material.

The Manager image archive is bound by package SHA-256, Docker archive config digest, Docker archive manifest digest, artifact-owned RootFS.Layers fingerprint, artifact-owned Config contract fingerprint, linux/arm64 platform, target image tag, exact product source/tree, exact Manager discovery source blob, exact Dockerfile blob, exact Compose blob, pinned arm64 base-image manifest digest, and installed Python distribution inventory. The live executor rechecks the distribution-inventory SHA/size/content rather than trusting file presence.

## Live executor boundary

The packaged executor has a read-only preflight and a future one-shot apply entrypoint.

The read-only preflight validates exact package/manifest/executor binding, predecessor Manager image, target Manager image absence, Broker and Home Assistant baselines, application/registration units, GH_MANAGER_IMAGE predecessor binding, database integrity, registration count=1, first-registration attempt count=0, unresolved first registration=0, pairing window CLOSED, 47110=1, 47111=1, 47112=0, and predecessor candidate TTL=30.

The preflight does not claim authorization and does not write target state. It also requires the historical F4 activation transaction and the predecessor R10 candidate-upgrade transaction to be committed, consumed/non-replayable predecessor authority for e299c937..., and freezes both ledger file hashes into the new refresh prestate.

A future live apply is not authorized by this source gate. When separately authorized, the executor may claim a new N3W_R10_MANAGER_SUCCESSOR_REFRESH authorization, create a private workspace, load the exact target Manager image, stop the existing Manager+Home Assistant application unit, prove Broker continuity and database quiescence, change only the GH_MANAGER_IMAGE line in /etc/n3wfc4/docker-compose.env, restart the application unit, verify the target runtime, and commit the refresh transaction.

The existing systemd unit couples Manager and Home Assistant, so one bounded application-layer stop/start affects both containers. The executor does not change the Home Assistant image, configuration or persistent data.

## Protected runtime invariants

The following are hashed or semantically fingerprinted before refresh and must remain unchanged after target Manager start:

- production Compose file bytes
- registration TLS certificate bytes
- registration TLS private-key bytes
- Broker DynSec bytes
- historical F4 activation transaction bytes
- predecessor R10 candidate-upgrade transaction bytes
- Broker container identity/image/start state
- Home Assistant container identity and image
- registration database business-state fingerprint
- registration count and first-registration attempt state
- pairing window CLOSED
- TCP/47112 closed

The target Manager must additionally prove candidate TTL=60. Image verification follows the existing KF-111 cross-image-store rule: a Docker runtime .Id is local evidence only and is not required to equal the CI/archive .Id representation. The loaded tag must instead reproduce the artifact-owned arm64/linux RootFS.Layers fingerprint and Config contract; the running Manager container is then bound to that locally verified runtime ID.

## Rollback

If target postcheck fails after the one-shot authorization is claimed, the executor stops the application unit, restores the exact predecessor docker-compose.env bytes, restarts the predecessor application, proves predecessor Manager plus Broker/HA/protected-state continuity, removes the target image tag only after predecessor runtime is healthy, and persists ROLLED_BACK.

A failed or rolled-back authorization remains consumed and is not replayable. The production authorization namespace accepts dated one-shot IDs only; no TEST authorization is accepted by the packaged executor. The executor does not restore or rewrite registration TLS, DynSec, Compose, F4 authority or Board state. Rollback must also prove predecessor candidate TTL=30.

## CI staging

Workflow: .github/workflows/n3w-r10-manager-successor-refresh-package-ci.yml

Normal branch/PR CI performs Python syntax checks, focused tests, product source/tree/blob binding, proof that the Manager production delta is exactly one file, proof of TTL 30 -> 60 transition, KF-111 cross-store runtime-ID regression coverage, predecessor-ledger binding checks, and live-package inventory-integrity checks. Normal CI does not produce an exact Manager package.

Exact artifact production requires a later explicit workflow_dispatch with produce_exact_artifact=true.

That manual build resolves and pins the linux/arm64 python:3.11-slim manifest digest, builds the exact target Manager image, verifies arm64/linux/user/entrypoint, runs a TTL=60 positive control inside the image, captures installed Python distributions, assembles the four-file package, uploads it, then redownloads and independently verifies package bindings.

## Source files in this gate

- tools/execution_packages/n3w/scan_first_pairing/r10_manager_successor_refresh/package_builder.py
- tools/execution_packages/n3w/scan_first_pairing/r10_manager_successor_refresh/live_refresh.py
- tests/execution_packages/n3w/scan_first_pairing/r10_manager_successor_refresh/test_manager_successor_refresh.py
- .github/workflows/n3w-r10-manager-successor-refresh-package-ci.yml
- this document

## Required next step

Source CI and an independent source review must pass before any exact-artifact dispatch.

No T1 preflight or live apply is authorized by this document.
