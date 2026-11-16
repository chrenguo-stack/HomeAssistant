# N3-W T1 U11 post-R40 successor live recovery R42 source design

## 1. Purpose

R41 real-T1 Attempt 04 proved the exact post-R40 partial-U10 state and returned U11_R41_POST_R40_READONLY_PREFLIGHT_PASS with successor_live_recovery_eligible=true and successor_live_recovery_authorized=false.

R42 is a new one-shot successor recovery. It is not R40 replay and it is not a generic retry path.

R40 already loaded the exact Home Assistant target image and published the target Compose binding. R42 therefore must not load the target image again and must not rewrite that binding.

The only intended live product mutations are: start the existing production services owner, verify exact Manager/Broker/Home Assistant runtime identity, persist U11 metadata to USB, then persist the U11 host transaction. R42 stops before U12.

## 2. Frozen predecessor evidence

R42 is bound to R41 Attempt 04 execution u11-r41-readonly04-20261116T140219Z, RC=0, exact U10 transaction SHA-256 c0dc58ebcfcd2876aec5bfcf556723ae779106803e19df5541b1847fc494bba3, exact target runtime image sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365, target binding local/n3w-homeassistant:2026.10.4-5881590f, exact USB mirror, failed/quiesced services owner, Broker running, Manager and Home Assistant stopped, repaired EXACT_HA_OTA_OVERLAY supervision, and passing post-target-load reserve.

R38 and R40 remain consumed and permanently no-replay.

## 3. Why R40 is not replayed

The original U11 install controller requires the target image to be absent and the binding to point to the predecessor before it performs target load and binding publication. Those two mutations already happened during R40.

Re-entering that install path would violate its preconditions and blur one-shot authorization semantics. R42 resumes only from the exact partial state that R41 proved.

## 4. Preclaim and authorization

Before claim, R42 reruns the complete R41 read-only predicate set in the same remote process. Any mismatch stops before claim.

After that preclaim passes, R42 creates a new state root and durably records a new R42 claim with claimed=true, consumed=true and replay_permitted=false.

R42 immediately reruns the full R41 predicate set after claim. Any drift at that point is STOP_POSTCLAIM and the same R42 authorization cannot be replayed.

Claim persistence uncertainty is STOP_UNKNOWN and is conservatively treated as consumed/no-replay.

## 5. Exact recovery source

The executor binds and transports exact repository bytes for the repaired host source, the U11 controller definitions and the repaired U11 host adapter. They are SHA-256 checked and loaded only into the remote Python process in dependency order host -> U11 -> U11-host.

No repaired source is installed on T1 by this recovery gate.

## 6. Recovery mutation

R42 verifies the prepared target archive again, proves the target image is already present with the exact expected runtime identity, and proves the Home Assistant binding already points at the target.

It then calls LocalU11RuntimeOwner.start_target_owner(). This keeps systemd as the production owner and uses the repaired effective HA-OTA supervision contract; R42 does not construct a manual Docker start path.

After runtime identity and the production /config bind are proven, R42 calls the existing record_target_started transition. Durability order remains USB U11 metadata first, host U11 transaction second.

Success ends at U11_TARGET_INSTALLED_STARTED. U12 health acceptance is explicitly out of scope.

## 7. Forbidden actions

R42 forbids R40 replay, target image reload, Compose binding rewrite, predecessor image manipulation, backup rewrite, filesystem destructive operations, U12/U13, board access and merge.

## 8. Failure semantics

There is no automatic rollback and no automatic retry after claim.

A postclaim failure records the strongest available transaction, USB phase and services-owner evidence and returns STOP_POSTCLAIM with recovery_required=true and replay_permitted=false.

If the failure ledger itself cannot be proven durable, the result escalates to STOP_UNKNOWN.

If SSH result delivery is ambiguous, the local executor performs a read-only status reconciliation against the R42 durable ledger and never replays the live action just because output was lost.

## 9. Preauthorization boundary

This source package is initially committed with live_recovery_authorized=false and authorization_state.granted=false. The local executor checks that state before evidence-root creation or T1 transport.

After source review and CI close, explicit user authorization is still required. The grant must be a grant-only successor manifest change, followed by fresh exact-head CI and final review before real-T1 execution.
