# N3-W R2B Board B Existing-Identity Credential Recovery Closeout

Date: 2026-09-02

## Scope

This is the public-safe closeout for the Board B existing-identity MQTT credential recovery performed during `N3W_THREE_BOARD_REGRESSION_RETEST`.

`FC4_FINAL_PHYSICAL_ACCEPTANCE=FROZEN_PASS` remains unchanged. This R2B recovery did not reopen FC4.

## Product-source authority

- Frozen/deployed product-source revision: `8fbedc7e0778ce91d146cd5f0772bebdd20ad13a`
- Frozen product-source tree: `77b5d89164bdb966555938f838804522fe865f7e`
- PR #350 merged into that product-source revision and supplied the explicit existing-identity credential-recovery product path.
- Documentation-only repository `main` advancement after that revision is tracked separately and does not redefine the deployed product source.

## Recovery authorization

Authorization: `R2B-BOARD-B-EXISTING-IDENTITY-CREDENTIAL-RECOVERY-20260902-01`

Final authorization state:

```text
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
AUTHORIZATION_REPLAY_PERMITTED=false
```

The authorization must never be replayed.

## Recovery closure

The recovery completed successfully with these public-safe results:

```text
PAIRING_STATE=approved
CREDENTIAL_STATE=active
CREDENTIAL_GENERATION_BEFORE=1
CREDENTIAL_GENERATION_AFTER=2
PENDING_GENERATION_AFTER=NONE
APPLICATION_KEY_EPOCH_BEFORE=1
APPLICATION_KEY_EPOCH_AFTER=1
APPLICATION_KEY_MATERIAL_PRESERVED=true
PEER_TRUST_GENERATION_BEFORE=1
PEER_TRUST_GENERATION_AFTER=1
PEER_KEY_MATERIAL_PRESERVED=true
BROKER_CHANGEINDEX_BEFORE=30
BROKER_CHANGEINDEX_AFTER=31
BROKER_CHANGEINDEX_DELTA=1
BROKER_TARGET_CLIENT_EXACT=true
BROKER_TARGET_ROLE_EXACT=true
BROKER_TARGET_ROLE_BINDING_EXACT=true
BROKER_TARGET_ACL_SEMANTIC_EXACT=true
BROKER_TARGET_ENCODED_PASSWORD_ROTATED=true
BROKER_TARGET_PLAINTEXT_CREDENTIAL_FIELDS_ABSENT=true
NON_TARGET_BROKER_SEMANTIC_PRESERVED=true
BOARD_B_DURABLE_WRITE_EVIDENCE=VALID_RECEIPT_COMMIT_CHAIN_WITH_GENERATION2_ACTIVE
BOARD_B_DURABLE_WRITE_OBSERVED=true
BOARD_A_MUTATION=false
BOARD_C_MUTATION=false
FLASH=false
NVS_ERASE=false
MANUAL_RESET=false
MUTATION_CLOSURE_PASS=true
```

The generation-2 recovery plan SHA-256 was `9e306ee9367b29dba7c73657daab6f681616516157c2167baba1904764958a0e`; its ACL semantic SHA-256 was `df1293308975495213cb8aa582c1a1644fd15aace6df25d56b1dd112711c079b`.

## Post-closure Manager/Broker verification

A separate read-only verifier confirmed:

- Manager and Broker running under the expected frozen runtime authority;
- pairing state `approved` and repair authorization cleared;
- credential generation 2 active and no pending generation;
- application-key epoch 1 and SYSTEM_PEER_KEY generation 1 preserved;
- active Broker `changeIndex=31`;
- exact target client/role/ACL preserved;
- rotated encoded password still present and plaintext credential fields absent;
- non-target Broker semantic state preserved.

The current active DynSec file SHA-256 after recovery was `6e875b356017c5d1130554fdc67ce623f675bf860d0bc1daedcce8f32af56e05`.

## Serial/runtime adjudication

The first 40-second read-only serial verifier observed:

```text
TELEMETRY_COUNT=8
TELEMETRY_SEQ_STRICTLY_INCREASING=true
TELEMETRY_ACCEPTED_COUNT=8
TELEMETRY_REJECTED_COUNT=0
DIRECT_TELEMETRY_COUNT=8
DIRECT_ACCEPTED_COUNT=8
DIRECT_RUNTIME_HEALTHY=true
PAIRING_PAYLOAD_COUNT=3
```

Because a whole-window `pairing payload count == 0` oracle could not distinguish live pairing output from stale/transient serial-buffer material, this was classified as an oracle ambiguity rather than a product failure.

A second read-only serial-quiescence adjudicator used a 20-second stabilization window followed by a 50-second authoritative verification window:

```text
STABILIZATION_PAIRING_PAYLOAD_COUNT=0
VERIFICATION_PAIRING_PAYLOAD_COUNT=0
VERIFICATION_TELEMETRY_COUNT=10
VERIFICATION_TELEMETRY_SEQ_STRICTLY_INCREASING=true
VERIFICATION_TELEMETRY_ACCEPTED_COUNT=10
VERIFICATION_TELEMETRY_REJECTED_COUNT=0
VERIFICATION_DIRECT_TELEMETRY_COUNT=10
VERIFICATION_DIRECT_ACCEPTED_COUNT=10
VERIFICATION_TELEMETRY_SPAN_SECONDS=45.004
POSTCLOSURE_PAIRING_QUIESCENCE_PROVEN=true
ADJUDICATION_PASS=true
```

Therefore generation-2 Direct runtime use and post-closure pairing quiescence are proven.

## Remaining boundary

```text
REBOOT_PERSISTENCE_TESTED=false
```

No operator-induced reboot, reset, or power-cycle was authorized in the post-closure read-only stage. This closeout proves durable state was used by the running Board B runtime after recovery; it does not claim a separate reboot-persistence test.

## KF-075 disposition

`KF-075=GUARDED`.

The product defect is no longer OPEN because the source path is merged, the deployed runtime is bound to the repaired source, the explicit exact-pairing recovery was successfully exercised on Board B, and post-closure Manager/Broker/runtime evidence is PASS.

## Mainline return

R2B now exits the Board B credential-recovery detour. Board A and Board C retained runtime-active state; Board B has recovered generation-2 credentials and healthy Direct runtime. The next mainline activity is fresh A→B→C R2 runtime liveness under `N3W_THREE_BOARD_REGRESSION_RETEST`.
