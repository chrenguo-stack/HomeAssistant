# H3/N2 Stage 2D-9R G3R D2-17 G04 target Mac static-check acceptance contract

## Scope

This public, secret-free contract records the successful G04 target Mac static-check and closes the gate immediately before physical execution.

The accepted terminal state is:

`TARGET_MAC_STATIC_CHECK_PASSED_AUTHORIZATION_UNCLAIMED_UNCONSUMED`

The G04 authorization exists, but it remains unclaimed and unconsumed. No physical decision has been created.

## Exact public boundary

- base Draft PR: #222;
- exact base HEAD: `0691b3c85cf3ee018cd07cf038138cbf4dcd1f34`;
- public execution Artifact: `8752919376`;
- terminal semantic-digest repair Artifact: `8757007857`;
- nested SHA256SUMS set-normalization repair Artifact: `8760604398`;
- G04 private-delivery binding: `95181293b0efc931718d62a269327ac633cf8e2be81c5dd2a8b8bf4ddc639906`;
- G04 authorization record SHA-256: `be4fa360d122350cece9bc312bf781be8d9f7879cb08bf2330f5e01e8be612ef`.

The public record contains only hashes, identifiers, booleans and timestamps. It does not contain the authorization document, execution identity document, local paths, private logs, board identity or secret values.

## Accepted safety state

The acceptance record must prove all of the following:

- `status == PASS`;
- authorization created/claimed/consumed is `true/false/false`;
- physical decision created is `false`;
- board, USB, serial, esptool, Flash/NVS, Broker, PREPARE, VERIFY, recovery, ACTIVATE and CLEANUP were not executed;
- replay and automatic retry are forbidden;
- G01, G02 and G03 private materials were not reused;
- the terminal record uses canonical JSON semantic-digest rules;
- Ready, merge, release, tag and deployment remain forbidden.

## Physical gate

The next decision is:

`D1-H3N2-STAGE2D9R-G3R-D2-17-G04-PHYSICAL-EXECUTION-20260730-01`

Until that exact decision is explicitly approved, claim, consume and every physical operation remain unauthorized.

Any drift in PR state, exact HEAD, CI, Artifact digest, authorization record, expiry, target-tool digest, execution identity or terminal binding requires a new decision. An expired authorization cannot be extended or edited; a new generation is required.
