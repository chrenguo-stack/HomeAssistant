# H3/N2 Stage 2D-9R G3R D2-17 G13 consumed failure and G14 mode-normalized execution view

## Frozen G13 terminal

G13 is permanently retired as `CONSUMED_FAILED_PRECLAIM`. Authorization claim and consume are both true. Replay, retry, package reuse and authorization reuse are forbidden.

The terminal record is `93c3ccb94adf3c185e1da6e535c93e9e9fc32edaf1121f00c8da63ccdb4cca2d`; the leaf failure is `PACKAGE_FILE_INVALID` at `PRECLAIM`. No Flash, network, Broker, PREPARE, VERIFY, recovery, ACTIVATE or CLEANUP operation occurred.

## Deterministic root cause

The frozen D2-17 canonical builder creates both shell entry files with mode `0700` and records those modes in the delivery manifest. The inherited successor preclaim verifier applies `regular(path, "0600", "PACKAGE_FILE_INVALID")` to every `SHA256SUMS` member. Once G13 reached the inherited executor, the two valid delivery shell modes therefore failed the older all-files-0600 preclaim contract.

Conflicting files:

- `run_d2_17_canonical_delivery_outer_20260730_v1.sh`;
- `run_stage2d9r_g3r_d2_17_execution_identity_frozen_physical_d2_20260730_v1.sh`.

## G14 repair contract

G14 must not mutate the canonical frozen execution root. Before entering the inherited executor it must create a new dedicated execution view that:

1. contains exactly the same regular files and bytes as the canonical root;
2. rejects source symlinks, directories, missing or unexpected `SHA256SUMS` members, and digest drift;
3. assigns mode `0600` to every copied file and mode `0700` only to the view directory;
4. validates content equivalence and the inherited all-files-0600 requirement;
5. passes the view as the inner inherited executor package root while retaining the canonical root for public identity and authorization verification;
6. is new for G14 and must never reuse G13 runtime, package, authorization or marker material.

The repair is host-only at this gate. It authorizes no private package, target-Mac static check or physical operation.

## Bindings and next gate

- G13 disposition binding: `2c37dcd807731d47c25f7a5b6a2ec0a03add0efc01ee461526cd95f86868915c`;
- G14 pending binding: `a91a3b699122ee83af663ef2c014115d1db02b28b9aa8890876a810462023d92`;
- next gate: `D1-H3N2-STAGE2D9R-G3R-D2-17-G14-PRIVATE-PACKAGE-AND-TARGET-MAC-STATIC-CHECK-AUTHORIZATION-CREATION-20260731-01`.

Ready, merge, release, tag, deployment, ACTIVATE and CLEANUP remain forbidden.
